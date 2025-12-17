"""
Testes para o CostInsightsAgent e ferramentas de custos.

Testa:
- Ferramentas de análise de custos
- CostInsightsAgent (análise pré-carregada e guiada por LLM)
- Geração de insights
"""

import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
)
from src.agents.tools import ToolRegistry
from src.agents.cost_tools import (
    CostSummaryTool,
    CostByCategoryTool,
    CostByPeriodTool,
    TopProceduresTool,
    TopProvidersTool,
    ComparePeriodsTool,
    register_cost_tools,
)
from src.agents.cost_insights_agent import (
    CostInsightsAgent,
    create_cost_insights_agent,
)


# ============================================
# Mock Data e Fixtures
# ============================================


def create_mock_summary() -> Dict[str, Any]:
    """Cria dados mock de resumo de custos."""
    return {
        "total_records": 1500,
        "total_charged": 250000.00,
        "total_paid": 200000.00,
        "date_start": "2024-01-01",
        "date_end": "2024-06-30",
    }


def create_mock_categories() -> List[Dict[str, Any]]:
    """Cria dados mock de custos por categoria."""
    return [
        {"category": "consulta", "total_records": 500, "total_charged": 50000, "total_paid": 40000},
        {"category": "exame", "total_records": 400, "total_charged": 80000, "total_paid": 70000},
        {"category": "internacao", "total_records": 50, "total_charged": 100000, "total_paid": 80000},
        {"category": "procedimento", "total_records": 100, "total_charged": 20000, "total_paid": 10000},
    ]


def create_mock_periods() -> List[Dict[str, Any]]:
    """Cria dados mock de custos por período."""
    return [
        {"month": "2024-01", "total_records": 200, "total_charged": 40000, "total_paid": 32000},
        {"month": "2024-02", "total_records": 220, "total_charged": 42000, "total_paid": 34000},
        {"month": "2024-03", "total_records": 250, "total_charged": 45000, "total_paid": 36000},
        {"month": "2024-04", "total_records": 230, "total_charged": 41000, "total_paid": 33000},
        {"month": "2024-05", "total_records": 280, "total_charged": 48000, "total_paid": 38000},
        {"month": "2024-06", "total_records": 320, "total_charged": 54000, "total_paid": 43000},
    ]


def create_mock_procedures() -> List[Dict[str, Any]]:
    """Cria dados mock de top procedimentos."""
    return [
        {"procedure_description": "Consulta médica", "procedure_code": "10101012", "occurrences": 300, "total_charged": 30000, "total_paid": 24000, "avg_paid": 80},
        {"procedure_description": "Hemograma completo", "procedure_code": "40304361", "occurrences": 200, "total_charged": 10000, "total_paid": 8000, "avg_paid": 40},
        {"procedure_description": "Ultrassonografia", "procedure_code": "40901030", "occurrences": 100, "total_charged": 25000, "total_paid": 20000, "avg_paid": 200},
    ]


def create_mock_providers() -> List[Dict[str, Any]]:
    """Cria dados mock de top prestadores."""
    return [
        {"provider_name": "Hospital ABC", "provider_code": "001", "total_records": 400, "total_charged": 100000, "total_paid": 80000},
        {"provider_name": "Laboratório XYZ", "provider_code": "002", "total_records": 300, "total_charged": 30000, "total_paid": 25000},
        {"provider_name": "Clínica 123", "provider_code": "003", "total_records": 200, "total_charged": 20000, "total_paid": 16000},
    ]


@pytest.fixture
def mock_cosmos_client():
    """Fixture que fornece um CosmosDBClient mockado."""
    mock = MagicMock()

    # Mock para get_cost_summary
    mock.get_cost_summary = AsyncMock(return_value=create_mock_summary())

    # Mock para get_cost_by_category
    mock.get_cost_by_category = AsyncMock(return_value=create_mock_categories())

    # Mock para container com query_items
    mock_container = MagicMock()
    mock._get_costs_container = MagicMock(return_value=mock_container)

    return mock


@pytest.fixture
def mock_llm_response():
    """Fixture que fornece uma resposta mock do LLM."""
    return {
        "content": """Com base nos dados analisados, apresento os principais insights:

**Resumo Geral:**
- Total de registros: 1.500 atendimentos
- Valor total pago: R$ 200.000,00
- Período: Janeiro a Junho de 2024

**Principais Custos por Categoria:**
1. Internação: R$ 80.000,00 (40% do total)
2. Exames: R$ 70.000,00 (35% do total)
3. Consultas: R$ 40.000,00 (20% do total)

**Tendência:**
Os custos apresentam tendência de alta nos últimos 3 meses.""",
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "total_tokens": 700,
        },
    }


@pytest.fixture
def mock_openai_client(mock_llm_response):
    """Fixture que fornece um cliente OpenAI mockado."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = mock_llm_response["content"]
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage = MagicMock()
    mock_response.usage.model_dump.return_value = mock_llm_response["usage"]

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


# ============================================
# Testes de Ferramentas de Custos
# ============================================


class TestCostSummaryTool:
    """Testes para CostSummaryTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = CostSummaryTool()

        assert tool.name == "get_cost_summary"
        assert "resumo" in tool.description.lower()

    def test_get_parameters(self):
        """Testa parâmetros da ferramenta."""
        tool = CostSummaryTool()
        params = tool.get_parameters()

        param_names = [p.name for p in params]
        assert "client_id" in param_names
        assert "contract_id" in param_names

    @pytest.mark.asyncio
    async def test_execute(self, mock_cosmos_client):
        """Testa execução da ferramenta."""
        tool = CostSummaryTool(cosmos_client=mock_cosmos_client)

        result = await tool.execute(client_id="cliente-123")

        assert "total_records" in result
        assert "total_charged" in result
        assert "total_paid" in result
        assert result["total_records"] == 1500


class TestCostByCategoryTool:
    """Testes para CostByCategoryTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = CostByCategoryTool()

        assert tool.name == "get_cost_by_category"
        assert "categoria" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute(self, mock_cosmos_client):
        """Testa execução da ferramenta."""
        tool = CostByCategoryTool(cosmos_client=mock_cosmos_client)

        result = await tool.execute(client_id="cliente-123")

        assert "categories" in result
        assert len(result["categories"]) == 4
        # Verifica que está ordenado por valor
        assert result["categories"][0]["total_paid"] >= result["categories"][1]["total_paid"]


class TestCostByPeriodTool:
    """Testes para CostByPeriodTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = CostByPeriodTool()

        assert tool.name == "get_cost_by_period"
        assert "evolução" in tool.description.lower() or "período" in tool.description.lower()

    def test_get_parameters(self):
        """Testa parâmetros da ferramenta."""
        tool = CostByPeriodTool()
        params = tool.get_parameters()

        param_names = [p.name for p in params]
        assert "start_date" in param_names
        assert "end_date" in param_names


class TestTopProceduresTool:
    """Testes para TopProceduresTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = TopProceduresTool()

        assert tool.name == "get_top_procedures"
        assert "procedimento" in tool.description.lower()

    def test_get_parameters(self):
        """Testa parâmetros da ferramenta."""
        tool = TopProceduresTool()
        params = tool.get_parameters()

        param_names = [p.name for p in params]
        assert "top" in param_names
        assert "category" in param_names


class TestTopProvidersTool:
    """Testes para TopProvidersTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = TopProvidersTool()

        assert tool.name == "get_top_providers"
        assert "prestador" in tool.description.lower()


class TestComparePeriodsTool:
    """Testes para ComparePeriodsTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = ComparePeriodsTool()

        assert tool.name == "compare_periods"
        assert "compar" in tool.description.lower()

    def test_get_parameters(self):
        """Testa parâmetros da ferramenta."""
        tool = ComparePeriodsTool()
        params = tool.get_parameters()

        param_names = [p.name for p in params]
        assert "period1_start" in param_names
        assert "period1_end" in param_names
        assert "period2_start" in param_names
        assert "period2_end" in param_names


class TestRegisterCostTools:
    """Testes para register_cost_tools."""

    def test_register_all_tools(self):
        """Testa registro de todas as ferramentas."""
        registry = ToolRegistry()

        with patch("src.agents.cost_tools.get_cosmos_client"):
            register_cost_tools(registry)

        tools = registry.list_tools()

        assert "get_cost_summary" in tools
        assert "get_cost_by_category" in tools
        assert "get_cost_by_period" in tools
        assert "get_top_procedures" in tools
        assert "get_top_providers" in tools
        assert "compare_periods" in tools


# ============================================
# Testes do CostInsightsAgent
# ============================================


class TestCostInsightsAgent:
    """Testes para CostInsightsAgent."""

    def test_agent_properties(self):
        """Testa propriedades do agente."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)

            assert agent.agent_type == AgentType.COST_INSIGHTS
            assert agent.agent_name == "cost_insights_agent"
            assert agent.temperature == 0.2

    def test_get_tools(self):
        """Testa ferramentas disponíveis."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)
            tools = agent.get_tools()

            assert "get_cost_summary" in tools
            assert "get_cost_by_category" in tools
            assert "get_top_procedures" in tools

    def test_system_prompt_contains_key_elements(self):
        """Testa que o system prompt contém elementos importantes."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)

            assert "custos" in agent.system_prompt.lower()
            assert "sinistralidade" in agent.system_prompt.lower()
            assert "tendência" in agent.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_process_with_preloaded_data(self, mock_openai_client):
        """Testa processamento com dados pré-carregados."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)
            agent._client = mock_openai_client

            cost_data = {
                "summary": {
                    "total_records": 1500,
                    "total_charged": 250000,
                    "total_paid": 200000,
                    "date_range": {"start": "2024-01-01", "end": "2024-06-30"},
                },
            }

            context = AgentContext(
                client_id="cliente-123",
                query="Qual o resumo dos custos?",
                cost_data=cost_data,
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert result.response is not None
            assert result.structured_output is not None

    @pytest.mark.asyncio
    async def test_process_with_metadata_cost_data(self, mock_openai_client):
        """Testa processamento com dados em metadata."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)
            agent._client = mock_openai_client

            cost_data = {
                "by_category": {
                    "categories": [
                        {"category": "internacao", "total_paid": 80000, "percentage": 40},
                        {"category": "exame", "total_paid": 70000, "percentage": 35},
                    ],
                },
            }

            context = AgentContext(
                client_id="cliente-123",
                query="Quais as categorias com maiores custos?",
                metadata={"cost_data": cost_data},
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED


class TestCostInsightsBuildPrompt:
    """Testes para construção de prompts."""

    def test_build_analysis_prompt_with_summary(self):
        """Testa construção do prompt com resumo."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)

            cost_data = {
                "summary": {
                    "total_records": 1500,
                    "total_charged": 250000,
                    "total_paid": 200000,
                    "date_range": {"start": "2024-01-01", "end": "2024-06-30"},
                },
            }

            prompt = agent._build_analysis_prompt(
                query="Qual o total de custos?",
                cost_data=cost_data,
            )

            assert "RESUMO GERAL" in prompt
            assert "1,500" in prompt or "1500" in prompt
            assert "200" in prompt

    def test_build_analysis_prompt_with_categories(self):
        """Testa construção do prompt com categorias."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)

            cost_data = {
                "by_category": {
                    "categories": [
                        {"category": "internacao", "total_paid": 80000, "percentage": 40.0},
                        {"category": "exame", "total_paid": 70000, "percentage": 35.0},
                    ],
                },
            }

            prompt = agent._build_analysis_prompt(
                query="Distribuição por categoria",
                cost_data=cost_data,
            )

            assert "CATEGORIA" in prompt
            assert "internacao" in prompt
            assert "40" in prompt


class TestCostInsightsGenerateInsights:
    """Testes para geração de insights."""

    def test_generate_insights_high_concentration_category(self):
        """Testa insight de categoria dominante."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)

            analysis = {
                "by_category": {
                    "categories": [
                        {"category": "internacao", "percentage": 55.0},
                        {"category": "exame", "percentage": 25.0},
                    ],
                },
            }

            insights = agent._generate_insights(analysis)

            assert len(insights) >= 1
            assert any("internacao" in i.lower() for i in insights)
            assert any("55" in i for i in insights)

    def test_generate_insights_upward_trend(self):
        """Testa insight de tendência de alta."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)

            analysis = {
                "by_period": {
                    "periods": [
                        {"month": "2024-01", "variation_percent": None},
                        {"month": "2024-02", "variation_percent": 15.0},
                        {"month": "2024-03", "variation_percent": 12.0},
                        {"month": "2024-04", "variation_percent": 18.0},
                    ],
                },
            }

            insights = agent._generate_insights(analysis)

            assert any("alta" in i.lower() for i in insights)

    def test_generate_insights_provider_concentration(self):
        """Testa insight de concentração em prestadores."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)

            analysis = {
                "top_providers": {
                    "providers": [
                        {"provider_name": "Hospital A", "percentage": 30.0},
                        {"provider_name": "Hospital B", "percentage": 20.0},
                        {"provider_name": "Clínica C", "percentage": 15.0},
                    ],
                },
            }

            insights = agent._generate_insights(analysis)

            assert any("prestador" in i.lower() or "concentra" in i.lower() for i in insights)


class TestCreateCostInsightsAgent:
    """Testes para factory function."""

    def test_create_agent(self):
        """Testa criação via factory."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = create_cost_insights_agent()

            assert isinstance(agent, CostInsightsAgent)
            assert agent.agent_type == AgentType.COST_INSIGHTS


class TestCostInsightsIntegration:
    """Testes de integração."""

    @pytest.mark.asyncio
    async def test_full_analysis_flow(self, mock_openai_client):
        """Testa fluxo completo de análise."""
        with patch("src.agents.cost_tools.get_cosmos_client"):
            agent = CostInsightsAgent(auto_register_tools=False)
            agent._client = mock_openai_client

            cost_data = {
                "summary": {
                    "total_records": 1500,
                    "total_charged": 250000,
                    "total_paid": 200000,
                    "date_range": {"start": "2024-01-01", "end": "2024-06-30"},
                },
                "by_category": {
                    "categories": [
                        {"category": "internacao", "total_paid": 80000, "percentage": 40.0},
                    ],
                },
            }

            result = await agent.execute(
                query="Faça uma análise completa dos custos",
                client_id="cliente-123",
                metadata={"cost_data": cost_data},
            )

            assert result.status == AgentStatus.COMPLETED
            assert result.response is not None
            assert result.agent_type == AgentType.COST_INSIGHTS

    @pytest.mark.asyncio
    async def test_execution_tracking(self, mock_openai_client):
        """Testa rastreamento de execução."""
        from src.agents.execution_logger import ExecutionTracker

        with patch("src.agents.cost_tools.get_cosmos_client"):
            tracker = ExecutionTracker()
            agent = CostInsightsAgent(
                execution_tracker=tracker,
                auto_register_tools=False,
            )
            agent._client = mock_openai_client

            cost_data = {"summary": {"total_records": 100, "total_paid": 10000}}

            result = await agent.execute(
                query="Teste",
                client_id="cliente-123",
                metadata={"cost_data": cost_data},
            )

            tracked = tracker.get(result.execution_id)
            assert tracked is not None
            assert tracked.agent_type == AgentType.COST_INSIGHTS
