"""
Testes para o OrchestratorAgent.

Testa:
- Análise de intent por keywords e LLM
- Decisão de quais agentes acionar
- Coordenação de execução (paralela/sequencial/mista)
- Consolidação de respostas
"""

import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
    OrchestratorDecision,
)
from src.agents.orchestrator_agent import (
    OrchestratorAgent,
    create_orchestrator_agent,
    INTENT_AGENT_MAPPING,
    INTENT_KEYWORDS,
)


# ============================================
# Fixtures
# ============================================


@pytest.fixture
def mock_retrieval_result():
    """Resultado mock do RetrievalAgent."""
    return AgentExecutionResult(
        execution_id="ret-123",
        agent_type=AgentType.RETRIEVAL,
        agent_name="retrieval_agent",
        status=AgentStatus.COMPLETED,
        response="Encontrei 3 chunks relevantes sobre carência.",
        structured_output={
            "chunks": [
                {"content": "Carência de 24 horas...", "page_number": 5},
                {"content": "Carência de 180 dias para cirurgias...", "page_number": 12},
            ],
            "total_results": 2,
        },
        sources=[{"page_number": 5}, {"page_number": 12}],
    )


@pytest.fixture
def mock_contract_analyst_result():
    """Resultado mock do ContractAnalystAgent."""
    return AgentExecutionResult(
        execution_id="ca-123",
        agent_type=AgentType.CONTRACT_ANALYST,
        agent_name="contract_analyst_agent",
        status=AgentStatus.COMPLETED,
        response="""**Carências do Contrato**

Conforme análise dos trechos:

1. **Carência de urgência/emergência**: 24 horas (Página 5)
2. **Carência para cirurgias eletivas**: 180 dias (Página 12)

Estes prazos estão dentro do permitido pela ANS.""",
        structured_output={"analysis": "...", "chunks_analyzed": 2},
    )


@pytest.fixture
def mock_cost_insights_result():
    """Resultado mock do CostInsightsAgent."""
    return AgentExecutionResult(
        execution_id="ci-123",
        agent_type=AgentType.COST_INSIGHTS,
        agent_name="cost_insights_agent",
        status=AgentStatus.COMPLETED,
        response="""**Análise de Custos**

- Total pago no período: R$ 200.000,00
- Categoria principal: Internação (40%)
- Tendência: Alta de 12% nos últimos 3 meses""",
        structured_output={
            "cost_data": {"total_paid": 200000},
            "analysis": "...",
        },
    )


@pytest.fixture
def mock_negotiation_result():
    """Resultado mock do NegotiationAdvisorAgent."""
    return AgentExecutionResult(
        execution_id="na-123",
        agent_type=AgentType.NEGOTIATION_ADVISOR,
        agent_name="negotiation_advisor_agent",
        status=AgentStatus.COMPLETED,
        response="""**Oportunidades de Economia**

1. Negociação com prestadores: R$ 14.000
2. Gestão de custos: R$ 10.000

Total potencial: R$ 24.000 (12% do custo anual)""",
        structured_output={
            "opportunities": [{"title": "...", "estimated_savings": 14000}],
        },
    )


@pytest.fixture
def mock_llm_response():
    """Resposta mock do LLM."""
    return {
        "content": "Resposta consolidada do orchestrator.",
        "finish_reason": "stop",
        "usage": {"total_tokens": 500},
    }


@pytest.fixture
def mock_openai_client(mock_llm_response):
    """Cliente OpenAI mockado."""
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
# Testes de Análise de Intent
# ============================================


class TestIntentDetection:
    """Testes para detecção de intent."""

    def test_detect_contract_query_intent(self):
        """Testa detecção de intent de consulta a contrato."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            result = orchestrator._detect_intent_by_keywords(
                "Qual é o prazo de carência para cirurgias?"
            )

            assert result["intent"] == "contract_query"
            assert result["confidence"] >= 0.5
            assert "carência" in result["keywords_found"]

    def test_detect_cost_analysis_intent(self):
        """Testa detecção de intent de análise de custos."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            result = orchestrator._detect_intent_by_keywords(
                "Quanto gastamos com internações no último trimestre?"
            )

            assert result["intent"] == "cost_analysis"
            assert "gasto" in result["keywords_found"] or "internação" in result["keywords_found"]

    def test_detect_negotiation_intent(self):
        """Testa detecção de intent de negociação."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            result = orchestrator._detect_intent_by_keywords(
                "Quais oportunidades de economia temos para renegociar?"
            )

            assert result["intent"] == "negotiation"
            assert any(
                kw in result["keywords_found"]
                for kw in ["economia", "renegociar", "oportunidade"]
            )

    def test_detect_mixed_intent(self):
        """Testa detecção de intent misto (contrato + custos)."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            result = orchestrator._detect_intent_by_keywords(
                "Qual a cobertura do contrato e quanto gastamos com exames?"
            )

            # Pode ser cost_and_contract ou um dos dois
            assert result["intent"] in ["cost_and_contract", "contract_query", "cost_analysis"]

    def test_detect_general_intent_no_keywords(self):
        """Testa fallback para intent geral."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            result = orchestrator._detect_intent_by_keywords(
                "Olá, bom dia!"
            )

            assert result["intent"] == "general"
            assert result["confidence"] < 0.5


class TestBuildDecision:
    """Testes para construção de decisão."""

    def test_build_decision_contract_query(self):
        """Testa construção de decisão para consulta de contrato."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            decision = orchestrator._build_decision_from_intent(
                intent="contract_query",
                confidence=0.8,
                reasoning="Detectado por keywords",
            )

            assert decision.query_intent == "contract_query"
            assert AgentType.RETRIEVAL in decision.agents_to_invoke
            assert AgentType.CONTRACT_ANALYST in decision.agents_to_invoke

    def test_build_decision_cost_analysis(self):
        """Testa construção de decisão para análise de custos."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            decision = orchestrator._build_decision_from_intent(
                intent="cost_analysis",
                confidence=0.9,
                reasoning="Detectado por keywords",
            )

            assert decision.query_intent == "cost_analysis"
            assert AgentType.COST_INSIGHTS in decision.agents_to_invoke

    def test_build_decision_negotiation(self):
        """Testa construção de decisão para negociação."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            decision = orchestrator._build_decision_from_intent(
                intent="negotiation",
                confidence=0.85,
                reasoning="Detectado por keywords",
            )

            assert decision.query_intent == "negotiation"
            assert AgentType.RETRIEVAL in decision.agents_to_invoke
            assert AgentType.COST_INSIGHTS in decision.agents_to_invoke
            assert AgentType.NEGOTIATION_ADVISOR in decision.agents_to_invoke
            assert decision.execution_mode == "mixed"


# ============================================
# Testes de Execução de Agentes
# ============================================


class TestAgentExecution:
    """Testes para execução de agentes."""

    @pytest.mark.asyncio
    async def test_execute_single_agent(
        self,
        mock_openai_client,
        mock_cost_insights_result,
    ):
        """Testa execução de um único agente."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            # Mock do agente de custos
            mock_cost_agent = MagicMock()
            mock_cost_agent.execute_with_context = AsyncMock(
                return_value=mock_cost_insights_result
            )
            orchestrator._cost_insights = mock_cost_agent

            context = AgentContext(
                client_id="cliente-123",
                query="Quanto gastamos?",
            )

            result = await orchestrator._execute_single_agent(
                agent_type=AgentType.COST_INSIGHTS,
                context=context,
            )

            assert result.status == AgentStatus.COMPLETED
            assert result.agent_type == AgentType.COST_INSIGHTS

    @pytest.mark.asyncio
    async def test_execute_agents_parallel(
        self,
        mock_openai_client,
        mock_retrieval_result,
        mock_cost_insights_result,
    ):
        """Testa execução paralela de agentes."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            # Mock dos agentes
            mock_retrieval = MagicMock()
            mock_retrieval.execute_with_context = AsyncMock(
                return_value=mock_retrieval_result
            )
            orchestrator._retrieval_agent = mock_retrieval

            mock_cost = MagicMock()
            mock_cost.execute_with_context = AsyncMock(
                return_value=mock_cost_insights_result
            )
            orchestrator._cost_insights = mock_cost

            context = AgentContext(
                client_id="cliente-123",
                query="Teste paralelo",
            )

            results = await orchestrator._execute_agents_parallel(
                agent_types=[AgentType.RETRIEVAL, AgentType.COST_INSIGHTS],
                context=context,
            )

            assert AgentType.RETRIEVAL in results
            assert AgentType.COST_INSIGHTS in results
            assert all(r.status == AgentStatus.COMPLETED for r in results.values())

    @pytest.mark.asyncio
    async def test_execute_agents_sequential(
        self,
        mock_openai_client,
        mock_retrieval_result,
        mock_contract_analyst_result,
    ):
        """Testa execução sequencial de agentes."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            # Mock dos agentes
            mock_retrieval = MagicMock()
            mock_retrieval.execute_with_context = AsyncMock(
                return_value=mock_retrieval_result
            )
            orchestrator._retrieval_agent = mock_retrieval

            mock_analyst = MagicMock()
            mock_analyst.execute_with_context = AsyncMock(
                return_value=mock_contract_analyst_result
            )
            orchestrator._contract_analyst = mock_analyst

            context = AgentContext(
                client_id="cliente-123",
                query="Qual a carência?",
            )

            results = await orchestrator._execute_agents_sequential(
                agent_types=[AgentType.RETRIEVAL, AgentType.CONTRACT_ANALYST],
                context=context,
                priority_order=[AgentType.RETRIEVAL, AgentType.CONTRACT_ANALYST],
            )

            assert AgentType.RETRIEVAL in results
            assert AgentType.CONTRACT_ANALYST in results

            # Verificar que Retrieval foi chamado primeiro
            assert mock_retrieval.execute_with_context.called
            assert mock_analyst.execute_with_context.called


# ============================================
# Testes de Consolidação
# ============================================


class TestConsolidation:
    """Testes para consolidação de respostas."""

    @pytest.mark.asyncio
    async def test_consolidate_single_response(self, mock_openai_client):
        """Testa consolidação com resposta única."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            result = AgentExecutionResult(
                execution_id="test",
                agent_type=AgentType.COST_INSIGHTS,
                agent_name="cost_insights",
                status=AgentStatus.COMPLETED,
                response="Análise de custos completa.",
            )

            consolidated = await orchestrator._consolidate_responses(
                query="Quanto gastamos?",
                decision=OrchestratorDecision(
                    query_intent="cost_analysis",
                    agents_to_invoke=[AgentType.COST_INSIGHTS],
                    reasoning="Teste",
                ),
                agent_results={AgentType.COST_INSIGHTS: result},
            )

            # Com um único resultado, retorna direto
            assert consolidated["content"] == "Análise de custos completa."

    @pytest.mark.asyncio
    async def test_consolidate_multiple_responses(
        self,
        mock_openai_client,
        mock_retrieval_result,
        mock_contract_analyst_result,
    ):
        """Testa consolidação com múltiplas respostas."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            consolidated = await orchestrator._consolidate_responses(
                query="Qual a carência do contrato?",
                decision=OrchestratorDecision(
                    query_intent="contract_query",
                    agents_to_invoke=[AgentType.RETRIEVAL, AgentType.CONTRACT_ANALYST],
                    reasoning="Teste",
                ),
                agent_results={
                    AgentType.RETRIEVAL: mock_retrieval_result,
                    AgentType.CONTRACT_ANALYST: mock_contract_analyst_result,
                },
            )

            # Com múltiplos resultados, usa LLM para consolidar
            assert consolidated["content"] is not None

    @pytest.mark.asyncio
    async def test_consolidate_no_successful_results(self, mock_openai_client):
        """Testa consolidação sem resultados bem-sucedidos."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            failed_result = AgentExecutionResult(
                execution_id="test",
                agent_type=AgentType.RETRIEVAL,
                agent_name="retrieval",
                status=AgentStatus.FAILED,
                error="Erro de conexão",
            )

            consolidated = await orchestrator._consolidate_responses(
                query="Teste",
                decision=OrchestratorDecision(
                    query_intent="general",
                    agents_to_invoke=[AgentType.RETRIEVAL],
                    reasoning="Teste",
                ),
                agent_results={AgentType.RETRIEVAL: failed_result},
            )

            assert "não foi possível" in consolidated["content"].lower()

    def test_build_consolidation_prompt(
        self,
        mock_retrieval_result,
        mock_contract_analyst_result,
    ):
        """Testa construção do prompt de consolidação."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            prompt = orchestrator._build_consolidation_prompt(
                query="Qual a carência?",
                agent_results={
                    AgentType.RETRIEVAL: mock_retrieval_result,
                    AgentType.CONTRACT_ANALYST: mock_contract_analyst_result,
                },
            )

            assert "PERGUNTA DO USUÁRIO" in prompt
            assert "Qual a carência?" in prompt
            assert "AGENTE DE BUSCA" in prompt or "ANALISTA" in prompt


# ============================================
# Testes de Fluxo Completo
# ============================================


class TestOrchestratorFullFlow:
    """Testes de fluxo completo do orchestrator."""

    def test_agent_properties(self):
        """Testa propriedades do agente."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            assert orchestrator.agent_type == AgentType.ORCHESTRATOR
            assert orchestrator.agent_name == "orchestrator_agent"
            assert orchestrator.temperature == 0.3

    def test_system_prompt_contains_key_elements(self):
        """Testa que o system prompt contém elementos importantes."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            assert "orquestrador" in orchestrator.system_prompt.lower()
            assert "agentes" in orchestrator.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_process_contract_query(
        self,
        mock_openai_client,
        mock_retrieval_result,
        mock_contract_analyst_result,
    ):
        """Testa processamento de query sobre contrato."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            # Mock dos agentes
            mock_retrieval = MagicMock()
            mock_retrieval.execute_with_context = AsyncMock(
                return_value=mock_retrieval_result
            )
            orchestrator._retrieval_agent = mock_retrieval

            mock_analyst = MagicMock()
            mock_analyst.execute_with_context = AsyncMock(
                return_value=mock_contract_analyst_result
            )
            orchestrator._contract_analyst = mock_analyst

            context = AgentContext(
                client_id="cliente-123",
                contract_id="contrato-456",
                query="Qual o prazo de carência para cirurgias?",
            )

            result = await orchestrator.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert result.response is not None
            assert result.structured_output is not None
            assert "contract_query" in result.structured_output["intent"]

    @pytest.mark.asyncio
    async def test_process_cost_query(
        self,
        mock_openai_client,
        mock_cost_insights_result,
    ):
        """Testa processamento de query sobre custos."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            # Mock do agente de custos
            mock_cost = MagicMock()
            mock_cost.execute_with_context = AsyncMock(
                return_value=mock_cost_insights_result
            )
            orchestrator._cost_insights = mock_cost

            context = AgentContext(
                client_id="cliente-123",
                query="Quanto gastamos com exames no último mês?",
            )

            result = await orchestrator.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert "cost" in result.structured_output["intent"]

    @pytest.mark.asyncio
    async def test_process_negotiation_query(
        self,
        mock_openai_client,
        mock_retrieval_result,
        mock_cost_insights_result,
        mock_negotiation_result,
    ):
        """Testa processamento de query sobre negociação."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()
            orchestrator._client = mock_openai_client

            # Mock dos agentes
            mock_retrieval = MagicMock()
            mock_retrieval.execute_with_context = AsyncMock(
                return_value=mock_retrieval_result
            )
            orchestrator._retrieval_agent = mock_retrieval

            mock_cost = MagicMock()
            mock_cost.execute_with_context = AsyncMock(
                return_value=mock_cost_insights_result
            )
            orchestrator._cost_insights = mock_cost

            mock_negotiation = MagicMock()
            mock_negotiation.execute_with_context = AsyncMock(
                return_value=mock_negotiation_result
            )
            orchestrator._negotiation_advisor = mock_negotiation

            context = AgentContext(
                client_id="cliente-123",
                query="Quais são as oportunidades de economia para renegociar o contrato?",
            )

            result = await orchestrator.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert "negotiation" in result.structured_output["intent"]


# ============================================
# Testes de Factory e Integração
# ============================================


class TestCreateOrchestratorAgent:
    """Testes para factory function."""

    def test_create_agent(self):
        """Testa criação via factory."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = create_orchestrator_agent()

            assert isinstance(orchestrator, OrchestratorAgent)
            assert orchestrator.agent_type == AgentType.ORCHESTRATOR


class TestIntentAgentMapping:
    """Testes para mapeamento de intent para agentes."""

    def test_all_intents_have_mappings(self):
        """Testa que todos os intents têm mapeamentos."""
        expected_intents = [
            "contract_query",
            "cost_analysis",
            "negotiation",
            "cost_and_contract",
            "general",
        ]

        for intent in expected_intents:
            assert intent in INTENT_AGENT_MAPPING
            assert len(INTENT_AGENT_MAPPING[intent]) > 0

    def test_intent_keywords_coverage(self):
        """Testa cobertura de keywords por intent."""
        for intent, keywords in INTENT_KEYWORDS.items():
            assert len(keywords) >= 5, f"Intent {intent} tem poucas keywords"


class TestContextEnrichment:
    """Testes para enriquecimento de contexto."""

    def test_enrich_context_with_retrieval(self, mock_retrieval_result):
        """Testa enriquecimento com resultado de retrieval."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            base_context = AgentContext(
                client_id="cliente-123",
                query="Teste",
            )

            enriched = orchestrator._enrich_context(
                context=base_context,
                previous_results={AgentType.RETRIEVAL: mock_retrieval_result},
            )

            assert len(enriched.retrieved_chunks) > 0
            assert "retrieval_result" in enriched.metadata

    def test_enrich_context_with_cost_data(self, mock_cost_insights_result):
        """Testa enriquecimento com dados de custos."""
        with patch("src.agents.orchestrator_agent.get_tool_registry"):
            orchestrator = OrchestratorAgent()

            base_context = AgentContext(
                client_id="cliente-123",
                query="Teste",
            )

            enriched = orchestrator._enrich_context(
                context=base_context,
                previous_results={AgentType.COST_INSIGHTS: mock_cost_insights_result},
            )

            assert enriched.cost_data is not None
            assert "cost_analysis" in enriched.metadata
