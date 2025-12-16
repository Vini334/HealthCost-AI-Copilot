"""
Serviço de processamento de dados de custos.

Orquestra o fluxo de processamento de arquivos CSV/Excel:
1. Baixar arquivo do Blob Storage
2. Parsear CSV/Excel
3. Validar colunas
4. Normalizar dados
5. Criar registros de custos
6. Armazenar no Cosmos DB
7. Atualizar status do documento
"""

import re
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Optional, Union
from uuid import UUID

import pandas as pd

from src.config.logging import get_logger
from src.models.costs import (
    COLUMN_ALIASES,
    ColumnMapping,
    ColumnValidationResult,
    CostCategory,
    CostProcessingResult,
    CostRecord,
    UtilizationType,
)
from src.models.documents import DocumentMetadata, DocumentStatus
from src.storage.blob_storage import get_blob_storage_client
from src.storage.cosmos_db import get_cosmos_client

logger = get_logger(__name__)


class CostDataProcessor:
    """
    Processa arquivos de custos (CSV/Excel).

    Fluxo completo:
        Arquivo (Blob Storage)
            ↓
        Leitura (pandas)
            ↓
        Validação de colunas
            ↓
        Normalização de dados
            ↓
        Registros de custos

    Exemplo de uso:
        processor = CostDataProcessor()
        result = await processor.process_document(
            document_id="abc-123",
            client_id="cliente-456"
        )
        if result.success:
            print(f"Processados {result.processed_rows} registros")
    """

    # Tamanho do batch para inserção no Cosmos DB
    BATCH_SIZE = 100

    def __init__(self, custom_mapping: Optional[ColumnMapping] = None):
        """
        Inicializa o processador.

        Args:
            custom_mapping: Mapeamento customizado de colunas (opcional).
                           Se não fornecido, tenta detectar automaticamente.
        """
        self.custom_mapping = custom_mapping
        logger.info("CostDataProcessor inicializado")

    def _normalize_column_name(self, name: str) -> str:
        """
        Normaliza nome de coluna para comparação.

        - Converte para minúsculas
        - Remove acentos
        - Remove caracteres especiais
        - Substitui espaços por underscore

        Args:
            name: Nome original da coluna

        Returns:
            Nome normalizado
        """
        # Minúsculas
        name = name.lower().strip()

        # Remove acentos (simplificado)
        replacements = {
            "á": "a", "à": "a", "ã": "a", "â": "a",
            "é": "e", "ê": "e",
            "í": "i",
            "ó": "o", "ô": "o", "õ": "o",
            "ú": "u", "ü": "u",
            "ç": "c",
        }
        for old, new in replacements.items():
            name = name.replace(old, new)

        # Remove caracteres especiais e substitui espaços
        name = re.sub(r"[^\w\s]", "", name)
        name = re.sub(r"\s+", "_", name)

        return name

    def _detect_column_mapping(
        self,
        columns: list[str],
    ) -> ColumnValidationResult:
        """
        Detecta automaticamente o mapeamento de colunas.

        Usa os aliases definidos em COLUMN_ALIASES para encontrar
        as colunas correspondentes.

        Args:
            columns: Lista de nomes de colunas do arquivo

        Returns:
            ColumnValidationResult com o mapeamento detectado
        """
        # Normaliza todas as colunas
        normalized_columns = {
            self._normalize_column_name(col): col
            for col in columns
        }

        found_mapping = {}
        found_columns = []
        missing_required = []
        unrecognized = list(columns)
        warnings = []

        # Campos obrigatórios
        required_fields = [
            "service_date",
            "procedure_description",
            "charged_amount",
            "paid_amount",
        ]

        # Tenta encontrar cada campo
        for field_name, aliases in COLUMN_ALIASES.items():
            found = False

            for alias in aliases:
                normalized_alias = self._normalize_column_name(alias)

                if normalized_alias in normalized_columns:
                    original_column = normalized_columns[normalized_alias]
                    found_mapping[field_name] = original_column
                    found_columns.append(original_column)

                    # Remove da lista de não reconhecidas
                    if original_column in unrecognized:
                        unrecognized.remove(original_column)

                    found = True
                    break

            # Verifica se campo obrigatório está faltando
            if not found and field_name in required_fields:
                missing_required.append(field_name)

        # Valida resultado
        valid = len(missing_required) == 0

        # Avisos para colunas não reconhecidas
        if unrecognized:
            warnings.append(
                f"Colunas não reconhecidas (serão ignoradas): {', '.join(unrecognized[:5])}"
            )
            if len(unrecognized) > 5:
                warnings.append(f"... e mais {len(unrecognized) - 5} colunas")

        # Cria o mapeamento se válido
        mapping = None
        if valid:
            mapping = ColumnMapping(**found_mapping)

        return ColumnValidationResult(
            valid=valid,
            mapping=mapping,
            found_columns=found_columns,
            missing_required=missing_required,
            unrecognized=unrecognized,
            warnings=warnings,
        )

    def _parse_date(self, value) -> Optional[date]:
        """
        Converte valor para data.

        Suporta múltiplos formatos comuns em arquivos brasileiros.

        Args:
            value: Valor a converter (string, datetime, date)

        Returns:
            date ou None se não conseguir converter
        """
        if pd.isna(value) or value is None:
            return None

        if isinstance(value, date):
            return value

        if isinstance(value, datetime):
            return value.date()

        # Tenta converter string
        value_str = str(value).strip()
        if not value_str:
            return None

        # Formatos comuns
        formats = [
            "%d/%m/%Y",      # 31/12/2024
            "%Y-%m-%d",      # 2024-12-31
            "%d-%m-%Y",      # 31-12-2024
            "%d.%m.%Y",      # 31.12.2024
            "%Y/%m/%d",      # 2024/12/31
            "%d/%m/%y",      # 31/12/24
            "%m/%d/%Y",      # 12/31/2024 (formato americano)
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value_str, fmt).date()
            except ValueError:
                continue

        return None

    def _parse_decimal(self, value) -> Optional[Decimal]:
        """
        Converte valor para Decimal.

        Trata diferentes formatos numéricos brasileiros.

        Args:
            value: Valor a converter

        Returns:
            Decimal ou None se não conseguir converter
        """
        if pd.isna(value) or value is None:
            return None

        if isinstance(value, (int, float)):
            if pd.isna(value):
                return None
            return Decimal(str(value))

        if isinstance(value, Decimal):
            return value

        # Tenta converter string
        value_str = str(value).strip()
        if not value_str:
            return None

        # Remove símbolos de moeda
        value_str = value_str.replace("R$", "").replace("$", "").strip()

        # Tenta detectar formato brasileiro (1.234,56) vs americano (1,234.56)
        # Se tiver vírgula após ponto, é formato brasileiro
        if "," in value_str and "." in value_str:
            if value_str.rfind(",") > value_str.rfind("."):
                # Formato brasileiro: 1.234,56
                value_str = value_str.replace(".", "").replace(",", ".")
            else:
                # Formato americano: 1,234.56
                value_str = value_str.replace(",", "")
        elif "," in value_str:
            # Só tem vírgula - assume brasileiro
            value_str = value_str.replace(",", ".")

        try:
            return Decimal(value_str)
        except InvalidOperation:
            return None

    def _classify_category(
        self,
        description: str,
        category_value: Optional[str] = None,
    ) -> CostCategory:
        """
        Classifica o registro em uma categoria.

        Usa palavras-chave na descrição ou valor explícito da coluna.

        Args:
            description: Descrição do procedimento
            category_value: Valor da coluna de categoria (se existir)

        Returns:
            CostCategory apropriada
        """
        # Se já tem categoria definida, tenta mapear
        if category_value:
            category_lower = category_value.lower().strip()
            category_map = {
                "consulta": CostCategory.CONSULTA,
                "exame": CostCategory.EXAME,
                "procedimento": CostCategory.PROCEDIMENTO,
                "internacao": CostCategory.INTERNACAO,
                "internação": CostCategory.INTERNACAO,
                "pronto_socorro": CostCategory.PRONTO_SOCORRO,
                "pronto socorro": CostCategory.PRONTO_SOCORRO,
                "urgencia": CostCategory.PRONTO_SOCORRO,
                "terapia": CostCategory.TERAPIA,
                "medicamento": CostCategory.MEDICAMENTO,
                "material": CostCategory.MATERIAL,
            }

            for key, cat in category_map.items():
                if key in category_lower:
                    return cat

        # Normaliza descrição (remove acentos para comparação)
        desc_normalized = self._normalize_column_name(description)

        # Classifica por palavras-chave na descrição
        # Ordem importa: mais específicos primeiro
        keywords = {
            CostCategory.TERAPIA: [
                "fisioterapia", "terapia", "fonoaudiologia",
                "psicologia", "sessao",
            ],
            CostCategory.CONSULTA: [
                "consulta", "atendimento medico", "visita",
            ],
            CostCategory.EXAME: [
                "exame", "laboratorio", "radiografia", "ultrassom",
                "tomografia", "ressonancia", "hemograma", "raio_x",
                "raiox", "raio x", "rx", "ecg", "eeg",
            ],
            CostCategory.INTERNACAO: [
                "internacao", "diaria", "leito", "uti", "enfermaria",
            ],
            CostCategory.PRONTO_SOCORRO: [
                "pronto_socorro", "pronto socorro", "emergencia",
                "urgencia",
            ],
            CostCategory.PROCEDIMENTO: [
                "cirurgia", "procedimento", "biopsia", "endoscopia",
                "colonoscopia",
            ],
            CostCategory.MEDICAMENTO: [
                "medicamento", "remedio", "farmacia", "quimioterapia",
            ],
            CostCategory.MATERIAL: [
                "material", "protese", "ortese",
            ],
        }

        for category, words in keywords.items():
            if any(word in desc_normalized for word in words):
                return category

        return CostCategory.OUTROS

    def _parse_utilization_type(
        self,
        value: Optional[str],
    ) -> Optional[UtilizationType]:
        """
        Converte valor para tipo de utilização.

        Args:
            value: Valor da coluna

        Returns:
            UtilizationType ou None
        """
        if not value:
            return None

        value_lower = str(value).lower().strip()

        type_map = {
            "ambulatorial": UtilizationType.AMBULATORIAL,
            "amb": UtilizationType.AMBULATORIAL,
            "hospitalar": UtilizationType.HOSPITALAR,
            "hosp": UtilizationType.HOSPITALAR,
            "internacao": UtilizationType.HOSPITALAR,
            "odontologico": UtilizationType.ODONTOLOGICO,
            "odonto": UtilizationType.ODONTOLOGICO,
            "domiciliar": UtilizationType.DOMICILIAR,
            "home care": UtilizationType.DOMICILIAR,
        }

        for key, ut_type in type_map.items():
            if key in value_lower:
                return ut_type

        return None

    def _read_file(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> pd.DataFrame:
        """
        Lê arquivo CSV ou Excel para DataFrame.

        Args:
            file_bytes: Conteúdo do arquivo
            filename: Nome do arquivo (para determinar formato)

        Returns:
            DataFrame com os dados

        Raises:
            ValueError: Se formato não suportado ou erro na leitura
        """
        file_stream = BytesIO(file_bytes)
        extension = filename.lower().split(".")[-1]

        try:
            if extension == "csv":
                # Tenta detectar encoding e separador
                encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
                separators = [",", ";", "\t"]

                for encoding in encodings:
                    for sep in separators:
                        try:
                            file_stream.seek(0)
                            df = pd.read_csv(
                                file_stream,
                                encoding=encoding,
                                sep=sep,
                                dtype=str,  # Lê tudo como string inicialmente
                            )
                            # Verifica se deu certo (mais de 1 coluna)
                            if len(df.columns) > 1:
                                logger.info(
                                    "CSV lido com sucesso",
                                    encoding=encoding,
                                    separator=sep,
                                    rows=len(df),
                                    columns=len(df.columns),
                                )
                                return df
                        except Exception:
                            continue

                raise ValueError("Não foi possível ler o arquivo CSV")

            elif extension in ("xls", "xlsx"):
                df = pd.read_excel(
                    file_stream,
                    dtype=str,  # Lê tudo como string
                    engine="openpyxl" if extension == "xlsx" else "xlrd",
                )
                logger.info(
                    "Excel lido com sucesso",
                    rows=len(df),
                    columns=len(df.columns),
                )
                return df

            else:
                raise ValueError(f"Formato não suportado: {extension}")

        except Exception as e:
            logger.error("Erro ao ler arquivo", error=str(e))
            raise ValueError(f"Erro ao ler arquivo: {str(e)}")

    def _process_row(
        self,
        row: pd.Series,
        row_number: int,
        mapping: ColumnMapping,
        document_id: UUID,
        client_id: str,
        contract_id: Optional[str],
    ) -> tuple[Optional[CostRecord], Optional[dict]]:
        """
        Processa uma linha do arquivo e cria um CostRecord.

        Args:
            row: Linha do DataFrame
            row_number: Número da linha (para rastreabilidade)
            mapping: Mapeamento de colunas
            document_id: ID do documento
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)

        Returns:
            Tupla (CostRecord, None) se sucesso ou (None, erro) se falha
        """
        try:
            # Extrai campos obrigatórios
            service_date = self._parse_date(row.get(mapping.service_date))
            if not service_date:
                return None, {
                    "row": row_number,
                    "field": "service_date",
                    "error": "Data inválida ou ausente",
                    "value": str(row.get(mapping.service_date)),
                }

            procedure_desc = str(row.get(mapping.procedure_description, "")).strip()
            # Trata "nan" do pandas como vazio
            if not procedure_desc or procedure_desc.lower() == "nan":
                return None, {
                    "row": row_number,
                    "field": "procedure_description",
                    "error": "Descrição ausente",
                }

            charged_amount = self._parse_decimal(row.get(mapping.charged_amount))
            if charged_amount is None:
                charged_amount = Decimal("0")

            paid_amount = self._parse_decimal(row.get(mapping.paid_amount))
            if paid_amount is None:
                paid_amount = Decimal("0")

            # Extrai campos opcionais
            beneficiary_id = None
            if mapping.beneficiary_id:
                val = row.get(mapping.beneficiary_id)
                beneficiary_id = str(val).strip() if pd.notna(val) else None

            beneficiary_name = None
            if mapping.beneficiary_name:
                val = row.get(mapping.beneficiary_name)
                beneficiary_name = str(val).strip() if pd.notna(val) else None

            beneficiary_cpf = None
            if mapping.beneficiary_cpf:
                val = row.get(mapping.beneficiary_cpf)
                beneficiary_cpf = str(val).strip() if pd.notna(val) else None

            procedure_code = None
            if mapping.procedure_code:
                val = row.get(mapping.procedure_code)
                procedure_code = str(val).strip() if pd.notna(val) else None

            provider_code = None
            if mapping.provider_code:
                val = row.get(mapping.provider_code)
                provider_code = str(val).strip() if pd.notna(val) else None

            provider_name = None
            if mapping.provider_name:
                val = row.get(mapping.provider_name)
                provider_name = str(val).strip() if pd.notna(val) else None

            # Classifica categoria
            category_value = None
            if mapping.category:
                val = row.get(mapping.category)
                category_value = str(val).strip() if pd.notna(val) else None

            category = self._classify_category(procedure_desc, category_value)

            # Tipo de utilização
            utilization_type = None
            if mapping.utilization_type:
                val = row.get(mapping.utilization_type)
                utilization_type = self._parse_utilization_type(
                    str(val) if pd.notna(val) else None
                )

            # Cria o registro
            record = CostRecord(
                document_id=document_id,
                client_id=client_id,
                contract_id=contract_id,
                source_row_number=row_number,
                beneficiary_id=beneficiary_id,
                beneficiary_name=beneficiary_name,
                beneficiary_cpf=beneficiary_cpf,
                service_date=service_date,
                procedure_code=procedure_code,
                procedure_description=procedure_desc,
                provider_code=provider_code,
                provider_name=provider_name,
                charged_amount=charged_amount,
                paid_amount=paid_amount,
                category=category,
                utilization_type=utilization_type,
            )

            return record, None

        except Exception as e:
            return None, {
                "row": row_number,
                "error": str(e),
            }

    async def process_document(
        self,
        document_id: Union[str, UUID],
        client_id: str,
    ) -> CostProcessingResult:
        """
        Processa um documento de custos já armazenado.

        Este método:
        1. Busca metadados do documento no Cosmos DB
        2. Baixa o arquivo do Blob Storage
        3. Parseia CSV/Excel
        4. Valida colunas
        5. Processa cada linha
        6. Armazena registros no Cosmos DB
        7. Atualiza status do documento

        Args:
            document_id: ID do documento (UUID)
            client_id: ID do cliente

        Returns:
            CostProcessingResult com estatísticas do processamento
        """
        start_time = time.time()
        doc_id = str(document_id)

        logger.info(
            "Iniciando processamento de dados de custos",
            document_id=doc_id,
            client_id=client_id,
        )

        # 1. Buscar metadados do documento
        cosmos_client = get_cosmos_client()
        metadata = await cosmos_client.get_document_metadata(doc_id, client_id)

        if not metadata:
            logger.error("Documento não encontrado", document_id=doc_id)
            return CostProcessingResult(
                document_id=UUID(doc_id),
                success=False,
                error_message="Documento não encontrado",
            )

        # 2. Atualizar status para PROCESSING
        await cosmos_client.update_document_status(
            document_id=doc_id,
            client_id=client_id,
            status=DocumentStatus.PROCESSING,
        )

        try:
            # 3. Baixar arquivo do Blob Storage
            logger.info(
                "Baixando arquivo do Blob Storage",
                blob_path=metadata.blob_path,
                container=metadata.container_name,
            )

            blob_client = get_blob_storage_client()
            file_bytes = await blob_client.download_blob(
                container_name=metadata.container_name,
                blob_path=metadata.blob_path,
            )

            logger.info("Arquivo baixado", size_bytes=len(file_bytes))

            # 4. Processar os bytes
            result = await self.process_bytes(
                file_bytes=file_bytes,
                filename=metadata.filename,
                document_id=metadata.id,
                client_id=client_id,
                contract_id=metadata.contract_id,
            )

            # 5. Atualizar status final
            if result.success:
                await cosmos_client.update_document_status(
                    document_id=doc_id,
                    client_id=client_id,
                    status=DocumentStatus.INDEXED,
                )
            else:
                await cosmos_client.update_document_status(
                    document_id=doc_id,
                    client_id=client_id,
                    status=DocumentStatus.FAILED,
                    error_message=result.error_message,
                )

            return result

        except Exception as e:
            logger.error(
                "Erro no processamento",
                document_id=doc_id,
                error=str(e),
            )

            await cosmos_client.update_document_status(
                document_id=doc_id,
                client_id=client_id,
                status=DocumentStatus.FAILED,
                error_message=str(e),
            )

            return CostProcessingResult(
                document_id=UUID(doc_id),
                success=False,
                error_message=str(e),
                processing_time_seconds=time.time() - start_time,
            )

    async def process_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        document_id: UUID,
        client_id: str,
        contract_id: Optional[str] = None,
        store_records: bool = True,
    ) -> CostProcessingResult:
        """
        Processa arquivo de custos diretamente de bytes.

        Versão que não depende de Blob Storage.
        Útil para testes ou processamento inline.

        Args:
            file_bytes: Conteúdo do arquivo
            filename: Nome do arquivo (para determinar formato)
            document_id: ID do documento
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            store_records: Se True, armazena registros no Cosmos DB

        Returns:
            CostProcessingResult com estatísticas
        """
        start_time = time.time()

        logger.info(
            "Processando arquivo de custos",
            filename=filename,
            size_bytes=len(file_bytes),
            document_id=str(document_id),
        )

        try:
            # 1. Ler arquivo
            df = self._read_file(file_bytes, filename)
            total_rows = len(df)

            if total_rows == 0:
                return CostProcessingResult(
                    document_id=document_id,
                    success=False,
                    error_message="Arquivo vazio",
                    processing_time_seconds=time.time() - start_time,
                )

            # 2. Validar/detectar colunas
            if self.custom_mapping:
                mapping = self.custom_mapping
                validation = ColumnValidationResult(
                    valid=True,
                    mapping=mapping,
                    found_columns=list(df.columns),
                )
            else:
                validation = self._detect_column_mapping(list(df.columns))

            if not validation.valid:
                return CostProcessingResult(
                    document_id=document_id,
                    success=False,
                    total_rows=total_rows,
                    error_message=f"Colunas obrigatórias não encontradas: {', '.join(validation.missing_required)}",
                    processing_time_seconds=time.time() - start_time,
                )

            mapping = validation.mapping
            logger.info(
                "Mapeamento de colunas detectado",
                mapping=mapping.model_dump(),
            )

            # 3. Processar linhas
            records: list[CostRecord] = []
            row_errors: list[dict] = []
            total_charged = Decimal("0")
            total_paid = Decimal("0")
            date_min: Optional[date] = None
            date_max: Optional[date] = None

            for idx, row in df.iterrows():
                # Número da linha (1-indexed, +2 por causa do header)
                row_number = int(idx) + 2

                record, error = self._process_row(
                    row=row,
                    row_number=row_number,
                    mapping=mapping,
                    document_id=document_id,
                    client_id=client_id,
                    contract_id=contract_id,
                )

                if record:
                    records.append(record)
                    total_charged += record.charged_amount
                    total_paid += record.paid_amount

                    # Atualiza range de datas
                    if date_min is None or record.service_date < date_min:
                        date_min = record.service_date
                    if date_max is None or record.service_date > date_max:
                        date_max = record.service_date
                else:
                    row_errors.append(error)

            logger.info(
                "Processamento de linhas concluído",
                total_rows=total_rows,
                processed=len(records),
                errors=len(row_errors),
            )

            # 4. Armazenar registros no Cosmos DB (se habilitado)
            if store_records and records:
                await self._store_records(records, client_id)

            processing_time = time.time() - start_time

            return CostProcessingResult(
                document_id=document_id,
                success=True,
                total_rows=total_rows,
                processed_rows=len(records),
                skipped_rows=0,
                error_rows=len(row_errors),
                total_charged=total_charged,
                total_paid=total_paid,
                date_range_start=date_min,
                date_range_end=date_max,
                column_mapping=mapping,
                processing_time_seconds=processing_time,
                row_errors=row_errors[:100],  # Limita erros retornados
                records=records if len(records) <= 100 else None,
            )

        except Exception as e:
            logger.error("Erro no processamento", error=str(e))
            return CostProcessingResult(
                document_id=document_id,
                success=False,
                error_message=str(e),
                processing_time_seconds=time.time() - start_time,
            )

    async def _store_records(
        self,
        records: list[CostRecord],
        client_id: str,
    ) -> int:
        """
        Armazena registros de custos no Cosmos DB.

        Args:
            records: Lista de registros a armazenar
            client_id: ID do cliente

        Returns:
            Número de registros armazenados com sucesso
        """
        cosmos_client = get_cosmos_client()
        stored_count = 0

        # Processa em batches
        for i in range(0, len(records), self.BATCH_SIZE):
            batch = records[i : i + self.BATCH_SIZE]

            for record in batch:
                try:
                    await cosmos_client.create_cost_record(record)
                    stored_count += 1
                except Exception as e:
                    logger.warning(
                        "Erro ao armazenar registro",
                        record_id=str(record.id),
                        error=str(e),
                    )

            logger.debug(
                "Batch armazenado",
                batch_start=i,
                batch_size=len(batch),
                stored=stored_count,
            )

        logger.info(
            "Registros armazenados no Cosmos DB",
            total=len(records),
            stored=stored_count,
        )

        return stored_count


# Singleton
_processor: Optional[CostDataProcessor] = None


def get_cost_processor() -> CostDataProcessor:
    """Retorna instância singleton do processador."""
    global _processor
    if _processor is None:
        _processor = CostDataProcessor()
    return _processor
