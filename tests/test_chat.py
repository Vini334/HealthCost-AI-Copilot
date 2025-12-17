"""
Testes para o endpoint de chat.

Testa:
- Validação de requisições
- Integração com o orquestrador
- Formatação de respostas
- Tratamento de erros
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.models.agents import AgentExecutionResult, AgentStatus, AgentType
from src.models.chat import ChatRequest, ChatResponse


# ============================================
# Fixtures
# ============================================


@pytest.fixture
def mock_orchestrator_result():
    """Resultado mock do orquestrador."""
    return AgentExecutionResult(
        execution_id="exec-123",
        agent_type=AgentType.ORCHESTRATOR,
        agent_name="orchestrator_agent",
        status=AgentStatus.COMPLETED,
        response="O prazo de carência para cirurgias é de 180 dias, conforme a Cláusula 5.2.",
        structured_output={
            "intent": "contract_query",
            "intent_confidence": 0.9,
            "agents_invoked": ["retrieval", "contract_analyst"],
            "execution_mode": "sequential",
        },
        sources=[
            {
                "document_id": "doc-456",
                "document_name": "Contrato_2024.pdf",
                "page_number": 12,
                "section_title": "Das Carências",
                "section_number": "5.2",
                "content": "O prazo de carência para cirurgias é de 180 dias...",
                "score": 0.95,
            }
        ],
        tokens_used=350,
        total_duration_ms=2345.6,
    )


@pytest.fixture
def mock_orchestrator_failed_result():
    """Resultado mock de falha do orquestrador."""
    return AgentExecutionResult(
        execution_id="exec-fail",
        agent_type=AgentType.ORCHESTRATOR,
        agent_name="orchestrator_agent",
        status=AgentStatus.FAILED,
        response=None,
        error="Erro ao conectar com o Azure OpenAI",
    )


@pytest.fixture
def mock_orchestrator(mock_orchestrator_result):
    """Mock do orquestrador."""
    orchestrator = MagicMock()
    orchestrator.execute = AsyncMock(return_value=mock_orchestrator_result)
    orchestrator.process_with_history = AsyncMock(return_value=mock_orchestrator_result)
    return orchestrator


# ============================================
# Testes de Validação de Request
# ============================================


class TestChatRequestValidation:
    """Testes de validação do ChatRequest."""

    def test_valid_request_minimal(self, client: TestClient):
        """Testa request válido com campos mínimos."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(
                return_value=AgentExecutionResult(
                    execution_id="test-123",
                    agent_type=AgentType.ORCHESTRATOR,
                    agent_name="orchestrator_agent",
                    status=AgentStatus.COMPLETED,
                    response="Resposta de teste",
                    structured_output={"intent": "general", "agents_invoked": []},
                )
            )
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Qual o prazo de carência?",
                    "client_id": "cliente-123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "conversation_id" in data
            assert "execution_id" in data

    def test_invalid_request_missing_message(self, client: TestClient):
        """Testa request inválido sem mensagem."""
        response = client.post(
            "/api/v1/chat/",
            json={
                "client_id": "cliente-123",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_invalid_request_missing_client_id(self, client: TestClient):
        """Testa request inválido sem client_id."""
        response = client.post(
            "/api/v1/chat/",
            json={
                "message": "Qual o prazo de carência?",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_invalid_request_empty_message(self, client: TestClient):
        """Testa request inválido com mensagem vazia."""
        response = client.post(
            "/api/v1/chat/",
            json={
                "message": "",
                "client_id": "cliente-123",
            },
        )

        assert response.status_code == 422  # Validation error


# ============================================
# Testes de Execução do Chat
# ============================================


class TestChatExecution:
    """Testes de execução do chat."""

    def test_chat_success(self, client: TestClient, mock_orchestrator_result):
        """Testa execução bem-sucedida do chat."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(return_value=mock_orchestrator_result)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Qual o prazo de carência?",
                    "client_id": "cliente-123",
                    "contract_id": "contrato-456",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["response"] == mock_orchestrator_result.response
            assert data["execution_id"] == mock_orchestrator_result.execution_id
            assert "conversation_id" in data
            assert "execution_time_ms" in data

    def test_chat_with_sources(self, client: TestClient, mock_orchestrator_result):
        """Testa chat com fontes incluídas."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(return_value=mock_orchestrator_result)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Qual o prazo de carência?",
                    "client_id": "cliente-123",
                    "include_sources": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "sources" in data
            assert len(data["sources"]) > 0
            assert data["sources"][0]["page_number"] == 12

    def test_chat_without_sources(self, client: TestClient, mock_orchestrator_result):
        """Testa chat sem fontes."""
        # Modificar resultado para não ter fontes quando não solicitado
        result_no_sources = AgentExecutionResult(
            execution_id="exec-123",
            agent_type=AgentType.ORCHESTRATOR,
            agent_name="orchestrator_agent",
            status=AgentStatus.COMPLETED,
            response="Resposta sem fontes",
            structured_output={"intent": "general", "agents_invoked": []},
            sources=[],
        )

        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(return_value=result_no_sources)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Qual o prazo de carência?",
                    "client_id": "cliente-123",
                    "include_sources": False,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["sources"] == []

    def test_chat_with_debug_trace(self, client: TestClient, mock_orchestrator_result):
        """Testa chat com trace de debug."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(return_value=mock_orchestrator_result)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Qual o prazo de carência?",
                    "client_id": "cliente-123",
                    "include_debug": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "agent_trace" in data
            # Pode ser None se não houver steps
            if data["agent_trace"]:
                assert "intent" in data["agent_trace"]
                assert "agents_invoked" in data["agent_trace"]

    def test_chat_with_conversation_history(self, client: TestClient, mock_orchestrator_result):
        """Testa chat com histórico de conversa."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.process_with_history = AsyncMock(return_value=mock_orchestrator_result)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "E para internações?",
                    "client_id": "cliente-123",
                    "conversation_history": [
                        {"role": "user", "content": "Qual o prazo de carência?"},
                        {"role": "assistant", "content": "O prazo de carência para cirurgias é 180 dias."},
                    ],
                },
            )

            assert response.status_code == 200
            mock_orch.process_with_history.assert_called_once()

    def test_chat_with_conversation_id(self, client: TestClient, mock_orchestrator_result):
        """Testa chat com conversation_id existente."""
        existing_conv_id = "conv-existing-123"

        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(return_value=mock_orchestrator_result)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Pergunta de continuação",
                    "client_id": "cliente-123",
                    "conversation_id": existing_conv_id,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["conversation_id"] == existing_conv_id


# ============================================
# Testes de Tratamento de Erros
# ============================================


class TestChatErrorHandling:
    """Testes de tratamento de erros."""

    def test_chat_orchestrator_failure(self, client: TestClient, mock_orchestrator_failed_result):
        """Testa resposta quando orquestrador falha."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(return_value=mock_orchestrator_failed_result)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Qual o prazo de carência?",
                    "client_id": "cliente-123",
                },
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_chat_unexpected_exception(self, client: TestClient):
        """Testa resposta para exceção inesperada."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_factory.side_effect = Exception("Erro inesperado de teste")

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Qual o prazo de carência?",
                    "client_id": "cliente-123",
                },
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Erro interno" in data["detail"]


# ============================================
# Testes do Endpoint Simplificado
# ============================================


class TestChatSimpleEndpoint:
    """Testes do endpoint simplificado."""

    def test_chat_simple_success(self, client: TestClient):
        """Testa o endpoint simplificado."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(
                return_value=AgentExecutionResult(
                    execution_id="simple-123",
                    agent_type=AgentType.ORCHESTRATOR,
                    agent_name="orchestrator_agent",
                    status=AgentStatus.COMPLETED,
                    response="Resposta simples",
                    structured_output={"intent": "general", "agents_invoked": []},
                )
            )
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/simple",
                params={
                    "message": "Teste simples",
                    "client_id": "cliente-123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Resposta simples"


# ============================================
# Testes de Formato de Resposta
# ============================================


class TestChatResponseFormat:
    """Testes de formato da resposta."""

    def test_response_has_required_fields(self, client: TestClient, mock_orchestrator_result):
        """Testa que a resposta tem todos os campos obrigatórios."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(return_value=mock_orchestrator_result)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Teste",
                    "client_id": "cliente-123",
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Campos obrigatórios
            required_fields = [
                "response",
                "conversation_id",
                "execution_id",
                "sources",
                "execution_time_ms",
                "created_at",
            ]

            for field in required_fields:
                assert field in data, f"Campo obrigatório '{field}' não encontrado"

    def test_response_execution_time_is_positive(self, client: TestClient, mock_orchestrator_result):
        """Testa que o tempo de execução é positivo."""
        with patch("src.api.routes.chat.create_orchestrator_agent") as mock_factory:
            mock_orch = MagicMock()
            mock_orch.execute = AsyncMock(return_value=mock_orchestrator_result)
            mock_factory.return_value = mock_orch

            response = client.post(
                "/api/v1/chat/",
                json={
                    "message": "Teste",
                    "client_id": "cliente-123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["execution_time_ms"] > 0
