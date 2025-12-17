"""
Testes para o sistema de contexto de conversas.

Testa:
- TokenCounter: contagem e truncamento de tokens
- ConversationSummarizer: sumarização de conversas
- Conversation: métodos de gerenciamento de contexto
- ConversationService: get_conversation_context()
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.utils.token_counter import TokenCounter, get_token_counter, count_tokens
from src.models.conversations import (
    Conversation,
    ConversationMessage,
    MessageRole,
    ConversationStatus,
)


# ============================================
# Testes para TokenCounter
# ============================================


class TestTokenCounter:
    """Testes para o contador de tokens."""

    def test_count_tokens_empty_string(self):
        """Testa contagem de string vazia."""
        counter = TokenCounter()
        assert counter.count_tokens("") == 0

    def test_count_tokens_simple_text(self):
        """Testa contagem de texto simples."""
        counter = TokenCounter()
        tokens = counter.count_tokens("Olá, como posso ajudar?")
        # Deve retornar valor > 0
        assert tokens > 0

    def test_count_tokens_long_text(self):
        """Testa contagem de texto longo."""
        counter = TokenCounter()
        long_text = "Esta é uma frase de teste. " * 100
        tokens = counter.count_tokens(long_text)
        # Texto longo deve ter muitos tokens
        assert tokens > 100

    def test_count_messages_tokens_empty_list(self):
        """Testa contagem de lista vazia de mensagens."""
        counter = TokenCounter()
        assert counter.count_messages_tokens([]) == 0

    def test_count_messages_tokens_single_message(self):
        """Testa contagem de uma mensagem."""
        counter = TokenCounter()
        messages = [{"role": "user", "content": "Olá!"}]
        tokens = counter.count_messages_tokens(messages)
        assert tokens > 0

    def test_count_messages_tokens_multiple_messages(self):
        """Testa contagem de múltiplas mensagens."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Qual a carência?"},
            {"role": "assistant", "content": "A carência é de 180 dias."},
            {"role": "user", "content": "E para internações?"},
        ]
        tokens = counter.count_messages_tokens(messages)
        assert tokens > 10  # Deve ter pelo menos alguns tokens

    def test_truncate_messages_to_fit_no_truncation_needed(self):
        """Testa truncamento quando não é necessário."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Olá!"},
            {"role": "assistant", "content": "Oi!"},
        ]
        result = counter.truncate_messages_to_fit(
            messages=messages,
            max_tokens=1000,
        )
        assert len(result) == len(messages)

    def test_truncate_messages_to_fit_with_truncation(self):
        """Testa truncamento quando necessário."""
        counter = TokenCounter()
        # Criar muitas mensagens
        messages = [
            {"role": "user", "content": f"Mensagem {i} " * 50}
            for i in range(20)
        ]
        result = counter.truncate_messages_to_fit(
            messages=messages,
            max_tokens=500,
            reserve_for_response=100,
        )
        # Deve ter menos mensagens que o original
        assert len(result) < len(messages)

    def test_truncate_messages_preserves_recent(self):
        """Testa que mensagens recentes são preservadas."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": f"Mensagem antiga {i} " * 50}
            for i in range(10)
        ] + [
            {"role": "user", "content": "Mensagem recente 1"},
            {"role": "user", "content": "Mensagem recente 2"},
        ]
        result = counter.truncate_messages_to_fit(
            messages=messages,
            max_tokens=200,
            preserve_recent=2,
        )
        # As últimas mensagens devem estar presentes
        assert any("recente 1" in m["content"] for m in result) or \
               any("recente 2" in m["content"] for m in result)

    def test_estimate_response_tokens(self):
        """Testa estimativa de tokens para resposta."""
        counter = TokenCounter()
        assert counter.estimate_response_tokens("short") == 200
        assert counter.estimate_response_tokens("medium") == 500
        assert counter.estimate_response_tokens("long") == 1000

    def test_calculate_available_context(self):
        """Testa cálculo de contexto disponível."""
        counter = TokenCounter()
        available = counter.calculate_available_context(
            model_context_window=128000,
            system_prompt_tokens=500,
            response_reserve=2000,
        )
        assert available == 128000 - 500 - 2000

    def test_split_text_into_chunks(self):
        """Testa divisão de texto em chunks."""
        counter = TokenCounter()
        text = "Parágrafo 1.\n\nParágrafo 2.\n\nParágrafo 3."
        chunks = counter.split_text_into_chunks(
            text=text,
            max_tokens_per_chunk=100,
        )
        assert len(chunks) >= 1

    def test_singleton_get_token_counter(self):
        """Testa que get_token_counter retorna singleton."""
        counter1 = get_token_counter()
        counter2 = get_token_counter()
        assert counter1 is counter2

    def test_convenience_function_count_tokens(self):
        """Testa função de conveniência count_tokens."""
        tokens = count_tokens("Teste de contagem")
        assert tokens > 0


# ============================================
# Testes para Conversation (métodos de contexto)
# ============================================


class TestConversationContextMethods:
    """Testes para métodos de contexto da Conversation."""

    def create_test_conversation(self, message_count: int = 5) -> Conversation:
        """Cria uma conversa de teste com N mensagens."""
        conversation = Conversation(
            client_id="test-client",
            contract_id="test-contract",
        )
        for i in range(message_count):
            if i % 2 == 0:
                conversation.add_user_message(f"Pergunta {i}")
            else:
                conversation.add_assistant_message(f"Resposta {i}")
        return conversation

    def test_get_summaries_empty(self):
        """Testa get_summaries com conversa sem resumos."""
        conversation = self.create_test_conversation()
        summaries = conversation.get_summaries()
        assert summaries == []

    def test_add_summary(self):
        """Testa adicionar resumo."""
        conversation = self.create_test_conversation()
        summary = {
            "message_range": [0, 5],
            "summary_text": "Resumo da conversa",
            "key_entities": {"topics": ["carência"]},
        }
        conversation.add_summary(summary)
        summaries = conversation.get_summaries()
        assert len(summaries) == 1
        assert summaries[0]["summary_text"] == "Resumo da conversa"

    def test_get_last_summary_index_no_summaries(self):
        """Testa índice sem resumos."""
        conversation = self.create_test_conversation()
        assert conversation.get_last_summary_index() == 0

    def test_get_last_summary_index_with_summaries(self):
        """Testa índice com resumos."""
        conversation = self.create_test_conversation(10)
        conversation.add_summary({"message_range": [0, 5]})
        conversation.add_summary({"message_range": [5, 8]})
        assert conversation.get_last_summary_index() == 8

    def test_get_unsummarized_messages(self):
        """Testa obter mensagens não resumidas."""
        conversation = self.create_test_conversation(10)
        conversation.add_summary({"message_range": [0, 5]})
        unsummarized = conversation.get_unsummarized_messages()
        assert len(unsummarized) == 5

    def test_get_message_by_id(self):
        """Testa busca de mensagem por ID."""
        conversation = self.create_test_conversation(3)
        target_msg = conversation.messages[1]
        found = conversation.get_message_by_id(target_msg.id)
        assert found is not None
        assert found.id == target_msg.id

    def test_get_message_by_id_not_found(self):
        """Testa busca com ID inexistente."""
        conversation = self.create_test_conversation(3)
        found = conversation.get_message_by_id(uuid4())
        assert found is None

    def test_get_message_index(self):
        """Testa obter índice de mensagem."""
        conversation = self.create_test_conversation(5)
        msg = conversation.messages[2]
        idx = conversation.get_message_index(msg.id)
        assert idx == 2

    def test_get_messages_in_range(self):
        """Testa obter mensagens em intervalo."""
        conversation = self.create_test_conversation(10)
        messages = conversation.get_messages_in_range(2, 5)
        assert len(messages) == 3

    def test_get_context_window_no_summary(self):
        """Testa janela de contexto sem resumo."""
        conversation = self.create_test_conversation(5)
        context = conversation.get_context_window(include_summary=True)
        assert context["summary"] is None
        assert len(context["recent_messages"]) == 5

    def test_get_context_window_with_summary(self):
        """Testa janela de contexto com resumo."""
        conversation = self.create_test_conversation(10)
        conversation.add_summary({
            "message_range": [0, 5],
            "summary_text": "Resumo das primeiras mensagens",
        })
        context = conversation.get_context_window(include_summary=True)
        assert context["summary"] == "Resumo das primeiras mensagens"
        # Mensagens recentes devem ser as não resumidas
        assert len(context["recent_messages"]) == 5

    def test_get_context_window_max_recent_messages(self):
        """Testa limite de mensagens recentes."""
        conversation = self.create_test_conversation(20)
        context = conversation.get_context_window(
            include_summary=False,
            max_recent_messages=5,
        )
        assert len(context["recent_messages"]) == 5

    def test_find_messages_by_content(self):
        """Testa busca por conteúdo."""
        conversation = Conversation(client_id="test")
        conversation.add_user_message("Qual a carência?")
        conversation.add_assistant_message("A carência é de 180 dias.")
        conversation.add_user_message("E para cirurgias?")

        found = conversation.find_messages_by_content("carência")
        assert len(found) == 2  # Deve encontrar nas duas mensagens

    def test_get_messages_around(self):
        """Testa obter mensagens ao redor."""
        conversation = self.create_test_conversation(10)
        center_msg = conversation.messages[5]
        around = conversation.get_messages_around(center_msg.id, window=2)
        # Deve ter 5 mensagens (2 antes, centro, 2 depois)
        assert len(around) == 5

    def test_referenced_message_ids_field(self):
        """Testa campo de referências em mensagem."""
        msg = ConversationMessage(
            role=MessageRole.ASSISTANT,
            content="Com base na sua pergunta anterior...",
            referenced_message_ids=[uuid4(), uuid4()],
        )
        assert len(msg.referenced_message_ids) == 2


# ============================================
# Testes para ConversationSummarizer
# ============================================


class TestConversationSummarizer:
    """Testes para o sumarizador de conversas."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock do cliente OpenAI."""
        with patch("src.services.conversation_summarizer.AsyncAzureOpenAI") as mock:
            mock_instance = MagicMock()
            mock_instance.chat = MagicMock()
            mock_instance.chat.completions = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_needs_summarization_few_messages(self):
        """Testa que poucas mensagens não precisam de resumo."""
        from src.services.conversation_summarizer import ConversationSummarizer

        with patch("src.services.conversation_summarizer.AsyncAzureOpenAI"):
            summarizer = ConversationSummarizer(summary_trigger_messages=20)

            conversation = Conversation(client_id="test")
            for i in range(5):
                conversation.add_user_message(f"Mensagem {i}")

            assert summarizer.needs_summarization(conversation) is False

    def test_needs_summarization_many_messages(self):
        """Testa que muitas mensagens precisam de resumo."""
        from src.services.conversation_summarizer import ConversationSummarizer

        with patch("src.services.conversation_summarizer.AsyncAzureOpenAI"):
            summarizer = ConversationSummarizer(summary_trigger_messages=5)

            conversation = Conversation(client_id="test")
            for i in range(10):
                conversation.add_user_message(f"Mensagem {i}")

            assert summarizer.needs_summarization(conversation) is True

    def test_needs_summarization_with_existing_summaries(self):
        """Testa com resumos existentes."""
        from src.services.conversation_summarizer import ConversationSummarizer, ConversationSummary

        with patch("src.services.conversation_summarizer.AsyncAzureOpenAI"):
            summarizer = ConversationSummarizer(summary_trigger_messages=5)

            conversation = Conversation(client_id="test")
            for i in range(10):
                conversation.add_user_message(f"Mensagem {i}")

            # Criar resumo existente
            existing = ConversationSummary(
                conversation_id=conversation.id,
                message_range=(0, 8),
                summary_text="Resumo existente",
            )

            # Com resumo até índice 8, só restam 2 mensagens não resumidas
            assert summarizer.needs_summarization(conversation, [existing]) is False

    def test_build_context_with_summary(self):
        """Testa construção de contexto com resumo."""
        from src.services.conversation_summarizer import ConversationSummarizer, ConversationSummary

        with patch("src.services.conversation_summarizer.AsyncAzureOpenAI"):
            summarizer = ConversationSummarizer()

            conversation = Conversation(client_id="test")
            for i in range(10):
                conversation.add_user_message(f"Mensagem {i}")

            summaries = [
                ConversationSummary(
                    conversation_id=conversation.id,
                    message_range=(0, 5),
                    summary_text="Resumo das primeiras mensagens",
                    key_entities={"topics": ["carência"]},
                )
            ]

            context = summarizer.build_context_with_summary(
                conversation=conversation,
                summaries=summaries,
                max_context_tokens=8000,
            )

            assert context["summary"] == "Resumo das primeiras mensagens"
            assert len(context["recent_messages"]) == 5  # Mensagens após índice 5
            assert context["key_entities"]["topics"] == ["carência"]

    @pytest.mark.asyncio
    async def test_summarize_conversation(self, mock_openai_client):
        """Testa geração de resumo."""
        from src.services.conversation_summarizer import ConversationSummarizer

        # Configurar mock para retornar resumo
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Este é o resumo da conversa."

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("src.services.conversation_summarizer.AsyncAzureOpenAI", return_value=mock_openai_client):
            summarizer = ConversationSummarizer()

            conversation = Conversation(client_id="test")
            for i in range(5):
                conversation.add_user_message(f"Pergunta {i}")
                conversation.add_assistant_message(f"Resposta {i}")

            summary = await summarizer.summarize_conversation(
                conversation=conversation,
                extract_entities=False,
            )

            assert summary.summary_text == "Este é o resumo da conversa."
            assert summary.message_range == (0, 10)


# ============================================
# Testes para ConversationService (contexto)
# ============================================


class TestConversationServiceContext:
    """Testes para métodos de contexto do ConversationService."""

    @pytest.fixture
    def mock_cosmos_client(self):
        """Mock do cliente Cosmos DB."""
        mock = MagicMock()
        mock.update_conversation = AsyncMock()
        return mock

    def test_get_messages_for_context(self, mock_cosmos_client):
        """Testa método existente get_messages_for_context."""
        from src.services.conversation_service import ConversationService

        with patch("src.services.conversation_service.get_cosmos_client", return_value=mock_cosmos_client):
            service = ConversationService()

            conversation = Conversation(client_id="test")
            conversation.add_user_message("Pergunta 1")
            conversation.add_assistant_message("Resposta 1")
            conversation.add_user_message("Pergunta 2")

            messages = service.get_messages_for_context(conversation, max_messages=2)
            assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_get_conversation_context_no_history(self, mock_cosmos_client):
        """Testa get_conversation_context sem histórico."""
        from src.services.conversation_service import ConversationService

        with patch("src.services.conversation_service.get_cosmos_client", return_value=mock_cosmos_client):
            service = ConversationService()

            conversation = Conversation(client_id="test")
            conversation.add_user_message("Primeira mensagem")

            context = await service.get_conversation_context(
                conversation=conversation,
                auto_summarize=False,
            )

            assert context["summary"] is None
            assert len(context["messages"]) == 1
            assert context["has_summary"] is False

    @pytest.mark.asyncio
    async def test_get_conversation_context_with_summary(self, mock_cosmos_client):
        """Testa get_conversation_context com resumo existente."""
        from src.services.conversation_service import ConversationService

        with patch("src.services.conversation_service.get_cosmos_client", return_value=mock_cosmos_client):
            service = ConversationService()

            conversation = Conversation(client_id="test")
            for i in range(10):
                conversation.add_user_message(f"Mensagem {i}")

            # Adicionar resumo
            conversation.add_summary({
                "message_range": [0, 5],
                "summary_text": "Resumo existente",
                "key_entities": {"topics": ["teste"]},
            })

            context = await service.get_conversation_context(
                conversation=conversation,
                auto_summarize=False,
            )

            assert context["summary"] == "Resumo existente"
            assert context["has_summary"] is True
            assert context["key_entities"]["topics"] == ["teste"]
            # Mensagens recentes (após índice 5)
            assert len(context["messages"]) == 5

    @pytest.mark.asyncio
    async def test_search_in_conversation(self, mock_cosmos_client):
        """Testa busca em conversa."""
        from src.services.conversation_service import ConversationService

        with patch("src.services.conversation_service.get_cosmos_client", return_value=mock_cosmos_client):
            service = ConversationService()

            conversation = Conversation(client_id="test")
            conversation.add_user_message("Qual a carência para cirurgias?")
            conversation.add_assistant_message("A carência é de 180 dias.")
            conversation.add_user_message("E para consultas?")

            results = await service.search_in_conversation(
                conversation=conversation,
                search_text="carência",
            )

            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_referenced_messages(self, mock_cosmos_client):
        """Testa recuperação de mensagens referenciadas."""
        from src.services.conversation_service import ConversationService

        with patch("src.services.conversation_service.get_cosmos_client", return_value=mock_cosmos_client):
            service = ConversationService()

            conversation = Conversation(client_id="test")
            conversation.add_user_message("Mensagem 1")
            conversation.add_assistant_message("Resposta 1")
            conversation.add_user_message("Mensagem 2")

            msg_id = str(conversation.messages[1].id)

            results = await service.get_referenced_messages(
                conversation=conversation,
                message_ids=[msg_id],
                include_context=True,
            )

            assert len(results) == 1
            assert "target_message" in results[0]
            assert "context" in results[0]
