"""
Serviço de sumarização de conversas.

Responsável por:
- Gerar resumos de conversas longas
- Manter contexto em conversas extensas
- Extrair informações-chave de históricos
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from openai import AsyncAzureOpenAI

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.models.conversations import (
    Conversation,
    ConversationMessage,
    MessageRole,
)
from src.utils.token_counter import TokenCounter, get_token_counter

logger = get_logger(__name__)


# Prompt para sumarização de conversas
SUMMARIZATION_SYSTEM_PROMPT = """Você é um assistente especializado em resumir conversas sobre planos de saúde corporativos.

Sua tarefa é criar um resumo conciso e informativo da conversa, preservando:
1. **Tópicos discutidos**: Os principais assuntos abordados
2. **Informações importantes**: Dados específicos mencionados (valores, datas, cláusulas)
3. **Decisões tomadas**: Conclusões ou acordos alcançados
4. **Perguntas pendentes**: Dúvidas que ainda precisam ser respondidas
5. **Contexto relevante**: Informações que podem ser úteis para continuidade

Formato do resumo:
- Seja conciso mas completo
- Use tópicos para organizar informações
- Mantenha nomes de entidades (contratos, procedimentos, valores)
- Preserve números e datas exatos
- Indique claramente se algo ficou em aberto

O resumo será usado para dar contexto em mensagens futuras da mesma conversa."""


# Prompt para extrair entidades-chave
ENTITY_EXTRACTION_PROMPT = """Analise a conversa e extraia as entidades-chave mencionadas.

Retorne um JSON com:
{
    "contracts_mentioned": ["lista de contratos mencionados"],
    "procedures": ["procedimentos médicos discutidos"],
    "values": ["valores monetários mencionados com contexto"],
    "dates": ["datas importantes"],
    "key_topics": ["tópicos principais"],
    "pending_questions": ["perguntas não respondidas"],
    "decisions": ["decisões ou conclusões tomadas"]
}

Seja preciso e inclua apenas informações explicitamente mencionadas."""


class ConversationSummary:
    """Representa um resumo de conversa."""

    def __init__(
        self,
        conversation_id: UUID,
        message_range: Tuple[int, int],
        summary_text: str,
        key_entities: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        tokens_in_summary: int = 0,
    ):
        """
        Inicializa o resumo.

        Args:
            conversation_id: ID da conversa
            message_range: Tupla (índice_inicio, índice_fim) das mensagens resumidas
            summary_text: Texto do resumo
            key_entities: Entidades-chave extraídas
            created_at: Momento de criação
            tokens_in_summary: Tokens no resumo
        """
        self.conversation_id = conversation_id
        self.message_range = message_range
        self.summary_text = summary_text
        self.key_entities = key_entities or {}
        self.created_at = created_at or datetime.utcnow()
        self.tokens_in_summary = tokens_in_summary

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "conversation_id": str(self.conversation_id),
            "message_range": list(self.message_range),
            "summary_text": self.summary_text,
            "key_entities": self.key_entities,
            "created_at": self.created_at.isoformat(),
            "tokens_in_summary": self.tokens_in_summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSummary":
        """Cria a partir de dicionário."""
        return cls(
            conversation_id=UUID(data["conversation_id"]),
            message_range=tuple(data["message_range"]),
            summary_text=data["summary_text"],
            key_entities=data.get("key_entities", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            tokens_in_summary=data.get("tokens_in_summary", 0),
        )


class ConversationSummarizer:
    """
    Serviço para sumarização de conversas.

    Gera resumos de conversas longas para manter contexto
    dentro dos limites de tokens do LLM.

    Exemplo:
        summarizer = ConversationSummarizer()

        # Gerar resumo de uma conversa
        summary = await summarizer.summarize_conversation(
            conversation=conversation,
            max_messages_to_summarize=50,
        )

        # Verificar se conversa precisa de resumo
        needs = summarizer.needs_summarization(conversation, threshold=20)
    """

    def __init__(
        self,
        token_counter: Optional[TokenCounter] = None,
        summary_trigger_messages: int = 20,
        summary_trigger_tokens: int = 6000,
        summary_target_tokens: int = 500,
    ):
        """
        Inicializa o sumarizador.

        Args:
            token_counter: Contador de tokens
            summary_trigger_messages: Número de mensagens que dispara sumarização
            summary_trigger_tokens: Tokens que disparam sumarização
            summary_target_tokens: Tamanho alvo do resumo em tokens
        """
        self._settings = get_settings()
        self._token_counter = token_counter or get_token_counter()

        self.summary_trigger_messages = summary_trigger_messages
        self.summary_trigger_tokens = summary_trigger_tokens
        self.summary_target_tokens = summary_target_tokens

        # Cliente Azure OpenAI
        self._client = AsyncAzureOpenAI(
            api_key=self._settings.azure_openai.api_key,
            api_version=self._settings.azure_openai.api_version,
            azure_endpoint=self._settings.azure_openai.endpoint,
        )
        self._deployment = self._settings.azure_openai.deployment_name

        logger.info(
            "ConversationSummarizer inicializado",
            trigger_messages=summary_trigger_messages,
            trigger_tokens=summary_trigger_tokens,
        )

    def needs_summarization(
        self,
        conversation: Conversation,
        existing_summaries: Optional[List[ConversationSummary]] = None,
    ) -> bool:
        """
        Verifica se a conversa precisa de sumarização.

        Args:
            conversation: Conversa a verificar
            existing_summaries: Resumos já existentes

        Returns:
            True se precisa de sumarização
        """
        # Contar mensagens não resumidas
        last_summarized_idx = 0
        if existing_summaries:
            for summary in existing_summaries:
                last_summarized_idx = max(last_summarized_idx, summary.message_range[1])

        unsummarized_messages = conversation.messages[last_summarized_idx:]

        # Verificar por número de mensagens
        if len(unsummarized_messages) >= self.summary_trigger_messages:
            logger.debug(
                "Sumarização necessária por número de mensagens",
                unsummarized_count=len(unsummarized_messages),
            )
            return True

        # Verificar por tokens
        messages_for_count = [
            {"role": msg.role.value, "content": msg.content}
            for msg in unsummarized_messages
        ]
        tokens = self._token_counter.count_messages_tokens(messages_for_count)

        if tokens >= self.summary_trigger_tokens:
            logger.debug(
                "Sumarização necessária por tokens",
                token_count=tokens,
            )
            return True

        return False

    async def summarize_conversation(
        self,
        conversation: Conversation,
        messages_to_summarize: Optional[List[ConversationMessage]] = None,
        start_index: int = 0,
        end_index: Optional[int] = None,
        extract_entities: bool = True,
    ) -> ConversationSummary:
        """
        Gera resumo de uma conversa ou parte dela.

        Args:
            conversation: Conversa a resumir
            messages_to_summarize: Mensagens específicas (opcional)
            start_index: Índice inicial das mensagens
            end_index: Índice final das mensagens
            extract_entities: Se deve extrair entidades-chave

        Returns:
            ConversationSummary com o resumo gerado
        """
        # Determinar mensagens a resumir
        if messages_to_summarize is None:
            end_idx = end_index if end_index is not None else len(conversation.messages)
            messages_to_summarize = conversation.messages[start_index:end_idx]
            message_range = (start_index, end_idx)
        else:
            message_range = (start_index, start_index + len(messages_to_summarize))

        if not messages_to_summarize:
            return ConversationSummary(
                conversation_id=conversation.id,
                message_range=message_range,
                summary_text="Nenhuma mensagem para resumir.",
            )

        logger.info(
            "Gerando resumo de conversa",
            conversation_id=str(conversation.id),
            message_count=len(messages_to_summarize),
            message_range=message_range,
        )

        # Formatar mensagens para o prompt
        formatted_messages = self._format_messages_for_summary(messages_to_summarize)

        # Gerar resumo
        summary_text = await self._generate_summary(formatted_messages)

        # Extrair entidades se solicitado
        key_entities = {}
        if extract_entities:
            key_entities = await self._extract_entities(formatted_messages)

        # Contar tokens do resumo
        tokens_in_summary = self._token_counter.count_tokens(summary_text)

        summary = ConversationSummary(
            conversation_id=conversation.id,
            message_range=message_range,
            summary_text=summary_text,
            key_entities=key_entities,
            tokens_in_summary=tokens_in_summary,
        )

        logger.info(
            "Resumo gerado",
            conversation_id=str(conversation.id),
            summary_tokens=tokens_in_summary,
        )

        return summary

    async def summarize_incrementally(
        self,
        conversation: Conversation,
        existing_summaries: List[ConversationSummary],
    ) -> Optional[ConversationSummary]:
        """
        Gera resumo incremental de novas mensagens.

        Args:
            conversation: Conversa
            existing_summaries: Resumos já existentes

        Returns:
            Novo ConversationSummary ou None se não necessário
        """
        if not self.needs_summarization(conversation, existing_summaries):
            return None

        # Encontrar onde parou o último resumo
        last_summarized_idx = 0
        for summary in existing_summaries:
            last_summarized_idx = max(last_summarized_idx, summary.message_range[1])

        # Determinar quantas mensagens resumir
        # Deixa as últimas N mensagens sem resumir para contexto imediato
        keep_recent = 5
        end_idx = max(last_summarized_idx, len(conversation.messages) - keep_recent)

        if end_idx <= last_summarized_idx:
            return None

        return await self.summarize_conversation(
            conversation=conversation,
            start_index=last_summarized_idx,
            end_index=end_idx,
        )

    async def create_progressive_summary(
        self,
        existing_summaries: List[ConversationSummary],
        conversation_id: UUID,
    ) -> ConversationSummary:
        """
        Cria um resumo de resumos (para conversas muito longas).

        Args:
            existing_summaries: Lista de resumos existentes
            conversation_id: ID da conversa

        Returns:
            ConversationSummary consolidado
        """
        if not existing_summaries:
            raise ValueError("Nenhum resumo para consolidar")

        # Combinar textos dos resumos
        combined_text = "\n\n---\n\n".join([
            f"[Mensagens {s.message_range[0]}-{s.message_range[1]}]\n{s.summary_text}"
            for s in existing_summaries
        ])

        # Combinar entidades
        combined_entities: Dict[str, List[Any]] = {}
        for summary in existing_summaries:
            for key, value in summary.key_entities.items():
                if key not in combined_entities:
                    combined_entities[key] = []
                if isinstance(value, list):
                    combined_entities[key].extend(value)
                else:
                    combined_entities[key].append(value)

        # Gerar resumo consolidado
        messages = [
            {"role": "system", "content": SUMMARIZATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Consolide os seguintes resumos em um único resumo coeso:\n\n{combined_text}",
            },
        ]

        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )

        summary_text = response.choices[0].message.content or ""

        # Determinar range total
        min_start = min(s.message_range[0] for s in existing_summaries)
        max_end = max(s.message_range[1] for s in existing_summaries)

        return ConversationSummary(
            conversation_id=conversation_id,
            message_range=(min_start, max_end),
            summary_text=summary_text,
            key_entities=combined_entities,
            tokens_in_summary=self._token_counter.count_tokens(summary_text),
        )

    def _format_messages_for_summary(
        self,
        messages: List[ConversationMessage],
    ) -> str:
        """Formata mensagens para o prompt de sumarização."""
        formatted = []

        for msg in messages:
            role_label = {
                MessageRole.USER: "Usuário",
                MessageRole.ASSISTANT: "Assistente",
                MessageRole.SYSTEM: "Sistema",
            }.get(msg.role, "Desconhecido")

            formatted.append(f"**{role_label}:** {msg.content}")

        return "\n\n".join(formatted)

    async def _generate_summary(self, formatted_messages: str) -> str:
        """Gera o resumo usando o LLM."""
        messages = [
            {"role": "system", "content": SUMMARIZATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Resuma a seguinte conversa:\n\n{formatted_messages}",
            },
        ]

        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            temperature=0.3,
            max_tokens=600,
        )

        return response.choices[0].message.content or ""

    async def _extract_entities(self, formatted_messages: str) -> Dict[str, Any]:
        """Extrai entidades-chave da conversa."""
        try:
            messages = [
                {"role": "system", "content": ENTITY_EXTRACTION_PROMPT},
                {
                    "role": "user",
                    "content": f"Analise a seguinte conversa:\n\n{formatted_messages}",
                },
            ]

            response = await self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                temperature=0.1,
                max_tokens=500,
            )

            content = response.choices[0].message.content or "{}"

            # Tentar parsear JSON
            import json

            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])

        except Exception as e:
            logger.warning(f"Erro ao extrair entidades: {e}")

        return {}

    def build_context_with_summary(
        self,
        conversation: Conversation,
        summaries: List[ConversationSummary],
        max_context_tokens: int = 8000,
        min_recent_messages: int = 5,
    ) -> Dict[str, Any]:
        """
        Constrói contexto otimizado com resumo + mensagens recentes.

        Args:
            conversation: Conversa completa
            summaries: Lista de resumos
            max_context_tokens: Limite de tokens
            min_recent_messages: Mínimo de mensagens recentes

        Returns:
            Dict com 'summary', 'recent_messages', 'total_tokens'
        """
        result = {
            "summary": None,
            "recent_messages": [],
            "key_entities": {},
            "total_tokens": 0,
        }

        # Calcular tokens disponíveis
        available_tokens = max_context_tokens

        # 1. Adicionar resumo consolidado se existir
        if summaries:
            # Pegar resumo mais recente ou consolidar
            latest_summary = max(summaries, key=lambda s: s.message_range[1])
            summary_text = latest_summary.summary_text
            summary_tokens = self._token_counter.count_tokens(summary_text)

            if summary_tokens < available_tokens * 0.4:  # Max 40% para resumo
                result["summary"] = summary_text
                result["key_entities"] = latest_summary.key_entities
                available_tokens -= summary_tokens
                result["total_tokens"] += summary_tokens

            # Determinar índice onde começar mensagens recentes
            last_summarized = latest_summary.message_range[1]
        else:
            last_summarized = 0

        # 2. Adicionar mensagens recentes
        recent_messages = conversation.messages[last_summarized:]

        # Formatar para contexto
        formatted_recent = [
            {"role": msg.role.value, "content": msg.content}
            for msg in recent_messages
        ]

        # Truncar se necessário mantendo mínimo
        truncated = self._token_counter.truncate_messages_to_fit(
            messages=formatted_recent,
            max_tokens=available_tokens,
            reserve_for_response=0,
            preserve_recent=min_recent_messages,
        )

        result["recent_messages"] = truncated
        result["total_tokens"] += self._token_counter.count_messages_tokens(truncated)

        return result


# Singleton
_conversation_summarizer: Optional[ConversationSummarizer] = None


def get_conversation_summarizer() -> ConversationSummarizer:
    """Retorna instância singleton do sumarizador."""
    global _conversation_summarizer
    if _conversation_summarizer is None:
        _conversation_summarizer = ConversationSummarizer()
    return _conversation_summarizer
