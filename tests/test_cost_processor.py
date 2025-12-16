"""
Testes para o processador de dados de custos.

Testa:
- Leitura de CSV e Excel
- Detecção automática de colunas
- Normalização de dados (datas, valores, categorias)
- Validação de dados
"""

import pytest
from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pandas as pd

from src.ingestion.cost_processor import CostDataProcessor
from src.models.costs import (
    CostCategory,
    CostRecord,
    ColumnMapping,
    ColumnValidationResult,
)


class TestColumnDetection:
    """Testes de detecção automática de colunas."""

    def test_detect_standard_columns(self):
        """Detecta colunas com nomes padrão."""
        processor = CostDataProcessor()

        columns = [
            "data_atendimento",
            "descricao_procedimento",
            "valor_cobrado",
            "valor_pago",
            "codigo_beneficiario",
            "nome_prestador",
        ]

        result = processor._detect_column_mapping(columns)

        assert result.valid is True
        assert result.mapping is not None
        assert result.mapping.service_date == "data_atendimento"
        assert result.mapping.procedure_description == "descricao_procedimento"
        assert result.mapping.charged_amount == "valor_cobrado"
        assert result.mapping.paid_amount == "valor_pago"
        assert len(result.missing_required) == 0

    def test_detect_aliased_columns(self):
        """Detecta colunas com variações de nomes."""
        processor = CostDataProcessor()

        columns = [
            "dt_sinistro",      # alias de service_date
            "procedimento",      # alias de procedure_description
            "vl_apresentado",    # alias de charged_amount
            "vl_reembolsado",    # alias de paid_amount
        ]

        result = processor._detect_column_mapping(columns)

        assert result.valid is True
        assert result.mapping is not None
        assert result.mapping.service_date == "dt_sinistro"
        assert result.mapping.procedure_description == "procedimento"

    def test_missing_required_columns(self):
        """Falha quando colunas obrigatórias estão faltando."""
        processor = CostDataProcessor()

        columns = [
            "data_atendimento",
            "descricao_procedimento",
            # Faltando: valor_cobrado, valor_pago
        ]

        result = processor._detect_column_mapping(columns)

        assert result.valid is False
        assert "charged_amount" in result.missing_required
        assert "paid_amount" in result.missing_required

    def test_normalized_column_names(self):
        """Normaliza nomes com acentos e espaços."""
        processor = CostDataProcessor()

        # Testa normalização
        assert processor._normalize_column_name("Data Atendimento") == "data_atendimento"
        assert processor._normalize_column_name("Descrição") == "descricao"
        assert processor._normalize_column_name("VALOR_COBRADO") == "valor_cobrado"
        assert processor._normalize_column_name("código  procedimento") == "codigo_procedimento"


class TestDataParsing:
    """Testes de parsing de dados."""

    def test_parse_date_brazilian_format(self):
        """Parseia datas no formato brasileiro (DD/MM/YYYY)."""
        processor = CostDataProcessor()

        assert processor._parse_date("31/12/2024") == date(2024, 12, 31)
        assert processor._parse_date("01/01/2024") == date(2024, 1, 1)
        assert processor._parse_date("15/06/2023") == date(2023, 6, 15)

    def test_parse_date_iso_format(self):
        """Parseia datas no formato ISO (YYYY-MM-DD)."""
        processor = CostDataProcessor()

        assert processor._parse_date("2024-12-31") == date(2024, 12, 31)
        assert processor._parse_date("2024-01-01") == date(2024, 1, 1)

    def test_parse_date_invalid(self):
        """Retorna None para datas inválidas."""
        processor = CostDataProcessor()

        assert processor._parse_date(None) is None
        assert processor._parse_date("") is None
        assert processor._parse_date("invalid") is None
        assert processor._parse_date("32/13/2024") is None

    def test_parse_decimal_brazilian_format(self):
        """Parseia valores no formato brasileiro (1.234,56)."""
        processor = CostDataProcessor()

        assert processor._parse_decimal("1.234,56") == Decimal("1234.56")
        assert processor._parse_decimal("10.000,00") == Decimal("10000.00")
        assert processor._parse_decimal("R$ 150,00") == Decimal("150.00")

    def test_parse_decimal_american_format(self):
        """Parseia valores no formato americano (1,234.56)."""
        processor = CostDataProcessor()

        assert processor._parse_decimal("1,234.56") == Decimal("1234.56")
        assert processor._parse_decimal("10,000.00") == Decimal("10000.00")

    def test_parse_decimal_simple(self):
        """Parseia valores simples."""
        processor = CostDataProcessor()

        assert processor._parse_decimal(100) == Decimal("100")
        assert processor._parse_decimal(100.50) == Decimal("100.5")
        assert processor._parse_decimal("150") == Decimal("150")
        assert processor._parse_decimal("150,50") == Decimal("150.50")

    def test_parse_decimal_invalid(self):
        """Retorna None para valores inválidos."""
        processor = CostDataProcessor()

        assert processor._parse_decimal(None) is None
        assert processor._parse_decimal("") is None
        assert processor._parse_decimal("abc") is None


class TestCategoryClassification:
    """Testes de classificação de categorias."""

    def test_classify_consulta(self):
        """Classifica como consulta."""
        processor = CostDataProcessor()

        assert processor._classify_category("Consulta médica") == CostCategory.CONSULTA
        assert processor._classify_category("CONSULTA ESPECIALISTA") == CostCategory.CONSULTA

    def test_classify_exame(self):
        """Classifica como exame."""
        processor = CostDataProcessor()

        assert processor._classify_category("Exame de sangue") == CostCategory.EXAME
        assert processor._classify_category("Hemograma completo") == CostCategory.EXAME
        assert processor._classify_category("Ultrassom abdominal") == CostCategory.EXAME
        assert processor._classify_category("Raio-X torax") == CostCategory.EXAME
        assert processor._classify_category("Tomografia") == CostCategory.EXAME

    def test_classify_internacao(self):
        """Classifica como internação."""
        processor = CostDataProcessor()

        assert processor._classify_category("Diária hospitalar") == CostCategory.INTERNACAO
        assert processor._classify_category("Internação UTI") == CostCategory.INTERNACAO
        assert processor._classify_category("Leito enfermaria") == CostCategory.INTERNACAO

    def test_classify_pronto_socorro(self):
        """Classifica como pronto socorro."""
        processor = CostDataProcessor()

        assert processor._classify_category("Atendimento pronto socorro") == CostCategory.PRONTO_SOCORRO
        assert processor._classify_category("Urgência") == CostCategory.PRONTO_SOCORRO
        assert processor._classify_category("PS - Emergência") == CostCategory.PRONTO_SOCORRO

    def test_classify_procedimento(self):
        """Classifica como procedimento."""
        processor = CostDataProcessor()

        assert processor._classify_category("Cirurgia cardíaca") == CostCategory.PROCEDIMENTO
        assert processor._classify_category("Endoscopia digestiva") == CostCategory.PROCEDIMENTO

    def test_classify_terapia(self):
        """Classifica como terapia."""
        processor = CostDataProcessor()

        assert processor._classify_category("Sessão fisioterapia") == CostCategory.TERAPIA
        assert processor._classify_category("Fonoaudiologia") == CostCategory.TERAPIA
        assert processor._classify_category("Sessão psicologia") == CostCategory.TERAPIA

    def test_classify_outros(self):
        """Classifica como outros quando não reconhece."""
        processor = CostDataProcessor()

        assert processor._classify_category("Serviço não identificado") == CostCategory.OUTROS
        assert processor._classify_category("XYZ123") == CostCategory.OUTROS

    def test_classify_from_explicit_category(self):
        """Usa categoria explícita quando fornecida."""
        processor = CostDataProcessor()

        assert processor._classify_category("Qualquer descrição", "consulta") == CostCategory.CONSULTA
        assert processor._classify_category("Qualquer coisa", "exame") == CostCategory.EXAME


class TestCSVProcessing:
    """Testes de processamento de arquivos CSV."""

    def create_csv_bytes(self, data: list[dict]) -> bytes:
        """Helper para criar bytes de CSV."""
        df = pd.DataFrame(data)
        return df.to_csv(index=False).encode("utf-8")

    @pytest.mark.asyncio
    async def test_process_valid_csv(self):
        """Processa CSV válido com sucesso."""
        data = [
            {
                "data_atendimento": "15/06/2024",
                "descricao_procedimento": "Consulta médica geral",
                "valor_cobrado": "150,00",
                "valor_pago": "120,00",
                "codigo_beneficiario": "BEN001",
                "nome_prestador": "Clínica ABC",
            },
            {
                "data_atendimento": "20/06/2024",
                "descricao_procedimento": "Exame de sangue",
                "valor_cobrado": "80,00",
                "valor_pago": "80,00",
                "codigo_beneficiario": "BEN001",
                "nome_prestador": "Lab XYZ",
            },
        ]

        processor = CostDataProcessor()
        result = await processor.process_bytes(
            file_bytes=self.create_csv_bytes(data),
            filename="custos.csv",
            document_id=uuid4(),
            client_id="cliente-teste",
            store_records=False,  # Não armazena no Cosmos DB
        )

        assert result.success is True
        assert result.total_rows == 2
        assert result.processed_rows == 2
        assert result.error_rows == 0
        assert result.total_charged == Decimal("230.00")
        assert result.total_paid == Decimal("200.00")
        assert result.date_range_start == date(2024, 6, 15)
        assert result.date_range_end == date(2024, 6, 20)

    @pytest.mark.asyncio
    async def test_process_csv_with_errors(self):
        """Processa CSV com algumas linhas inválidas."""
        data = [
            {
                "data_atendimento": "15/06/2024",
                "descricao_procedimento": "Consulta médica",
                "valor_cobrado": "150,00",
                "valor_pago": "120,00",
            },
            {
                "data_atendimento": "data_invalida",  # Data inválida
                "descricao_procedimento": "Exame",
                "valor_cobrado": "80,00",
                "valor_pago": "80,00",
            },
            {
                "data_atendimento": "20/06/2024",
                "descricao_procedimento": "",  # Descrição vazia
                "valor_cobrado": "50,00",
                "valor_pago": "50,00",
            },
        ]

        processor = CostDataProcessor()
        result = await processor.process_bytes(
            file_bytes=self.create_csv_bytes(data),
            filename="custos.csv",
            document_id=uuid4(),
            client_id="cliente-teste",
            store_records=False,
        )

        assert result.success is True
        assert result.total_rows == 3
        assert result.processed_rows == 1  # Apenas a primeira linha é válida
        assert result.error_rows == 2

    @pytest.mark.asyncio
    async def test_process_csv_missing_columns(self):
        """Falha quando colunas obrigatórias não existem."""
        data = [
            {
                "data": "15/06/2024",  # Nome não reconhecido
                "descricao": "Consulta",  # Nome não reconhecido
            },
        ]

        processor = CostDataProcessor()
        result = await processor.process_bytes(
            file_bytes=self.create_csv_bytes(data),
            filename="custos.csv",
            document_id=uuid4(),
            client_id="cliente-teste",
            store_records=False,
        )

        assert result.success is False
        assert "obrigatórias não encontradas" in result.error_message

    @pytest.mark.asyncio
    async def test_process_empty_csv(self):
        """Falha para arquivo CSV vazio."""
        df = pd.DataFrame(columns=["data_atendimento", "descricao_procedimento", "valor_cobrado", "valor_pago"])

        processor = CostDataProcessor()
        result = await processor.process_bytes(
            file_bytes=df.to_csv(index=False).encode("utf-8"),
            filename="custos.csv",
            document_id=uuid4(),
            client_id="cliente-teste",
            store_records=False,
        )

        assert result.success is False
        assert "vazio" in result.error_message.lower()


class TestExcelProcessing:
    """Testes de processamento de arquivos Excel."""

    def create_xlsx_bytes(self, data: list[dict]) -> bytes:
        """Helper para criar bytes de Excel."""
        df = pd.DataFrame(data)
        output = BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")
        return output.getvalue()

    @pytest.mark.asyncio
    async def test_process_valid_xlsx(self):
        """Processa Excel válido com sucesso."""
        data = [
            {
                "data_atendimento": "15/06/2024",
                "descricao_procedimento": "Consulta médica",
                "valor_cobrado": 150.00,
                "valor_pago": 120.00,
            },
            {
                "data_atendimento": "20/06/2024",
                "descricao_procedimento": "Fisioterapia",
                "valor_cobrado": 100.00,
                "valor_pago": 100.00,
            },
        ]

        processor = CostDataProcessor()
        result = await processor.process_bytes(
            file_bytes=self.create_xlsx_bytes(data),
            filename="custos.xlsx",
            document_id=uuid4(),
            client_id="cliente-teste",
            store_records=False,
        )

        assert result.success is True
        assert result.total_rows == 2
        assert result.processed_rows == 2


class TestCostRecordModel:
    """Testes do modelo CostRecord."""

    def test_cpf_validation(self):
        """CPF é normalizado (remove formatação)."""
        record = CostRecord(
            document_id=uuid4(),
            client_id="cliente",
            source_row_number=1,
            service_date=date(2024, 6, 15),
            procedure_description="Consulta",
            charged_amount=Decimal("100"),
            paid_amount=Decimal("80"),
            beneficiary_cpf="123.456.789-00",
        )

        assert record.beneficiary_cpf == "12345678900"

    def test_codes_cleaned(self):
        """Códigos têm espaços removidos."""
        record = CostRecord(
            document_id=uuid4(),
            client_id="cliente",
            source_row_number=1,
            service_date=date(2024, 6, 15),
            procedure_description="Consulta",
            charged_amount=Decimal("100"),
            paid_amount=Decimal("80"),
            procedure_code="  10101012  ",
            provider_code="  PROV001  ",
        )

        assert record.procedure_code == "10101012"
        assert record.provider_code == "PROV001"

    def test_empty_codes_become_none(self):
        """Códigos vazios se tornam None."""
        record = CostRecord(
            document_id=uuid4(),
            client_id="cliente",
            source_row_number=1,
            service_date=date(2024, 6, 15),
            procedure_description="Consulta",
            charged_amount=Decimal("100"),
            paid_amount=Decimal("80"),
            procedure_code="   ",
            provider_code="",
        )

        assert record.procedure_code is None
        assert record.provider_code is None


class TestCustomColumnMapping:
    """Testes com mapeamento customizado de colunas."""

    @pytest.mark.asyncio
    async def test_custom_mapping(self):
        """Usa mapeamento customizado fornecido."""
        data = [
            {
                "dt_servico": "15/06/2024",
                "servico": "Consulta médica",
                "vl_total": "150,00",
                "vl_autorizado": "120,00",
            },
        ]

        custom_mapping = ColumnMapping(
            service_date="dt_servico",
            procedure_description="servico",
            charged_amount="vl_total",
            paid_amount="vl_autorizado",
        )

        processor = CostDataProcessor(custom_mapping=custom_mapping)
        df = pd.DataFrame(data)
        csv_bytes = df.to_csv(index=False).encode("utf-8")

        result = await processor.process_bytes(
            file_bytes=csv_bytes,
            filename="custos.csv",
            document_id=uuid4(),
            client_id="cliente-teste",
            store_records=False,
        )

        assert result.success is True
        assert result.processed_rows == 1
