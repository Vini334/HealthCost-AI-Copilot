"""
Endpoints de gerenciamento de clientes.

Permite criar, listar, atualizar e remover clientes,
além de consultar seus contratos e status de processamento.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.config.logging import get_logger
from src.models.clients import (
    Client,
    ClientStatus,
    ClientListResponse,
    ClientDetailResponse,
    CreateClientRequest,
    UpdateClientRequest,
    ClientContractsResponse,
    ProcessingStatusResponse,
    ClientStatsResponse,
)
from src.models.documents import DocumentStatus
from src.services.client_service import get_client_service

logger = get_logger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])


# ============================================
# CRUD de Clientes
# ============================================


@router.get(
    "/",
    response_model=ClientListResponse,
    summary="Listar clientes",
    description="""
Lista todos os clientes cadastrados com filtros e paginação.

## Filtros disponíveis

- **status**: Filtra por status (active, inactive, suspended)
- **search**: Busca por nome ou documento (CPF/CNPJ)

## Paginação

Use `limit` e `offset` para paginar resultados.

## Exemplo de resposta

```json
{
    "clients": [
        {
            "id": "uuid-123",
            "name": "Empresa ABC Ltda",
            "document": "12.345.678/0001-90",
            "document_type": "cnpj",
            "status": "active",
            "created_at": "2024-12-16T10:30:00Z"
        }
    ],
    "total_count": 42,
    "has_more": true
}
```
    """,
)
async def list_clients(
    status: Optional[ClientStatus] = Query(None, description="Filtrar por status"),
    search: Optional[str] = Query(None, description="Buscar por nome ou documento"),
    limit: int = Query(20, ge=1, le=100, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Pular primeiros N resultados"),
) -> ClientListResponse:
    """Lista clientes cadastrados."""
    logger.info(
        "Listando clientes",
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )

    try:
        client_service = get_client_service()

        summaries, total, has_more = await client_service.list_clients(
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )

        return ClientListResponse(
            clients=summaries,
            total_count=total,
            has_more=has_more,
        )

    except Exception as e:
        logger.error("Erro ao listar clientes", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar clientes: {str(e)}",
        )


@router.get(
    "/{client_id}",
    response_model=ClientDetailResponse,
    summary="Obter cliente",
    description="""
Retorna detalhes completos de um cliente, incluindo estatísticas.

## Estatísticas incluídas

- Número de contratos
- Número de documentos
- Número de conversas

## Exemplo de resposta

```json
{
    "id": "uuid-123",
    "name": "Empresa ABC Ltda",
    "document": "12.345.678/0001-90",
    "document_type": "cnpj",
    "email": "contato@empresa.com.br",
    "status": "active",
    "contract_count": 3,
    "document_count": 5,
    "conversation_count": 12
}
```
    """,
)
async def get_client(
    client_id: str,
) -> ClientDetailResponse:
    """Retorna detalhes de um cliente."""
    logger.info("Buscando cliente", client_id=client_id)

    try:
        client_service = get_client_service()

        client_detail = await client_service.get_client_detail(client_id)

        if not client_detail:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente não encontrado: {client_id}",
            )

        return client_detail

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao buscar cliente", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar cliente: {str(e)}",
        )


@router.post(
    "/",
    response_model=ClientDetailResponse,
    status_code=201,
    summary="Criar cliente",
    description="""
Cria um novo cliente no sistema.

## Campos obrigatórios

- **name**: Nome ou Razão Social
- **document**: CPF ou CNPJ

## Campos opcionais

- **document_type**: Tipo do documento ('cpf' ou 'cnpj', padrão: 'cnpj')
- **email**: E-mail de contato
- **phone**: Telefone
- **address**: Endereço completo
- **city**: Cidade
- **state**: UF (2 letras)
- **metadata**: Dados adicionais customizados

## Exemplo de requisição

```json
{
    "name": "Empresa ABC Ltda",
    "document": "12.345.678/0001-90",
    "document_type": "cnpj",
    "email": "contato@empresa.com.br",
    "city": "São Paulo",
    "state": "SP"
}
```
    """,
)
async def create_client(
    request: CreateClientRequest,
) -> ClientDetailResponse:
    """Cria um novo cliente."""
    logger.info(
        "Criando cliente",
        client_name=request.name,
        document_type=request.document_type,
    )

    try:
        client_service = get_client_service()

        client = await client_service.create_client(
            name=request.name,
            document=request.document,
            document_type=request.document_type,
            email=request.email,
            phone=request.phone,
            address=request.address,
            city=request.city,
            state=request.state,
            metadata=request.metadata,
        )

        # Retorna detalhes completos
        return ClientDetailResponse(
            id=client.id,
            name=client.name,
            document=client.document,
            document_type=client.document_type,
            email=client.email,
            phone=client.phone,
            address=client.address,
            city=client.city,
            state=client.state,
            status=client.status,
            created_at=client.created_at,
            updated_at=client.updated_at,
            metadata=client.metadata,
            contract_count=0,
            document_count=0,
            conversation_count=0,
        )

    except Exception as e:
        logger.error("Erro ao criar cliente", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao criar cliente: {str(e)}",
        )


@router.patch(
    "/{client_id}",
    response_model=ClientDetailResponse,
    summary="Atualizar cliente",
    description="""
Atualiza dados de um cliente existente.

Apenas os campos fornecidos serão atualizados.

## Campos atualizáveis

- **name**: Nome/Razão Social
- **email**: E-mail
- **phone**: Telefone
- **address**: Endereço
- **city**: Cidade
- **state**: UF
- **status**: Status (active, inactive, suspended)
- **metadata**: Metadados (substitui existentes)

## Exemplo de requisição

```json
{
    "email": "novo-email@empresa.com.br",
    "status": "active"
}
```
    """,
)
async def update_client(
    client_id: str,
    request: UpdateClientRequest,
) -> ClientDetailResponse:
    """Atualiza um cliente."""
    logger.info(
        "Atualizando cliente",
        client_id=client_id,
    )

    try:
        client_service = get_client_service()

        client = await client_service.update_client(
            client_id=client_id,
            name=request.name,
            email=request.email,
            phone=request.phone,
            address=request.address,
            city=request.city,
            state=request.state,
            status=request.status,
            metadata=request.metadata,
        )

        if not client:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente não encontrado: {client_id}",
            )

        # Busca detalhes atualizados com estatísticas
        client_detail = await client_service.get_client_detail(client_id)

        return client_detail

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao atualizar cliente", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao atualizar cliente: {str(e)}",
        )


@router.delete(
    "/{client_id}",
    summary="Remover cliente",
    description="""
Remove ou desativa um cliente.

Por padrão, realiza soft delete (muda status para inactive).
Para remoção permanente, use `permanent=true`.

**Atenção:** Remoção permanente não remove documentos e conversas associados.
    """,
)
async def delete_client(
    client_id: str,
    permanent: bool = Query(False, description="Se True, remove permanentemente"),
) -> dict:
    """Remove um cliente."""
    logger.info(
        "Removendo cliente",
        client_id=client_id,
        permanent=permanent,
    )

    try:
        client_service = get_client_service()

        deleted = await client_service.delete_client(
            client_id=client_id,
            soft_delete=not permanent,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente não encontrado: {client_id}",
            )

        action = "removido permanentemente" if permanent else "desativado"
        return {
            "message": f"Cliente {action} com sucesso",
            "client_id": client_id,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao remover cliente", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao remover cliente: {str(e)}",
        )


# ============================================
# Contratos por Cliente
# ============================================


@router.get(
    "/{client_id}/contracts",
    response_model=ClientContractsResponse,
    summary="Listar contratos do cliente",
    description="""
Lista todos os contratos (documentos PDF) de um cliente.

## Filtros

- **status**: Filtrar por status de processamento (uploaded, processing, indexed, failed)

## Resposta

Inclui informações básicas de cada contrato:
- Nome do arquivo
- Status de processamento
- Data de upload e processamento
    """,
)
async def list_client_contracts(
    client_id: str,
    status: Optional[DocumentStatus] = Query(None, description="Filtrar por status"),
    limit: int = Query(20, ge=1, le=100, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Pular primeiros N resultados"),
) -> ClientContractsResponse:
    """Lista contratos de um cliente."""
    logger.info(
        "Listando contratos do cliente",
        client_id=client_id,
        status=status,
    )

    try:
        client_service = get_client_service()

        # Verifica se cliente existe
        client = await client_service.get_client(client_id)
        if not client:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente não encontrado: {client_id}",
            )

        return await client_service.get_client_contracts(
            client_id=client_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao listar contratos", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar contratos: {str(e)}",
        )


# ============================================
# Status de Processamento
# ============================================


@router.get(
    "/{client_id}/processing-status",
    response_model=ProcessingStatusResponse,
    summary="Status de processamento",
    description="""
Retorna o status de processamento de todos os documentos de um cliente.

## Informações incluídas

- Total de documentos
- Documentos aguardando processamento
- Documentos em processamento
- Documentos processados com sucesso
- Documentos com falha

## Detalhes opcionais

Use `include_documents=true` para incluir lista detalhada de cada documento.

## Exemplo de resposta

```json
{
    "client_id": "uuid-123",
    "total_documents": 10,
    "documents_uploaded": 2,
    "documents_processing": 1,
    "documents_indexed": 6,
    "documents_failed": 1
}
```
    """,
)
async def get_processing_status(
    client_id: str,
    include_documents: bool = Query(False, description="Incluir lista detalhada"),
) -> ProcessingStatusResponse:
    """Retorna status de processamento dos documentos."""
    logger.info(
        "Obtendo status de processamento",
        client_id=client_id,
        include_documents=include_documents,
    )

    try:
        client_service = get_client_service()

        # Verifica se cliente existe
        client = await client_service.get_client(client_id)
        if not client:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente não encontrado: {client_id}",
            )

        return await client_service.get_processing_status(
            client_id=client_id,
            include_documents=include_documents,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao obter status", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter status de processamento: {str(e)}",
        )


# ============================================
# Estatísticas
# ============================================


@router.get(
    "/{client_id}/stats",
    response_model=ClientStatsResponse,
    summary="Estatísticas do cliente",
    description="""
Retorna estatísticas completas de um cliente.

## Métricas incluídas

### Documentos
- Total de contratos
- Total de arquivos de custos
- Documentos pendentes vs prontos

### Conversas
- Total de conversas
- Conversas ativas

### Custos (se houver dados)
- Total de registros
- Valor total cobrado
- Período dos dados

## Exemplo de resposta

```json
{
    "client_id": "uuid-123",
    "client_name": "Empresa ABC",
    "total_contracts": 3,
    "total_cost_files": 2,
    "documents_pending": 1,
    "documents_ready": 4,
    "total_conversations": 15,
    "total_cost_records": 1250,
    "total_charged_amount": 125000.50,
    "cost_period_start": "2024-01-01",
    "cost_period_end": "2024-12-31"
}
```
    """,
)
async def get_client_stats(
    client_id: str,
) -> ClientStatsResponse:
    """Retorna estatísticas do cliente."""
    logger.info("Obtendo estatísticas", client_id=client_id)

    try:
        client_service = get_client_service()

        stats = await client_service.get_client_stats(client_id)

        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente não encontrado: {client_id}",
            )

        return stats

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao obter estatísticas", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter estatísticas: {str(e)}",
        )
