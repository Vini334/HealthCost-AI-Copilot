"""
Modelos Pydantic para dados de custos de saúde.

Estes modelos definem a estrutura dos dados para:
- Registros de custos/sinistros
- Validação de colunas obrigatórias
- Normalização de dados
- Resultados de processamento
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class CostCategory(str, Enum):
    """
    Categorias de custos de saúde.

    Classificação padrão para análise e agregação.
    """
    CONSULTA = "consulta"
    EXAME = "exame"
    PROCEDIMENTO = "procedimento"
    INTERNACAO = "internacao"
    PRONTO_SOCORRO = "pronto_socorro"
    TERAPIA = "terapia"
    MEDICAMENTO = "medicamento"
    MATERIAL = "material"
    OUTROS = "outros"


class UtilizationType(str, Enum):
    """
    Tipo de utilização do serviço de saúde.
    """
    AMBULATORIAL = "ambulatorial"
    HOSPITALAR = "hospitalar"
    ODONTOLOGICO = "odontologico"
    DOMICILIAR = "domiciliar"


# ============================================================
# Modelos para Registros de Custos
# ============================================================

class CostRecord(BaseModel):
    """
    Registro individual de custo/sinistro.

    Representa uma linha do arquivo de custos após normalização.
    Este modelo é armazenado no Cosmos DB para consultas e análises.
    """

    # Identificadores
    id: UUID = Field(default_factory=uuid4, description="ID único do registro")
    document_id: UUID = Field(..., description="ID do documento de origem")
    client_id: str = Field(..., description="ID do cliente (multi-tenancy)")
    contract_id: Optional[str] = Field(None, description="ID do contrato relacionado")

    # Linha de origem (para rastreabilidade)
    source_row_number: int = Field(..., ge=1, description="Número da linha no arquivo original")

    # Dados do beneficiário
    beneficiary_id: Optional[str] = Field(None, description="Código/ID do beneficiário")
    beneficiary_name: Optional[str] = Field(None, description="Nome do beneficiário")
    beneficiary_cpf: Optional[str] = Field(None, description="CPF do beneficiário")

    # Dados do atendimento
    service_date: date = Field(..., description="Data do atendimento/sinistro")
    procedure_code: Optional[str] = Field(None, description="Código do procedimento (TUSS)")
    procedure_description: str = Field(..., description="Descrição do procedimento")

    # Dados do prestador
    provider_code: Optional[str] = Field(None, description="Código do prestador")
    provider_name: Optional[str] = Field(None, description="Nome do prestador")

    # Valores
    charged_amount: Decimal = Field(..., ge=0, description="Valor cobrado")
    paid_amount: Decimal = Field(..., ge=0, description="Valor pago")

    # Classificação
    category: CostCategory = Field(
        default=CostCategory.OUTROS,
        description="Categoria do custo"
    )
    utilization_type: Optional[UtilizationType] = Field(
        None,
        description="Tipo de utilização"
    )

    # Metadados
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Data de criação do registro"
    )

    # Campos extras/customizados (para dados específicos do cliente)
    extra_data: Optional[dict] = Field(
        None,
        description="Dados adicionais do registro"
    )

    @field_validator("beneficiary_cpf")
    @classmethod
    def validate_cpf(cls, v: Optional[str]) -> Optional[str]:
        """Remove formatação do CPF."""
        if v is None:
            return None
        # Remove pontos, traços e espaços
        cpf = "".join(c for c in v if c.isdigit())
        return cpf if cpf else None

    @field_validator("procedure_code", "provider_code")
    @classmethod
    def clean_code(cls, v: Optional[str]) -> Optional[str]:
        """Remove espaços extras de códigos."""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    class Config:
        """Configuração do modelo."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v),
        }


# ============================================================
# Modelos para Validação de Colunas
# ============================================================

class ColumnMapping(BaseModel):
    """
    Mapeamento de colunas do arquivo para os campos do modelo.

    Permite flexibilidade para diferentes formatos de arquivo.
    """

    # Colunas obrigatórias
    service_date: str = Field(..., description="Nome da coluna de data do atendimento")
    procedure_description: str = Field(..., description="Nome da coluna de descrição")
    charged_amount: str = Field(..., description="Nome da coluna de valor cobrado")
    paid_amount: str = Field(..., description="Nome da coluna de valor pago")

    # Colunas opcionais (podem não existir no arquivo)
    beneficiary_id: Optional[str] = Field(None, description="Coluna de ID do beneficiário")
    beneficiary_name: Optional[str] = Field(None, description="Coluna de nome do beneficiário")
    beneficiary_cpf: Optional[str] = Field(None, description="Coluna de CPF")
    procedure_code: Optional[str] = Field(None, description="Coluna de código do procedimento")
    provider_code: Optional[str] = Field(None, description="Coluna de código do prestador")
    provider_name: Optional[str] = Field(None, description="Coluna de nome do prestador")
    category: Optional[str] = Field(None, description="Coluna de categoria")
    utilization_type: Optional[str] = Field(None, description="Coluna de tipo de utilização")


# Mapeamentos pré-definidos para formatos comuns
DEFAULT_COLUMN_MAPPING = ColumnMapping(
    service_date="data_atendimento",
    procedure_description="descricao_procedimento",
    charged_amount="valor_cobrado",
    paid_amount="valor_pago",
    beneficiary_id="codigo_beneficiario",
    beneficiary_name="nome_beneficiario",
    beneficiary_cpf="cpf",
    procedure_code="codigo_procedimento",
    provider_code="codigo_prestador",
    provider_name="nome_prestador",
    category="categoria",
    utilization_type="tipo_utilizacao",
)

# Variações comuns de nomes de colunas (para detecção automática)
COLUMN_ALIASES = {
    "service_date": [
        "data_atendimento", "data", "dt_atendimento", "data_servico",
        "dt_sinistro", "data_sinistro", "data_evento",
    ],
    "procedure_description": [
        "descricao_procedimento", "descricao", "procedimento",
        "desc_procedimento", "servico", "descricao_servico",
    ],
    "charged_amount": [
        "valor_cobrado", "vl_cobrado", "valor_apresentado",
        "vl_apresentado", "valor_total", "valor",
    ],
    "paid_amount": [
        "valor_pago", "vl_pago", "valor_reembolsado",
        "vl_reembolsado", "valor_liberado",
    ],
    "beneficiary_id": [
        "codigo_beneficiario", "cd_beneficiario", "matricula",
        "carteirinha", "nr_carteira", "id_beneficiario",
    ],
    "beneficiary_name": [
        "nome_beneficiario", "nm_beneficiario", "beneficiario", "nome",
    ],
    "beneficiary_cpf": [
        "cpf", "cpf_beneficiario", "nr_cpf", "documento",
    ],
    "procedure_code": [
        "codigo_procedimento", "cd_procedimento", "codigo_tuss",
        "tuss", "cod_procedimento",
    ],
    "provider_code": [
        "codigo_prestador", "cd_prestador", "cnpj_prestador",
        "cod_prestador",
    ],
    "provider_name": [
        "nome_prestador", "nm_prestador", "prestador",
        "razao_social_prestador",
    ],
    "category": [
        "categoria", "tipo_servico", "tipo", "classificacao",
    ],
    "utilization_type": [
        "tipo_utilizacao", "regime", "tipo_atendimento",
        "natureza_atendimento",
    ],
}


class ColumnValidationResult(BaseModel):
    """
    Resultado da validação de colunas do arquivo.
    """

    valid: bool = Field(..., description="Se as colunas obrigatórias foram encontradas")
    mapping: Optional[ColumnMapping] = Field(None, description="Mapeamento detectado")
    found_columns: list[str] = Field(default_factory=list, description="Colunas encontradas")
    missing_required: list[str] = Field(default_factory=list, description="Colunas obrigatórias faltando")
    unrecognized: list[str] = Field(default_factory=list, description="Colunas não reconhecidas")
    warnings: list[str] = Field(default_factory=list, description="Avisos")


# ============================================================
# Modelos para Resultado do Processamento
# ============================================================

class CostProcessingResult(BaseModel):
    """
    Resultado do processamento de um arquivo de custos.
    """

    document_id: UUID = Field(..., description="ID do documento processado")
    success: bool = Field(..., description="Se o processamento foi bem-sucedido")

    # Estatísticas
    total_rows: int = Field(default=0, description="Total de linhas no arquivo")
    processed_rows: int = Field(default=0, description="Linhas processadas com sucesso")
    skipped_rows: int = Field(default=0, description="Linhas ignoradas (header, vazias)")
    error_rows: int = Field(default=0, description="Linhas com erro")

    # Valores agregados
    total_charged: Optional[Decimal] = Field(None, description="Soma dos valores cobrados")
    total_paid: Optional[Decimal] = Field(None, description="Soma dos valores pagos")

    # Período dos dados
    date_range_start: Optional[date] = Field(None, description="Data mais antiga")
    date_range_end: Optional[date] = Field(None, description="Data mais recente")

    # Detalhes
    column_mapping: Optional[ColumnMapping] = Field(None, description="Mapeamento utilizado")
    processing_time_seconds: Optional[float] = Field(None, description="Tempo de processamento")
    error_message: Optional[str] = Field(None, description="Mensagem de erro")
    row_errors: list[dict] = Field(default_factory=list, description="Erros por linha")

    # Registros criados (opcional, pode ser omitido para arquivos grandes)
    records: Optional[list[CostRecord]] = Field(None, description="Registros criados")

    class Config:
        """Configuração do modelo."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v),
        }


# ============================================================
# Modelos para Agregações e Análises
# ============================================================

class CostSummaryByCategory(BaseModel):
    """
    Resumo de custos por categoria.
    """
    category: CostCategory
    total_records: int
    total_charged: Decimal
    total_paid: Decimal
    avg_charged: Decimal
    avg_paid: Decimal


class CostSummaryByPeriod(BaseModel):
    """
    Resumo de custos por período (mensal).
    """
    year: int
    month: int
    total_records: int
    total_charged: Decimal
    total_paid: Decimal


class CostSummary(BaseModel):
    """
    Resumo geral dos custos de um cliente.
    """
    client_id: str
    contract_id: Optional[str] = None

    # Totais
    total_records: int
    total_charged: Decimal
    total_paid: Decimal

    # Período
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None

    # Agregações
    by_category: list[CostSummaryByCategory] = Field(default_factory=list)
    by_period: list[CostSummaryByPeriod] = Field(default_factory=list)

    # Top procedimentos
    top_procedures: list[dict] = Field(default_factory=list)

    # Top prestadores
    top_providers: list[dict] = Field(default_factory=list)
