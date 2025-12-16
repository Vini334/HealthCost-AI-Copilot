"""
Endpoints de upload de documentos.

Responsável por:
- Upload de contratos (PDF)
- Upload de dados de custos (CSV/Excel)
- Validação de arquivos
- Armazenamento no Azure Blob Storage
- Registro de metadados no Cosmos DB
"""

import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from src.config.logging import get_logger
from src.models.documents import (
    ALLOWED_CONTRACT_EXTENSIONS,
    ALLOWED_CONTRACT_TYPES,
    ALLOWED_COST_EXTENSIONS,
    ALLOWED_COST_TYPES,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    DocumentMetadata,
    DocumentStatus,
    DocumentType,
    UploadResponse,
)
from src.storage.blob_storage import get_blob_storage_client
from src.storage.cosmos_db import get_cosmos_client

logger = get_logger(__name__)

# Cria o router com prefixo /upload e tag para documentação
router = APIRouter(prefix="/upload", tags=["upload"])


def _get_file_extension(filename: str) -> str:
    """
    Extrai a extensão do arquivo (com ponto).

    Args:
        filename: Nome do arquivo

    Returns:
        Extensão em minúsculas (ex: ".pdf", ".csv")
    """
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _validate_file_size(file: UploadFile) -> None:
    """
    Valida o tamanho do arquivo.

    Args:
        file: Arquivo do upload

    Raises:
        HTTPException: Se o arquivo for muito grande

    Nota: UploadFile.size pode ser None em alguns casos,
          então verificamos também durante a leitura.
    """
    if file.size and file.size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande. Máximo permitido: {MAX_FILE_SIZE_MB}MB",
        )


def _validate_contract_file(file: UploadFile) -> None:
    """
    Valida arquivo de contrato (deve ser PDF).

    Args:
        file: Arquivo do upload

    Raises:
        HTTPException: Se o arquivo não for PDF válido
    """
    _validate_file_size(file)

    # Verifica extensão
    extension = _get_file_extension(file.filename or "")
    if extension not in ALLOWED_CONTRACT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensão inválida '{extension}'. Apenas PDFs são aceitos.",
        )

    # Verifica content-type
    if file.content_type and file.content_type not in ALLOWED_CONTRACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo inválido '{file.content_type}'. Apenas PDF é aceito.",
        )


def _validate_cost_file(file: UploadFile) -> None:
    """
    Valida arquivo de dados de custos (CSV ou Excel).

    Args:
        file: Arquivo do upload

    Raises:
        HTTPException: Se o arquivo não for CSV/Excel válido
    """
    _validate_file_size(file)

    extension = _get_file_extension(file.filename or "")
    if extension not in ALLOWED_COST_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensão inválida '{extension}'. Aceitos: CSV, XLS, XLSX.",
        )

    if file.content_type and file.content_type not in ALLOWED_COST_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo inválido '{file.content_type}'. Aceitos: CSV, Excel.",
        )


# ============================================================
# ENDPOINT: Upload de Contrato (PDF)
# ============================================================

@router.post(
    "/contract",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de contrato PDF",
    description="""
    Faz upload de um contrato em formato PDF.

    O arquivo será:
    1. Validado (tamanho, formato)
    2. Armazenado no Azure Blob Storage
    3. Registrado no Cosmos DB com status "uploaded"

    O processamento (extração de texto, indexação) acontecerá depois
    de forma assíncrona.
    """,
)
async def upload_contract(
    file: UploadFile = File(..., description="Arquivo PDF do contrato"),
    client_id: str = Form(..., description="ID do cliente (multi-tenancy)"),
    contract_id: Optional[str] = Form(
        None,
        description="ID do contrato (opcional, se já existir no sistema)",
    ),
) -> UploadResponse:
    """
    Upload de contrato PDF.

    Args:
        file: Arquivo PDF enviado via multipart/form-data
        client_id: ID do cliente dono do contrato
        contract_id: ID do contrato (opcional)

    Returns:
        UploadResponse com informações do documento criado

    Raises:
        HTTPException 400: Arquivo inválido
        HTTPException 413: Arquivo muito grande
        HTTPException 500: Erro interno

    Exemplo de chamada com curl:
        curl -X POST "http://localhost:8000/api/v1/upload/contract" \\
             -H "Content-Type: multipart/form-data" \\
             -F "file=@contrato.pdf" \\
             -F "client_id=cliente-123"
    """
    logger.info(
        "Recebendo upload de contrato",
        filename=file.filename,
        client_id=client_id,
        content_type=file.content_type,
        size=file.size,
    )

    # 1. Validar arquivo
    _validate_contract_file(file)

    # 2. Gerar ID único para o documento
    document_id = uuid4()

    # 3. Ler conteúdo do arquivo
    # Precisamos ler aqui porque vamos enviar para o Blob Storage
    try:
        file_content = await file.read()
        file_size = len(file_content)

        # Validação extra de tamanho após leitura
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Arquivo muito grande. Máximo permitido: {MAX_FILE_SIZE_MB}MB",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo vazio não é permitido",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao ler arquivo", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar arquivo",
        )

    # 4. Upload para Blob Storage
    try:
        blob_client = get_blob_storage_client()

        # BytesIO para criar um file-like object do conteúdo
        from io import BytesIO

        file_stream = BytesIO(file_content)

        blob_path = await blob_client.upload_contract(
            file_content=file_stream,
            client_id=client_id,
            document_id=str(document_id),
            filename=file.filename or "contrato.pdf",
            content_type=file.content_type or "application/pdf",
        )

    except Exception as e:
        logger.error("Erro no upload para Blob Storage", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao armazenar arquivo",
        )

    # 5. Criar metadados no Cosmos DB
    try:
        cosmos_client = get_cosmos_client()

        metadata = DocumentMetadata(
            id=document_id,
            client_id=client_id,
            filename=file.filename or "contrato.pdf",
            file_size=file_size,
            content_type=file.content_type or "application/pdf",
            document_type=DocumentType.CONTRACT,
            blob_path=blob_path,
            container_name="contracts",
            status=DocumentStatus.UPLOADED,
            contract_id=contract_id,
        )

        await cosmos_client.create_document_metadata(metadata)

    except Exception as e:
        logger.error("Erro ao salvar metadados", error=str(e))
        # Idealmente deveríamos reverter o upload do blob aqui
        # Por simplicidade, apenas logamos e retornamos erro
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar documento",
        )

    logger.info(
        "Upload de contrato concluído com sucesso",
        document_id=str(document_id),
        blob_path=blob_path,
    )

    return UploadResponse(
        success=True,
        document_id=document_id,
        filename=file.filename or "contrato.pdf",
        blob_path=blob_path,
        message="Contrato enviado com sucesso. Processamento será iniciado em breve.",
    )


# ============================================================
# ENDPOINT: Upload de Dados de Custos (CSV/Excel)
# ============================================================

@router.post(
    "/costs",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de dados de custos",
    description="""
    Faz upload de planilha de custos (CSV ou Excel).

    O arquivo será:
    1. Validado (tamanho, formato)
    2. Armazenado no Azure Blob Storage
    3. Registrado no Cosmos DB com status "uploaded"

    O processamento (parsing, normalização) acontecerá depois.
    """,
)
async def upload_costs(
    file: UploadFile = File(..., description="Arquivo CSV ou Excel"),
    client_id: str = Form(..., description="ID do cliente"),
    contract_id: Optional[str] = Form(
        None,
        description="ID do contrato relacionado (opcional)",
    ),
) -> UploadResponse:
    """
    Upload de dados de custos (CSV/Excel).

    Args:
        file: Arquivo CSV ou Excel
        client_id: ID do cliente
        contract_id: ID do contrato relacionado (opcional)

    Returns:
        UploadResponse com informações do documento

    Raises:
        HTTPException: Se validação ou upload falhar

    Exemplo com curl:
        curl -X POST "http://localhost:8000/api/v1/upload/costs" \\
             -F "file=@custos-2024.xlsx" \\
             -F "client_id=cliente-123"
    """
    logger.info(
        "Recebendo upload de dados de custos",
        filename=file.filename,
        client_id=client_id,
        content_type=file.content_type,
    )

    # 1. Validar arquivo
    _validate_cost_file(file)

    # 2. Gerar ID único
    document_id = uuid4()

    # 3. Ler conteúdo
    try:
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Arquivo muito grande. Máximo: {MAX_FILE_SIZE_MB}MB",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo vazio não é permitido",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao ler arquivo", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar arquivo",
        )

    # 4. Upload para Blob Storage
    try:
        blob_client = get_blob_storage_client()

        from io import BytesIO

        file_stream = BytesIO(file_content)

        # Determina content_type baseado na extensão se não fornecido
        content_type = file.content_type
        if not content_type:
            ext = _get_file_extension(file.filename or "")
            content_type_map = {
                ".csv": "text/csv",
                ".xls": "application/vnd.ms-excel",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
            content_type = content_type_map.get(ext, "application/octet-stream")

        blob_path = await blob_client.upload_costs(
            file_content=file_stream,
            client_id=client_id,
            document_id=str(document_id),
            filename=file.filename or "custos.csv",
            content_type=content_type,
        )

    except Exception as e:
        logger.error("Erro no upload para Blob Storage", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao armazenar arquivo",
        )

    # 5. Criar metadados no Cosmos DB
    try:
        cosmos_client = get_cosmos_client()

        metadata = DocumentMetadata(
            id=document_id,
            client_id=client_id,
            filename=file.filename or "custos.csv",
            file_size=file_size,
            content_type=content_type,
            document_type=DocumentType.COST_DATA,
            blob_path=blob_path,
            container_name="costs",
            status=DocumentStatus.UPLOADED,
            contract_id=contract_id,
        )

        await cosmos_client.create_document_metadata(metadata)

    except Exception as e:
        logger.error("Erro ao salvar metadados", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar documento",
        )

    logger.info(
        "Upload de custos concluído",
        document_id=str(document_id),
        blob_path=blob_path,
    )

    return UploadResponse(
        success=True,
        document_id=document_id,
        filename=file.filename or "custos.csv",
        blob_path=blob_path,
        message="Dados de custos enviados com sucesso. Processamento será iniciado.",
    )
