"""
Testes para o ContractAnalystAgent.

Testa:
- Análise de cláusulas contratuais
- Geração de respostas com citações
- Tratamento de casos sem chunks
- Métodos auxiliares (analyze_clause, compare_clauses, summarize_contract)
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
from src.agents.contract_analyst_agent import (
    ContractAnalystAgent,
    create_contract_analyst_agent,
)


# ============================================
# Mock Data e Fixtures
# ============================================


def create_mock_chunks(num_chunks: int = 3) -> List[Dict[str, Any]]:
    """Cria chunks mock para testes."""
    chunks = [
        {
            "id": "chunk-1",
            "content": """CLÁUSULA 5 - CARÊNCIAS
5.1. Para procedimentos de urgência e emergência, não há carência.
5.2. Para consultas e exames simples, a carência é de 30 dias.
5.3. Para internações, a carência é de 180 dias.
5.4. Para partos, a carência é de 300 dias.""",
            "document_id": "doc-123",
            "page_number": 12,
            "section_title": "Carências",
            "section_number": "5",
            "section_type": "clausula",
            "score": 0.95,
        },
        {
            "id": "chunk-2",
            "content": """CLÁUSULA 6 - COBERTURAS
6.1. O plano cobre consultas médicas em todas as especialidades.
6.2. Exames laboratoriais e de imagem conforme rol da ANS.
6.3. Internações hospitalares em enfermaria padrão.
6.4. Procedimentos cirúrgicos eletivos e de urgência.""",
            "document_id": "doc-123",
            "page_number": 15,
            "section_title": "Coberturas",
            "section_number": "6",
            "section_type": "clausula",
            "score": 0.90,
        },
        {
            "id": "chunk-3",
            "content": """CLÁUSULA 10 - REAJUSTES
10.1. O reajuste anual será aplicado na data de aniversário do contrato.
10.2. O índice de reajuste será calculado com base na variação de custos médicos.
10.3. A sinistralidade do grupo será considerada para reajustes adicionais.""",
            "document_id": "doc-123",
            "page_number": 25,
            "section_title": "Reajustes",
            "section_number": "10",
            "section_type": "clausula",
            "score": 0.85,
        },
    ]
    return chunks[:num_chunks]


@pytest.fixture
def mock_llm_response():
    """Fixture que fornece uma resposta mock do LLM."""
    return {
        "content": """Com base nos trechos analisados, posso informar sobre as carências do plano:

**Prazos de Carência:**

1. **Urgência e Emergência**: Não há carência (cobertura imediata)
2. **Consultas e Exames Simples**: 30 dias
3. **Internações**: 180 dias
4. **Partos**: 300 dias

**Fonte**: Cláusula 5 - Carências, página 12

**Pontos de Atenção:**
- O prazo de 300 dias para partos é o máximo permitido pela ANS
- Procedimentos de urgência/emergência têm cobertura imediata por lei""",
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
# Testes do ContractAnalystAgent
# ============================================


class TestContractAnalystAgent:
    """Testes para ContractAnalystAgent."""

    def test_agent_properties(self):
        """Testa propriedades do agente."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()

            assert agent.agent_type == AgentType.CONTRACT_ANALYST
            assert agent.agent_name == "contract_analyst_agent"
            assert agent.temperature == 0.3
            assert agent.max_tokens == 2500

    def test_get_tools_returns_empty(self):
        """Testa que o agente não usa ferramentas externas."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            tools = agent.get_tools()

            assert tools == []

    def test_system_prompt_contains_key_elements(self):
        """Testa que o system prompt contém elementos importantes."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()

            assert "planos de saúde" in agent.system_prompt.lower()
            assert "carência" in agent.system_prompt.lower()
            assert "cobertura" in agent.system_prompt.lower()
            assert "fonte" in agent.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_process_with_chunks(self, mock_openai_client):
        """Testa processamento com chunks disponíveis."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            chunks = create_mock_chunks()
            context = AgentContext(
                client_id="cliente-123",
                query="Qual o prazo de carência para internação?",
                retrieved_chunks=chunks,
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert result.response is not None
            assert "carência" in result.response.lower() or "Carência" in result.response
            assert result.structured_output["chunks_analyzed"] == 3

    @pytest.mark.asyncio
    async def test_process_without_chunks(self, mock_openai_client):
        """Testa processamento sem chunks disponíveis."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            context = AgentContext(
                client_id="cliente-123",
                query="Qual o prazo de carência?",
                retrieved_chunks=[],
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert "não encontrei" in result.response.lower()
            assert result.structured_output["no_data"] is True

    @pytest.mark.asyncio
    async def test_chunks_from_metadata(self, mock_openai_client):
        """Testa obtenção de chunks dos metadata."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            chunks = create_mock_chunks(2)
            context = AgentContext(
                client_id="cliente-123",
                query="Quais as coberturas?",
                metadata={"chunks": chunks},
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert result.structured_output["chunks_analyzed"] == 2

    @pytest.mark.asyncio
    async def test_sources_extraction(self, mock_openai_client):
        """Testa extração de fontes dos chunks."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            chunks = create_mock_chunks()
            context = AgentContext(
                client_id="cliente-123",
                query="Teste",
                retrieved_chunks=chunks,
            )

            result = await agent.execute_with_context(context)

            assert len(result.sources) > 0
            # Verifica que as fontes contêm informações de página
            first_source = result.sources[0]
            assert "page_number" in first_source or first_source.get("page_number") is not None

    @pytest.mark.asyncio
    async def test_tokens_tracking(self, mock_openai_client):
        """Testa rastreamento de tokens."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            chunks = create_mock_chunks(1)
            context = AgentContext(
                client_id="cliente-123",
                query="Teste",
                retrieved_chunks=chunks,
            )

            result = await agent.execute_with_context(context)

            assert result.tokens_used == 700


class TestContractAnalystBuildPrompt:
    """Testes para construção de prompts."""

    def test_build_analysis_prompt(self):
        """Testa construção do prompt de análise."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()

            chunks = create_mock_chunks(2)
            prompt = agent._build_analysis_prompt(
                query="Qual o prazo de carência?",
                chunks=chunks,
            )

            # Verifica que o prompt contém elementos esperados
            assert "carência" in prompt.lower()
            assert "Página 12" in prompt
            assert "Seção 5" in prompt
            assert "PERGUNTA DO USUÁRIO" in prompt
            assert "TRECHOS DO CONTRATO" in prompt

    def test_prompt_with_missing_metadata(self):
        """Testa construção do prompt com metadados faltando."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()

            chunks = [
                {"content": "Texto sem metadados"},
            ]
            prompt = agent._build_analysis_prompt(
                query="Teste",
                chunks=chunks,
            )

            # Deve funcionar mesmo sem metadados
            assert "Texto sem metadados" in prompt
            assert "Trecho 1" in prompt


class TestContractAnalystHelperMethods:
    """Testes para métodos auxiliares."""

    @pytest.mark.asyncio
    async def test_analyze_clause(self, mock_openai_client):
        """Testa análise de cláusula específica."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            result = await agent.analyze_clause(
                clause_text="A carência para internação é de 180 dias.",
                clause_type="carência",
                client_id="cliente-123",
            )

            assert "clause_type" in result
            assert result["clause_type"] == "carência"
            assert "analysis" in result
            assert "original_text" in result

    @pytest.mark.asyncio
    async def test_compare_clauses(self, mock_openai_client):
        """Testa comparação de cláusulas."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            clauses = [
                {"source": "Contrato A", "text": "Carência de 30 dias"},
                {"source": "Contrato B", "text": "Carência de 60 dias"},
            ]

            result = await agent.compare_clauses(
                clauses=clauses,
                comparison_aspect="carência",
                client_id="cliente-123",
            )

            assert "comparison_aspect" in result
            assert result["clauses_count"] == 2
            assert "analysis" in result

    @pytest.mark.asyncio
    async def test_summarize_contract(self, mock_openai_client):
        """Testa geração de resumo do contrato."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            chunks = create_mock_chunks()

            result = await agent.summarize_contract(
                chunks=chunks,
                client_id="cliente-123",
                focus_areas=["carência", "cobertura"],
            )

            assert "summary" in result
            assert result["chunks_analyzed"] == 3
            assert result["focus_areas"] == ["carência", "cobertura"]


class TestContractAnalystErrorHandling:
    """Testes para tratamento de erros."""

    @pytest.mark.asyncio
    async def test_llm_error_handling(self):
        """Testa tratamento de erro do LLM."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()

            # Mock que lança exceção
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("LLM Error")
            )
            agent._client = mock_client

            chunks = create_mock_chunks()
            context = AgentContext(
                client_id="cliente-123",
                query="Teste",
                retrieved_chunks=chunks,
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.FAILED
            assert "LLM Error" in result.error


class TestCreateContractAnalystAgent:
    """Testes para factory function."""

    def test_create_agent(self):
        """Testa criação via factory."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = create_contract_analyst_agent()

            assert isinstance(agent, ContractAnalystAgent)
            assert agent.agent_type == AgentType.CONTRACT_ANALYST


class TestContractAnalystIntegration:
    """Testes de integração."""

    @pytest.mark.asyncio
    async def test_full_analysis_flow(self, mock_openai_client):
        """Testa fluxo completo de análise."""
        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            agent = ContractAnalystAgent()
            agent._client = mock_openai_client

            # Simular fluxo: query -> chunks -> análise
            chunks = create_mock_chunks()

            result = await agent.execute(
                query="Quais são os prazos de carência do plano?",
                client_id="cliente-123",
                contract_id="contrato-456",
                metadata={"chunks": chunks},
            )

            assert result.status == AgentStatus.COMPLETED
            assert result.response is not None
            assert result.structured_output is not None
            assert len(result.sources) > 0
            assert result.agent_type == AgentType.CONTRACT_ANALYST

    @pytest.mark.asyncio
    async def test_execution_tracking(self, mock_openai_client):
        """Testa rastreamento de execução."""
        from src.agents.execution_logger import ExecutionTracker

        with patch("src.agents.contract_analyst_agent.get_tool_registry"):
            tracker = ExecutionTracker()
            agent = ContractAnalystAgent(execution_tracker=tracker)
            agent._client = mock_openai_client

            chunks = create_mock_chunks(1)

            result = await agent.execute(
                query="Teste",
                client_id="cliente-123",
                metadata={"chunks": chunks},
            )

            # Verifica que a execução foi registrada
            tracked = tracker.get(result.execution_id)
            assert tracked is not None
            assert tracked.agent_type == AgentType.CONTRACT_ANALYST
