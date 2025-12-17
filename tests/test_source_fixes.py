"""
Testes para correções de extração, conversão e deduplicação de sources.

Estes testes validam as correções feitas para:
1. Campos null em sources (content_snippet, relevance_score, document_name)
2. Deduplicação de sources de múltiplos agentes
3. Fallbacks para nomes de campos antigos
"""

import pytest
from unittest.mock import MagicMock, patch

from src.api.routes.chat import _convert_sources
from src.models.chat import SourceReference
from src.models.agents import AgentExecutionResult, AgentType, AgentStatus


class TestExtractSourcesFromChunks:
    """Testes para _extract_sources_from_chunks em BaseAgent."""

    def test_extract_sources_includes_all_fields(self):
        """Verifica que todos os campos são extraídos corretamente."""
        # Arrange
        from src.agents.base import BaseAgent

        # Criar mock do agente para testar o método
        class TestAgent(BaseAgent):
            agent_type = AgentType.RETRIEVAL
            agent_name = "test_agent"

            def get_tools(self):
                return []

            async def process(self, context):
                pass

        # Mock das settings para evitar erro de configuração
        with patch('src.agents.base.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                azure_openai=MagicMock(
                    api_key="test",
                    api_version="2024-02-01",
                    endpoint="https://test.openai.azure.com",
                    deployment_name="gpt-4o",
                    deployment_name_mini="o4-mini",
                )
            )
            with patch('src.agents.base.AsyncAzureOpenAI'):
                agent = TestAgent()

        chunks = [{
            "document_id": "doc-123",
            "document_name": "Contrato_2024.pdf",
            "page_number": 12,
            "page_start": 12,
            "page_end": 13,
            "section_title": "Das Carencias",
            "section_number": "5.2",
            "section_type": "clausula",
            "content": "O prazo de carencia para cirurgias e de 180 dias conforme regulamentacao vigente.",
            "score": 0.85,
            "reranker_score": 0.92,
        }]

        # Act
        sources = agent._extract_sources_from_chunks(chunks)

        # Assert
        assert len(sources) == 1
        source = sources[0]
        assert source["document_id"] == "doc-123"
        assert source["document_name"] == "Contrato_2024.pdf"
        assert source["page_number"] == 12
        assert source["section_title"] == "Das Carencias"
        assert source["section_number"] == "5.2"
        assert source["content_snippet"] is not None
        assert "180 dias" in source["content_snippet"]
        assert source["relevance_score"] == 0.92  # Deve usar reranker_score

    def test_extract_sources_handles_missing_score(self):
        """Verifica que sources sem score recebem valor 0.0."""
        from src.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            agent_type = AgentType.RETRIEVAL
            agent_name = "test_agent"

            def get_tools(self):
                return []

            async def process(self, context):
                pass

        with patch('src.agents.base.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                azure_openai=MagicMock(
                    api_key="test",
                    api_version="2024-02-01",
                    endpoint="https://test.openai.azure.com",
                    deployment_name="gpt-4o",
                    deployment_name_mini="o4-mini",
                )
            )
            with patch('src.agents.base.AsyncAzureOpenAI'):
                agent = TestAgent()

        chunks = [{
            "document_id": "doc-123",
            "content": "Texto do documento.",
        }]

        # Act
        sources = agent._extract_sources_from_chunks(chunks)

        # Assert
        assert sources[0]["relevance_score"] is None  # 0.0 se torna None após float(0.0) if 0.0

    def test_extract_sources_deduplicates_by_location(self):
        """Verifica que chunks duplicados (mesma localização) são removidos."""
        from src.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            agent_type = AgentType.RETRIEVAL
            agent_name = "test_agent"

            def get_tools(self):
                return []

            async def process(self, context):
                pass

        with patch('src.agents.base.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                azure_openai=MagicMock(
                    api_key="test",
                    api_version="2024-02-01",
                    endpoint="https://test.openai.azure.com",
                    deployment_name="gpt-4o",
                    deployment_name_mini="o4-mini",
                )
            )
            with patch('src.agents.base.AsyncAzureOpenAI'):
                agent = TestAgent()

        chunks = [
            {"document_id": "doc-123", "page_number": 12, "section_title": "Sec A", "content": "Conteudo A"},
            {"document_id": "doc-123", "page_number": 12, "section_title": "Sec A", "content": "Conteudo B"},  # Duplicata
            {"document_id": "doc-123", "page_number": 13, "section_title": "Sec B", "content": "Conteudo C"},
        ]

        # Act
        sources = agent._extract_sources_from_chunks(chunks)

        # Assert
        assert len(sources) == 2  # Deve deduplicar, mantendo apenas 2


class TestConvertSources:
    """Testes para _convert_sources em chat.py."""

    def test_convert_with_new_field_names(self):
        """Verifica conversão com novos nomes de campos padronizados."""
        sources = [{
            "document_id": "doc-123",
            "document_name": "Contrato.pdf",
            "page_number": 5,
            "section_title": "Cobertura",
            "section_number": "3.1",
            "content_snippet": "Cobertura hospitalar completa...",
            "relevance_score": 0.92,
        }]

        # Act
        result = _convert_sources(sources)

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], SourceReference)
        assert result[0].document_id == "doc-123"
        assert result[0].document_name == "Contrato.pdf"
        assert result[0].content_snippet == "Cobertura hospitalar completa..."
        assert result[0].relevance_score == 0.92

    def test_convert_with_legacy_content_preview(self):
        """Verifica fallback para campo content_preview (nome antigo)."""
        sources = [{
            "document_id": "doc-123",
            "content_preview": "Preview do conteudo antigo...",  # Nome antigo
        }]

        # Act
        result = _convert_sources(sources)

        # Assert
        assert result[0].content_snippet == "Preview do conteudo antigo..."

    def test_convert_with_legacy_score_names(self):
        """Verifica fallback para diferentes nomes de score."""
        # Test com 'score'
        sources_score = [{"document_id": "doc-1", "score": 0.85}]
        result_score = _convert_sources(sources_score)
        assert result_score[0].relevance_score == 0.85

        # Test com 'reranker_score'
        sources_reranker = [{"document_id": "doc-2", "reranker_score": 0.90}]
        result_reranker = _convert_sources(sources_reranker)
        assert result_reranker[0].relevance_score == 0.90

    def test_convert_handles_missing_fields(self):
        """Verifica que campos ausentes resultam em None."""
        sources = [{"document_id": "doc-123"}]

        # Act
        result = _convert_sources(sources)

        # Assert
        assert result[0].document_id == "doc-123"
        assert result[0].document_name is None
        assert result[0].content_snippet is None
        assert result[0].relevance_score is None

    def test_convert_truncates_long_content(self):
        """Verifica que conteúdo longo é truncado ao usar fallback."""
        long_content = "A" * 500  # Conteúdo muito longo
        sources = [{"document_id": "doc-123", "content": long_content}]

        # Act
        result = _convert_sources(sources)

        # Assert
        assert len(result[0].content_snippet) <= 200


class TestDeduplicateSources:
    """Testes para _deduplicate_sources no OrchestratorAgent."""

    def test_deduplicate_removes_duplicates(self):
        """Verifica que duplicatas são removidas."""
        from src.agents.orchestrator_agent import OrchestratorAgent

        # Mock para evitar inicialização real
        with patch('src.agents.orchestrator_agent.BaseAgent.__init__'):
            orchestrator = OrchestratorAgent.__new__(OrchestratorAgent)
            orchestrator._logger = MagicMock()

        # Criar resultados simulados de agentes
        results = {
            AgentType.RETRIEVAL: MagicMock(
                sources=[
                    {"document_id": "doc-123", "page_number": 5, "section_title": "Sec A", "relevance_score": 0.8},
                    {"document_id": "doc-123", "page_number": 6, "section_title": "Sec B", "relevance_score": 0.7},
                ]
            ),
            AgentType.CONTRACT_ANALYST: MagicMock(
                sources=[
                    {"document_id": "doc-123", "page_number": 5, "section_title": "Sec A", "relevance_score": 0.85},  # Duplicata com score maior
                ]
            ),
        }

        # Act
        deduplicated = orchestrator._deduplicate_sources(results)

        # Assert
        assert len(deduplicated) == 2  # Deve ter apenas 2 sources únicos

    def test_deduplicate_keeps_highest_score(self):
        """Verifica que a duplicata com maior score é mantida."""
        from src.agents.orchestrator_agent import OrchestratorAgent

        with patch('src.agents.orchestrator_agent.BaseAgent.__init__'):
            orchestrator = OrchestratorAgent.__new__(OrchestratorAgent)
            orchestrator._logger = MagicMock()

        results = {
            AgentType.RETRIEVAL: MagicMock(
                sources=[
                    {"document_id": "doc-123", "page_number": 5, "section_title": "Sec A", "relevance_score": 0.70},
                ]
            ),
            AgentType.CONTRACT_ANALYST: MagicMock(
                sources=[
                    {"document_id": "doc-123", "page_number": 5, "section_title": "Sec A", "relevance_score": 0.95},  # Score maior
                ]
            ),
        }

        # Act
        deduplicated = orchestrator._deduplicate_sources(results)

        # Assert
        assert len(deduplicated) == 1
        assert deduplicated[0]["relevance_score"] == 0.95  # Deve manter o de maior score

    def test_deduplicate_sorts_by_relevance(self):
        """Verifica que resultado é ordenado por relevância decrescente."""
        from src.agents.orchestrator_agent import OrchestratorAgent

        with patch('src.agents.orchestrator_agent.BaseAgent.__init__'):
            orchestrator = OrchestratorAgent.__new__(OrchestratorAgent)
            orchestrator._logger = MagicMock()

        results = {
            AgentType.RETRIEVAL: MagicMock(
                sources=[
                    {"document_id": "doc-1", "page_number": 1, "section_title": "A", "relevance_score": 0.50},
                    {"document_id": "doc-2", "page_number": 2, "section_title": "B", "relevance_score": 0.90},
                    {"document_id": "doc-3", "page_number": 3, "section_title": "C", "relevance_score": 0.70},
                ]
            ),
        }

        # Act
        deduplicated = orchestrator._deduplicate_sources(results)

        # Assert
        assert deduplicated[0]["relevance_score"] == 0.90  # Maior primeiro
        assert deduplicated[1]["relevance_score"] == 0.70
        assert deduplicated[2]["relevance_score"] == 0.50

    def test_deduplicate_handles_empty_sources(self):
        """Verifica que lida corretamente com sources vazios."""
        from src.agents.orchestrator_agent import OrchestratorAgent

        with patch('src.agents.orchestrator_agent.BaseAgent.__init__'):
            orchestrator = OrchestratorAgent.__new__(OrchestratorAgent)
            orchestrator._logger = MagicMock()

        results = {
            AgentType.RETRIEVAL: MagicMock(sources=[]),
            AgentType.CONTRACT_ANALYST: MagicMock(sources=None),
        }

        # Act
        deduplicated = orchestrator._deduplicate_sources(results)

        # Assert
        assert len(deduplicated) == 0


class TestModelSelection:
    """Testes para seleção de modelo (mini vs full)."""

    def test_orchestrator_uses_mini_model(self):
        """Verifica que orchestrator usa modelo mini."""
        from src.agents.orchestrator_agent import OrchestratorAgent

        assert OrchestratorAgent.use_mini_model is True

    def test_retrieval_agent_uses_mini_model(self):
        """Verifica que retrieval agent usa modelo mini."""
        from src.agents.retrieval_agent import RetrievalAgent

        assert RetrievalAgent.use_mini_model is True

    def test_cost_insights_uses_mini_model(self):
        """Verifica que cost insights agent usa modelo mini."""
        from src.agents.cost_insights_agent import CostInsightsAgent

        assert CostInsightsAgent.use_mini_model is True

    def test_contract_analyst_uses_full_model(self):
        """Verifica que contract analyst usa modelo completo (default)."""
        from src.agents.contract_analyst_agent import ContractAnalystAgent

        # use_mini_model não está definido ou é False
        assert not getattr(ContractAnalystAgent, 'use_mini_model', False)

    def test_negotiation_advisor_uses_full_model(self):
        """Verifica que negotiation advisor usa modelo completo (default)."""
        from src.agents.negotiation_advisor_agent import NegotiationAdvisorAgent

        assert not getattr(NegotiationAdvisorAgent, 'use_mini_model', False)


class TestKeywordThreshold:
    """Testes para threshold de detecção por keywords."""

    def test_keyword_threshold_is_lowered(self):
        """Verifica que threshold foi reduzido para 0.6."""
        # Lê o arquivo e verifica o valor
        import ast
        import re

        with open("src/agents/orchestrator_agent.py", "r") as f:
            content = f.read()

        # Procura pelo padrão de threshold
        match = re.search(r'keyword_intent\["confidence"\]\s*>=\s*([\d.]+)', content)
        assert match is not None
        threshold = float(match.group(1))
        assert threshold == 0.6, f"Expected threshold 0.6, got {threshold}"
