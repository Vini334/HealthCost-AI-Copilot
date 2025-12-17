"""
Testes para o sistema de gerenciamento de conversas.

Testa:
- Modelos de conversa e mensagem
- Operações CRUD no CosmosDB (mockado)
- ConversationService
- Endpoints da API
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.models.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
)


# ============================================
# Testes dos Modelos
# ============================================


class TestConversationMessage:
    """Testes para o modelo ConversationMessage."""

    def test_create_user_message(self):
        """Testa criação de mensagem do usuário."""
        message = ConversationMessage(
            role=MessageRole.USER,
            content="Qual o prazo de carência?",
        )

        assert message.role == MessageRole.USER
        assert message.content == "Qual o prazo de carência?"
        assert message.id is not None
        assert message.created_at is not None

    def test_create_assistant_message_with_metadata(self):
        """Testa criação de mensagem do assistente com metadados."""
        message = ConversationMessage(
            role=MessageRole.ASSISTANT,
            content="O prazo de carência é 180 dias.",
            execution_id="exec-123",
            intent="contract_query",
            agents_invoked=["retrieval", "contract_analyst"],
            tokens_used=500,
            execution_time_ms=2345.6,
        )

        assert message.role == MessageRole.ASSISTANT
        assert message.execution_id == "exec-123"
        assert message.intent == "contract_query"
        assert message.agents_invoked == ["retrieval", "contract_analyst"]
        assert message.tokens_used == 500


class TestConversation:
    """Testes para o modelo Conversation."""

    def test_create_conversation(self):
        """Testa criação de conversa."""
        conversation = Conversation(
            client_id="cliente-123",
            contract_id="contrato-456",
        )

        assert conversation.client_id == "cliente-123"
        assert conversation.contract_id == "contrato-456"
        assert conversation.status == ConversationStatus.ACTIVE
        assert conversation.message_count == 0
        assert conversation.messages == []

    def test_add_user_message(self):
        """Testa adição de mensagem do usuário."""
        conversation = Conversation(client_id="cliente-123")

        message = conversation.add_user_message("Qual o prazo de carência?")

        assert conversation.message_count == 1
        assert len(conversation.messages) == 1
        assert message.role == MessageRole.USER
        assert message.content == "Qual o prazo de carência?"

    def test_add_assistant_message(self):
        """Testa adição de mensagem do assistente."""
        conversation = Conversation(client_id="cliente-123")

        message = conversation.add_assistant_message(
            content="O prazo é 180 dias.",
            execution_id="exec-123",
            intent="contract_query",
            tokens_used=500,
        )

        assert conversation.message_count == 1
        assert conversation.total_tokens_used == 500
        assert message.role == MessageRole.ASSISTANT

    def test_get_messages_for_context(self):
        """Testa obtenção de mensagens para contexto do LLM."""
        conversation = Conversation(client_id="cliente-123")
        conversation.add_user_message("Pergunta 1")
        conversation.add_assistant_message("Resposta 1")
        conversation.add_user_message("Pergunta 2")

        context = conversation.get_messages_for_context(max_messages=10)

        assert len(context) == 3
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"
        assert context[2]["role"] == "user"

    def test_get_messages_for_context_limit(self):
        """Testa limite de mensagens para contexto."""
        conversation = Conversation(client_id="cliente-123")
        for i in range(10):
            conversation.add_user_message(f"Pergunta {i}")
            conversation.add_assistant_message(f"Resposta {i}")

        context = conversation.get_messages_for_context(max_messages=5)

        assert len(context) == 5

    def test_generate_title(self):
        """Testa geração automática de título."""
        conversation = Conversation(client_id="cliente-123")
        conversation.add_user_message("Qual o prazo de carência para cirurgias?")

        title = conversation.generate_title()

        assert title == "Qual o prazo de carência para cirurgias?"

    def test_generate_title_truncated(self):
        """Testa truncamento do título gerado."""
        conversation = Conversation(client_id="cliente-123")
        long_message = "Esta é uma mensagem muito longa que deve ser truncada para gerar um título adequado"
        conversation.add_user_message(long_message)

        title = conversation.generate_title()

        assert len(title) <= 53  # 50 + "..."
        assert title.endswith("...")


# ============================================
# Testes do ConversationService
# ============================================


class TestConversationService:
    """Testes para o serviço de conversas."""

    @pytest.fixture
    def mock_cosmos_client(self):
        """Mock do cliente Cosmos DB."""
        with patch("src.services.conversation_service.get_cosmos_client") as mock:
            cosmos = MagicMock()
            cosmos.create_conversation = AsyncMock(return_value={})
            cosmos.get_conversation = AsyncMock(return_value=None)
            cosmos.update_conversation = AsyncMock(return_value={})
            cosmos.list_conversations_by_client = AsyncMock(return_value=([], 0))
            cosmos.delete_conversation = AsyncMock(return_value=True)
            mock.return_value = cosmos
            yield cosmos

    @pytest.fixture
    def conversation_service(self, mock_cosmos_client):
        """Fixture do ConversationService."""
        # Reset singleton
        import src.services.conversation_service as module
        module._conversation_service = None

        from src.services.conversation_service import ConversationService
        return ConversationService(cosmos_client=mock_cosmos_client)

    @pytest.mark.asyncio
    async def test_create_conversation(self, conversation_service, mock_cosmos_client):
        """Testa criação de conversa."""
        conversation = await conversation_service.create_conversation(
            client_id="cliente-123",
            contract_id="contrato-456",
        )

        assert conversation.client_id == "cliente-123"
        assert conversation.contract_id == "contrato-456"
        mock_cosmos_client.create_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conversation_with_initial_message(
        self, conversation_service, mock_cosmos_client
    ):
        """Testa criação de conversa com mensagem inicial."""
        conversation = await conversation_service.create_conversation(
            client_id="cliente-123",
            initial_message="Qual o prazo de carência?",
        )

        assert conversation.message_count == 1
        assert conversation.title is not None

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_new(
        self, conversation_service, mock_cosmos_client
    ):
        """Testa get_or_create quando conversa não existe."""
        mock_cosmos_client.get_conversation.return_value = None

        conversation = await conversation_service.get_or_create_conversation(
            client_id="cliente-123",
        )

        assert conversation is not None
        mock_cosmos_client.create_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_existing(
        self, conversation_service, mock_cosmos_client
    ):
        """Testa get_or_create quando conversa existe."""
        existing = Conversation(client_id="cliente-123")
        mock_cosmos_client.get_conversation.return_value = existing

        conversation = await conversation_service.get_or_create_conversation(
            client_id="cliente-123",
            conversation_id=str(existing.id),
        )

        assert conversation.id == existing.id
        mock_cosmos_client.create_conversation.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_user_message(self, conversation_service, mock_cosmos_client):
        """Testa adição de mensagem do usuário."""
        conversation = Conversation(client_id="cliente-123")

        message = await conversation_service.add_user_message(
            conversation=conversation,
            content="Qual o prazo?",
        )

        assert message.role == MessageRole.USER
        mock_cosmos_client.update_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_assistant_message(self, conversation_service, mock_cosmos_client):
        """Testa adição de mensagem do assistente."""
        conversation = Conversation(client_id="cliente-123")

        message = await conversation_service.add_assistant_message(
            conversation=conversation,
            content="O prazo é 180 dias.",
            execution_id="exec-123",
            tokens_used=500,
        )

        assert message.role == MessageRole.ASSISTANT
        assert message.tokens_used == 500
        mock_cosmos_client.update_conversation.assert_called_once()


# ============================================
# Testes dos Endpoints
# ============================================


class TestConversationsEndpoints:
    """Testes dos endpoints de conversas."""

    @pytest.fixture
    def mock_conversation_service(self):
        """Mock do serviço de conversas."""
        with patch("src.api.routes.conversations.get_conversation_service") as mock:
            service = MagicMock()
            mock.return_value = service
            yield service

    def test_list_conversations(self, client, mock_conversation_service):
        """Testa listagem de conversas."""
        # Arrange
        summary = ConversationSummary(
            id=uuid4(),
            client_id="cliente-123",
            title="Conversa teste",
            status=ConversationStatus.ACTIVE,
            message_count=5,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_conversation_service.list_conversations = AsyncMock(
            return_value=([summary], 1, False)
        )

        # Act
        response = client.get(
            "/api/v1/conversations/",
            params={"client_id": "cliente-123"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["title"] == "Conversa teste"

    def test_get_conversation(self, client, mock_conversation_service):
        """Testa obtenção de conversa."""
        # Arrange
        conversation = Conversation(
            client_id="cliente-123",
            title="Conversa teste",
        )
        conversation.add_user_message("Pergunta teste")

        mock_conversation_service.get_conversation = AsyncMock(
            return_value=conversation
        )

        # Act
        response = client.get(
            f"/api/v1/conversations/{conversation.id}",
            params={"client_id": "cliente-123"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Conversa teste"
        assert data["message_count"] == 1

    def test_get_conversation_not_found(self, client, mock_conversation_service):
        """Testa obtenção de conversa não existente."""
        mock_conversation_service.get_conversation = AsyncMock(return_value=None)

        response = client.get(
            "/api/v1/conversations/nonexistent-id",
            params={"client_id": "cliente-123"},
        )

        assert response.status_code == 404

    def test_create_conversation(self, client, mock_conversation_service):
        """Testa criação de conversa."""
        conversation = Conversation(
            client_id="cliente-123",
            title="Nova conversa",
        )
        mock_conversation_service.create_conversation = AsyncMock(
            return_value=conversation
        )

        response = client.post(
            "/api/v1/conversations/",
            json={
                "client_id": "cliente-123",
                "title": "Nova conversa",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Nova conversa"

    def test_delete_conversation(self, client, mock_conversation_service):
        """Testa remoção de conversa."""
        mock_conversation_service.delete_conversation = AsyncMock(return_value=True)

        response = client.delete(
            "/api/v1/conversations/conv-123",
            params={"client_id": "cliente-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Conversa removida com sucesso"

    def test_delete_conversation_not_found(self, client, mock_conversation_service):
        """Testa remoção de conversa não existente."""
        mock_conversation_service.delete_conversation = AsyncMock(return_value=False)

        response = client.delete(
            "/api/v1/conversations/nonexistent",
            params={"client_id": "cliente-123"},
        )

        assert response.status_code == 404


# ============================================
# Testes de Integração Chat + Conversas
# ============================================


class TestChatWithConversations:
    """Testes de integração entre chat e conversas."""

    @pytest.fixture
    def mock_services(self):
        """Mock dos serviços."""
        with patch("src.api.routes.chat.get_conversation_service") as conv_mock, \
             patch("src.api.routes.chat.create_orchestrator_agent") as orch_mock:

            # Mock do serviço de conversas
            conv_service = MagicMock()
            conversation = Conversation(client_id="cliente-123")
            conv_service.get_or_create_conversation = AsyncMock(return_value=conversation)
            conv_service.add_user_message = AsyncMock(
                return_value=ConversationMessage(role=MessageRole.USER, content="test")
            )
            conv_service.add_assistant_message = AsyncMock(
                return_value=ConversationMessage(role=MessageRole.ASSISTANT, content="response")
            )
            conv_mock.return_value = conv_service

            # Mock do orquestrador
            from src.models.agents import AgentExecutionResult, AgentStatus, AgentType
            orchestrator = MagicMock()
            orchestrator.execute = AsyncMock(
                return_value=AgentExecutionResult(
                    execution_id="exec-123",
                    agent_type=AgentType.ORCHESTRATOR,
                    agent_name="orchestrator",
                    status=AgentStatus.COMPLETED,
                    response="Resposta teste",
                    structured_output={"intent": "general", "agents_invoked": []},
                )
            )
            orch_mock.return_value = orchestrator

            yield {
                "conv_service": conv_service,
                "orchestrator": orchestrator,
                "conversation": conversation,
            }

    def test_chat_creates_conversation(self, client, mock_services):
        """Testa que chat cria conversa automaticamente."""
        response = client.post(
            "/api/v1/chat/",
            json={
                "message": "Qual o prazo de carência?",
                "client_id": "cliente-123",
            },
        )

        assert response.status_code == 200
        mock_services["conv_service"].get_or_create_conversation.assert_called_once()

    def test_chat_adds_messages(self, client, mock_services):
        """Testa que chat adiciona mensagens à conversa."""
        response = client.post(
            "/api/v1/chat/",
            json={
                "message": "Qual o prazo de carência?",
                "client_id": "cliente-123",
            },
        )

        assert response.status_code == 200
        mock_services["conv_service"].add_user_message.assert_called_once()
        mock_services["conv_service"].add_assistant_message.assert_called_once()

    def test_chat_returns_conversation_id(self, client, mock_services):
        """Testa que chat retorna conversation_id."""
        response = client.post(
            "/api/v1/chat/",
            json={
                "message": "Qual o prazo de carência?",
                "client_id": "cliente-123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert data["conversation_id"] == str(mock_services["conversation"].id)
