"""
Testes para o NegotiationAdvisorAgent e ferramentas de negociação.

Testa:
- Ferramentas de análise de renegociação
- NegotiationAdvisorAgent (análise completa e guiada por LLM)
- Identificação de oportunidades e priorização
- Estimativas de economia
"""

import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
)
from src.agents.tools import ToolRegistry
from src.agents.negotiation_tools import (
    IdentifyRenegotiationOpportunitiesTool,
    EstimateSavingsTool,
    PrioritizeNegotiationPointsTool,
    GenerateNegotiationReportTool,
    register_negotiation_tools,
    MARKET_BENCHMARKS,
)
from src.agents.negotiation_advisor_agent import (
    NegotiationAdvisorAgent,
    create_negotiation_advisor_agent,
)


# ============================================
# Mock Data e Fixtures
# ============================================


def create_mock_cost_data() -> Dict[str, Any]:
    """Cria dados mock de custos completos."""
    return {
        "summary": {
            "total_records": 1500,
            "total_charged": 250000.00,
            "total_paid": 200000.00,
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
        },
        "total_paid": 200000.00,
        "total_charged": 250000.00,
        "by_category": {
            "categories": [
                {"category": "internacao", "total_paid": 80000, "percentage": 40.0},
                {"category": "exame", "total_paid": 60000, "percentage": 30.0},
                {"category": "consulta", "total_paid": 40000, "percentage": 20.0},
                {"category": "procedimento", "total_paid": 20000, "percentage": 10.0},
            ],
        },
        "by_period": {
            "periods": [
                {"month": "2024-01", "total_paid": 15000, "variation_percent": None},
                {"month": "2024-02", "total_paid": 16000, "variation_percent": 6.7},
                {"month": "2024-03", "total_paid": 17500, "variation_percent": 9.4},
                {"month": "2024-04", "total_paid": 19000, "variation_percent": 8.6},
                {"month": "2024-05", "total_paid": 22000, "variation_percent": 15.8},
                {"month": "2024-06", "total_paid": 25000, "variation_percent": 13.6},
            ],
        },
        "top_procedures": {
            "procedures": [
                {"procedure_description": "Consulta médica", "occurrences": 300, "total_paid": 24000, "avg_paid": 80},
                {"procedure_description": "Hemograma completo", "occurrences": 200, "total_paid": 8000, "avg_paid": 40},
                {"procedure_description": "Ultrassonografia", "occurrences": 100, "total_paid": 20000, "avg_paid": 200},
            ],
        },
        "top_providers": {
            "providers": [
                {"provider_name": "Hospital ABC", "total_paid": 80000, "percentage": 40.0},
                {"provider_name": "Laboratório XYZ", "total_paid": 30000, "percentage": 15.0},
                {"provider_name": "Clínica 123", "total_paid": 20000, "percentage": 10.0},
            ],
        },
    }


def create_mock_opportunities() -> List[Dict[str, Any]]:
    """Cria lista mock de oportunidades identificadas."""
    return [
        {
            "type": "provider_concentration",
            "title": "Alta concentração em prestadores",
            "description": "Os 3 maiores prestadores concentram 65% dos custos.",
            "priority": "alta",
            "estimated_savings": 9100.00,
            "action_items": ["Negociar descontos", "Avaliar alternativas"],
        },
        {
            "type": "cost_trend",
            "title": "Tendência de alta acima do mercado",
            "description": "Custos crescendo 12% ao mês em média.",
            "priority": "alta",
            "estimated_savings": 5000.00,
            "action_items": ["Analisar causas", "Implementar gestão de saúde"],
        },
        {
            "type": "high_cost_category",
            "title": "Alta concentração em internação",
            "description": "Internação representa 40% dos custos.",
            "priority": "média",
            "estimated_savings": 4800.00,
            "action_items": ["Revisar autorizações", "Segunda opinião"],
        },
    ]


@pytest.fixture
def mock_cosmos_client():
    """Fixture que fornece um CosmosDBClient mockado."""
    mock = MagicMock()
    mock.get_cost_summary = AsyncMock(return_value={
        "total_records": 1500,
        "total_charged": 250000,
        "total_paid": 200000,
    })
    mock.get_cost_by_category = AsyncMock(return_value=[
        {"category": "internacao", "total_paid": 80000},
        {"category": "exame", "total_paid": 60000},
    ])
    return mock


@pytest.fixture
def mock_llm_response():
    """Fixture que fornece uma resposta mock do LLM."""
    return {
        "content": """## Análise de Oportunidades de Renegociação

**Resumo Executivo:**
Identificamos 3 oportunidades de economia com potencial total de R$ 18.900,00.

**Principais Recomendações:**

1. **[ALTA PRIORIDADE] Negociação com Prestadores**
   - Economia estimada: R$ 9.100,00
   - Ação: Solicitar proposta comercial dos principais prestadores

2. **[ALTA PRIORIDADE] Gestão de Tendência de Custos**
   - Economia estimada: R$ 5.000,00
   - Ação: Implementar programa de gestão de saúde

3. **[MÉDIA PRIORIDADE] Otimização de Internações**
   - Economia estimada: R$ 4.800,00
   - Ação: Revisar protocolo de autorizações

**Próximos Passos:**
1. Validar dados com equipe de RH
2. Agendar reunião com operadora
3. Elaborar proposta de renegociação""",
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 800,
            "completion_tokens": 400,
            "total_tokens": 1200,
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
# Testes de Ferramentas de Negociação
# ============================================


class TestIdentifyRenegotiationOpportunitiesTool:
    """Testes para IdentifyRenegotiationOpportunitiesTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = IdentifyRenegotiationOpportunitiesTool()

        assert tool.name == "identify_renegotiation_opportunities"
        assert "oportunidades" in tool.description.lower()
        assert "renegociação" in tool.description.lower()

    def test_get_parameters(self):
        """Testa parâmetros da ferramenta."""
        tool = IdentifyRenegotiationOpportunitiesTool()
        params = tool.get_parameters()

        param_names = [p.name for p in params]
        assert "client_id" in param_names
        assert "contract_id" in param_names
        assert "cost_data" in param_names

    @pytest.mark.asyncio
    async def test_execute_with_cost_data(self, mock_cosmos_client):
        """Testa execução com dados de custos fornecidos."""
        tool = IdentifyRenegotiationOpportunitiesTool(cosmos_client=mock_cosmos_client)
        cost_data = create_mock_cost_data()

        result = await tool.execute(
            client_id="cliente-123",
            cost_data=cost_data,
        )

        assert "opportunities" in result
        assert "total_opportunities" in result
        assert "total_potential_savings" in result
        assert isinstance(result["opportunities"], list)

    def test_analyze_provider_concentration(self):
        """Testa análise de concentração de prestadores."""
        tool = IdentifyRenegotiationOpportunitiesTool()
        cost_data = {
            "total_paid": 200000,
            "top_providers": {
                "providers": [
                    {"provider_name": "Hospital A", "percentage": 40.0},
                    {"provider_name": "Hospital B", "percentage": 20.0},
                    {"provider_name": "Clínica C", "percentage": 10.0},
                ],
            },
        }

        opportunities = tool._analyze_provider_concentration(cost_data)

        # Concentração > 50% deve gerar oportunidade
        assert len(opportunities) == 1
        assert opportunities[0]["type"] == "provider_concentration"
        assert opportunities[0]["estimated_savings"] > 0

    def test_analyze_cost_trends_high(self):
        """Testa análise de tendência de alta."""
        tool = IdentifyRenegotiationOpportunitiesTool()
        cost_data = {
            "total_paid": 200000,
            "by_period": {
                "periods": [
                    {"month": "2024-01", "variation_percent": None},
                    {"month": "2024-02", "variation_percent": 20.0},
                    {"month": "2024-03", "variation_percent": 18.0},
                    {"month": "2024-04", "variation_percent": 22.0},
                ],
            },
        }

        opportunities = tool._analyze_cost_trends(cost_data)

        # Tendência > 15% deve gerar oportunidade
        assert len(opportunities) == 1
        assert opportunities[0]["type"] == "cost_trend"
        assert "alta" in opportunities[0]["description"].lower()

    def test_analyze_high_cost_categories(self):
        """Testa análise de categorias de alto custo."""
        tool = IdentifyRenegotiationOpportunitiesTool()
        cost_data = {
            "total_paid": 200000,
            "by_category": {
                "categories": [
                    {"category": "internacao", "total_paid": 100000, "percentage": 50.0},
                    {"category": "exame", "total_paid": 60000, "percentage": 30.0},
                ],
            },
        }

        opportunities = tool._analyze_high_cost_categories(cost_data)

        # Categoria > 35% deve gerar oportunidade
        assert len(opportunities) >= 1
        assert any(o["type"] == "high_cost_category" for o in opportunities)

    def test_analyze_glosas_high(self):
        """Testa análise de glosas altas."""
        tool = IdentifyRenegotiationOpportunitiesTool()
        cost_data = {
            "total_charged": 250000,
            "total_paid": 200000,  # 20% de glosa
        }

        opportunities = tool._analyze_glosas(cost_data)

        assert len(opportunities) == 1
        assert opportunities[0]["type"] == "high_glosa"

    def test_analyze_glosas_low(self):
        """Testa análise de glosas baixas."""
        tool = IdentifyRenegotiationOpportunitiesTool()
        cost_data = {
            "total_charged": 202000,
            "total_paid": 200000,  # ~1% de glosa
        }

        opportunities = tool._analyze_glosas(cost_data)

        assert len(opportunities) == 1
        assert opportunities[0]["type"] == "low_glosa"


class TestEstimateSavingsTool:
    """Testes para EstimateSavingsTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = EstimateSavingsTool()

        assert tool.name == "estimate_savings"
        assert "economia" in tool.description.lower()

    def test_get_parameters(self):
        """Testa parâmetros da ferramenta."""
        tool = EstimateSavingsTool()
        params = tool.get_parameters()

        param_names = [p.name for p in params]
        assert "client_id" in param_names
        assert "annual_cost" in param_names
        assert "scenarios" in param_names

    @pytest.mark.asyncio
    async def test_execute_all_scenarios(self):
        """Testa execução com todos os cenários."""
        tool = EstimateSavingsTool()

        result = await tool.execute(
            client_id="cliente-123",
            annual_cost=200000,
            scenarios=["all"],
        )

        assert "scenarios" in result
        assert "total_estimates" in result
        assert len(result["scenarios"]) == 4  # reajuste, coparticipacao, rede, gestao_saude

    @pytest.mark.asyncio
    async def test_execute_specific_scenario(self):
        """Testa execução com cenário específico."""
        tool = EstimateSavingsTool()

        result = await tool.execute(
            client_id="cliente-123",
            annual_cost=200000,
            scenarios=["reajuste"],
        )

        assert len(result["scenarios"]) == 1
        assert result["scenarios"][0]["scenario"] == "reajuste"

    def test_calculate_scenario_reajuste(self):
        """Testa cálculo do cenário de reajuste."""
        tool = EstimateSavingsTool()

        scenario = tool._calculate_scenario("reajuste", 200000)

        assert scenario is not None
        assert scenario["scenario"] == "reajuste"
        assert scenario["conservative"] > 0
        assert scenario["realistic"] > 0
        assert scenario["optimistic"] > 0
        assert scenario["conservative"] < scenario["realistic"] < scenario["optimistic"]

    def test_calculate_scenario_invalid(self):
        """Testa cenário inválido."""
        tool = EstimateSavingsTool()

        scenario = tool._calculate_scenario("cenario_invalido", 200000)

        assert scenario is None


class TestPrioritizeNegotiationPointsTool:
    """Testes para PrioritizeNegotiationPointsTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = PrioritizeNegotiationPointsTool()

        assert tool.name == "prioritize_negotiation_points"
        assert "prioriz" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute(self):
        """Testa execução da ferramenta."""
        tool = PrioritizeNegotiationPointsTool()
        opportunities = create_mock_opportunities()

        result = await tool.execute(opportunities=opportunities)

        assert "prioritized_opportunities" in result
        assert "summary" in result
        assert "by_priority" in result
        assert len(result["prioritized_opportunities"]) == 3

    @pytest.mark.asyncio
    async def test_ranking_order(self):
        """Testa ordenação por ranking."""
        tool = PrioritizeNegotiationPointsTool()
        opportunities = create_mock_opportunities()

        result = await tool.execute(opportunities=opportunities)

        # Verifica que ranks estão em ordem crescente
        ranks = [o["rank"] for o in result["prioritized_opportunities"]]
        assert ranks == sorted(ranks)

    @pytest.mark.asyncio
    async def test_priority_categorization(self):
        """Testa categorização por prioridade."""
        tool = PrioritizeNegotiationPointsTool()
        opportunities = create_mock_opportunities()

        result = await tool.execute(opportunities=opportunities)

        by_priority = result["by_priority"]
        assert "alta" in by_priority
        assert "média" in by_priority
        assert "baixa" in by_priority

    def test_calculate_scores(self):
        """Testa cálculo de scores."""
        tool = PrioritizeNegotiationPointsTool()

        opportunity = {
            "estimated_savings": 50000,
            "type": "provider_concentration",
            "priority": "alta",
        }

        scores = tool._calculate_scores(opportunity)

        assert "impacto" in scores
        assert "facilidade" in scores
        assert "urgencia" in scores
        assert all(0 <= v <= 1 for v in scores.values())


class TestGenerateNegotiationReportTool:
    """Testes para GenerateNegotiationReportTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = GenerateNegotiationReportTool()

        assert tool.name == "generate_negotiation_report"
        assert "relatório" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute(self):
        """Testa execução da ferramenta."""
        tool = GenerateNegotiationReportTool()

        result = await tool.execute(
            client_id="cliente-123",
            opportunities=create_mock_opportunities(),
            savings_estimates={
                "total_estimates": {
                    "conservative": 10000,
                    "realistic": 15000,
                    "optimistic": 20000,
                },
            },
        )

        assert "executive_summary" in result
        assert "savings_potential" in result
        assert "top_recommendations" in result
        assert "action_plan" in result
        assert "next_steps" in result

    @pytest.mark.asyncio
    async def test_report_structure(self):
        """Testa estrutura do relatório."""
        tool = GenerateNegotiationReportTool()

        result = await tool.execute(
            client_id="cliente-123",
            opportunities=create_mock_opportunities(),
            savings_estimates={"total_estimates": {"realistic": 15000}},
        )

        # Verifica que tem top 3 recomendações
        assert len(result["top_recommendations"]) <= 3

        # Verifica estrutura do action plan
        assert "curto_prazo" in result["action_plan"]
        assert "medio_prazo" in result["action_plan"]
        assert "longo_prazo" in result["action_plan"]


class TestRegisterNegotiationTools:
    """Testes para register_negotiation_tools."""

    def test_register_all_tools(self):
        """Testa registro de todas as ferramentas."""
        registry = ToolRegistry()

        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            register_negotiation_tools(registry)

        tools = registry.list_tools()

        assert "identify_renegotiation_opportunities" in tools
        assert "estimate_savings" in tools
        assert "prioritize_negotiation_points" in tools
        assert "generate_negotiation_report" in tools


# ============================================
# Testes do NegotiationAdvisorAgent
# ============================================


class TestNegotiationAdvisorAgent:
    """Testes para NegotiationAdvisorAgent."""

    def test_agent_properties(self):
        """Testa propriedades do agente."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            agent = NegotiationAdvisorAgent(auto_register_tools=False)

            assert agent.agent_type == AgentType.NEGOTIATION_ADVISOR
            assert agent.agent_name == "negotiation_advisor_agent"
            assert agent.temperature == 0.3

    def test_get_tools(self):
        """Testa ferramentas disponíveis."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            agent = NegotiationAdvisorAgent(auto_register_tools=False)
            tools = agent.get_tools()

            assert "identify_renegotiation_opportunities" in tools
            assert "estimate_savings" in tools
            assert "prioritize_negotiation_points" in tools
            assert "generate_negotiation_report" in tools

    def test_system_prompt_contains_key_elements(self):
        """Testa que o system prompt contém elementos importantes."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            agent = NegotiationAdvisorAgent(auto_register_tools=False)

            assert "renegociação" in agent.system_prompt.lower()
            assert "economia" in agent.system_prompt.lower()
            assert "priorizar" in agent.system_prompt.lower() or "prioriza" in agent.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_process_with_preloaded_data(self, mock_openai_client):
        """Testa processamento com dados pré-carregados."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            registry = ToolRegistry()
            register_negotiation_tools(registry)

            agent = NegotiationAdvisorAgent(
                tool_registry=registry,
                auto_register_tools=False,
            )
            agent._client = mock_openai_client

            cost_data = create_mock_cost_data()

            context = AgentContext(
                client_id="cliente-123",
                query="Quais as oportunidades de economia?",
                cost_data=cost_data,
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert result.response is not None
            assert result.structured_output is not None
            assert "opportunities" in result.structured_output

    @pytest.mark.asyncio
    async def test_process_with_metadata_cost_data(self, mock_openai_client):
        """Testa processamento com dados em metadata."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            registry = ToolRegistry()
            register_negotiation_tools(registry)

            agent = NegotiationAdvisorAgent(
                tool_registry=registry,
                auto_register_tools=False,
            )
            agent._client = mock_openai_client

            cost_data = create_mock_cost_data()

            context = AgentContext(
                client_id="cliente-123",
                query="Analise oportunidades de renegociação",
                metadata={"cost_data": cost_data},
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED


class TestNegotiationAdvisorBuildPrompt:
    """Testes para construção de prompts."""

    def test_build_analysis_prompt_with_opportunities(self):
        """Testa construção do prompt com oportunidades."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            agent = NegotiationAdvisorAgent(auto_register_tools=False)

            opportunities = create_mock_opportunities()
            savings_estimates = {
                "total_estimates": {
                    "conservative": 10000,
                    "realistic": 15000,
                    "optimistic": 20000,
                    "conservative_percent": 5.0,
                    "realistic_percent": 7.5,
                    "optimistic_percent": 10.0,
                },
            }
            cost_data = {"summary": {"total_paid": 200000}, "total_paid": 200000}

            prompt = agent._build_analysis_prompt(
                query="Quais as oportunidades de economia?",
                opportunities=opportunities,
                savings_estimates=savings_estimates,
                cost_data=cost_data,
                contract_context=None,
                chunks=[],
            )

            assert "OPORTUNIDADES IDENTIFICADAS" in prompt
            assert "POTENCIAL DE ECONOMIA" in prompt
            assert "200" in prompt

    def test_enhance_query(self):
        """Testa enriquecimento da query."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            agent = NegotiationAdvisorAgent(auto_register_tools=False)

            context = AgentContext(
                client_id="cliente-123",
                contract_id="contrato-456",
                query="Oportunidades de economia",
            )

            enhanced = agent._enhance_query(context)

            assert "cliente-123" in enhanced
            assert "contrato-456" in enhanced
            assert "renegociação" in enhanced.lower()


class TestCreateNegotiationAdvisorAgent:
    """Testes para factory function."""

    def test_create_agent(self):
        """Testa criação via factory."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            agent = create_negotiation_advisor_agent()

            assert isinstance(agent, NegotiationAdvisorAgent)
            assert agent.agent_type == AgentType.NEGOTIATION_ADVISOR


class TestNegotiationAdvisorIntegration:
    """Testes de integração."""

    @pytest.mark.asyncio
    async def test_full_analysis_flow(self, mock_openai_client):
        """Testa fluxo completo de análise."""
        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            registry = ToolRegistry()
            register_negotiation_tools(registry)

            agent = NegotiationAdvisorAgent(
                tool_registry=registry,
                auto_register_tools=False,
            )
            agent._client = mock_openai_client

            cost_data = create_mock_cost_data()

            result = await agent.execute(
                query="Faça uma análise completa de oportunidades de renegociação",
                client_id="cliente-123",
                metadata={"cost_data": cost_data},
            )

            assert result.status == AgentStatus.COMPLETED
            assert result.response is not None
            assert result.agent_type == AgentType.NEGOTIATION_ADVISOR

    @pytest.mark.asyncio
    async def test_execution_tracking(self, mock_openai_client):
        """Testa rastreamento de execução."""
        from src.agents.execution_logger import ExecutionTracker

        with patch("src.agents.negotiation_tools.get_cosmos_client"):
            registry = ToolRegistry()
            register_negotiation_tools(registry)

            tracker = ExecutionTracker()
            agent = NegotiationAdvisorAgent(
                tool_registry=registry,
                execution_tracker=tracker,
                auto_register_tools=False,
            )
            agent._client = mock_openai_client

            cost_data = create_mock_cost_data()

            result = await agent.execute(
                query="Oportunidades de economia",
                client_id="cliente-123",
                metadata={"cost_data": cost_data},
            )

            tracked = tracker.get(result.execution_id)
            assert tracked is not None
            assert tracked.agent_type == AgentType.NEGOTIATION_ADVISOR


class TestMarketBenchmarks:
    """Testes para benchmarks de mercado."""

    def test_benchmark_values_exist(self):
        """Testa que benchmarks estão definidos."""
        assert "reajuste_anual" in MARKET_BENCHMARKS
        assert "coparticipacao" in MARKET_BENCHMARKS
        assert "glosa_aceitavel" in MARKET_BENCHMARKS
        assert "sinistralidade_alvo" in MARKET_BENCHMARKS

    def test_reajuste_benchmark_values(self):
        """Testa valores de benchmark de reajuste."""
        reajuste = MARKET_BENCHMARKS["reajuste_anual"]

        assert reajuste["min_mercado"] < reajuste["inflacao_medica"]
        assert reajuste["inflacao_medica"] < reajuste["max_mercado"]
        assert reajuste["otimo"] < reajuste["inflacao_medica"]

    def test_coparticipacao_benchmark_structure(self):
        """Testa estrutura de benchmark de coparticipação."""
        coprt = MARKET_BENCHMARKS["coparticipacao"]

        assert "consulta" in coprt
        assert "exame_simples" in coprt
        assert "internacao" in coprt

        for key, values in coprt.items():
            assert "min" in values
            assert "max" in values
            assert "comum" in values
            assert values["min"] <= values["comum"] <= values["max"]
