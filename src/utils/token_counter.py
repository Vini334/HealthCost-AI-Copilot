"""
Utilitário para contagem de tokens.

Fornece funções para estimar e contar tokens em textos,
fundamental para gerenciamento de contexto em conversas.
"""

import re
from typing import Any, Dict, List, Optional, Union

from src.config.logging import get_logger

logger = get_logger(__name__)


# Estimativa aproximada: 1 token ≈ 4 caracteres em inglês, 2-3 em português
# Para maior precisão, usar tiktoken com modelo específico
CHARS_PER_TOKEN_ESTIMATE = 3.5


class TokenCounter:
    """
    Contador de tokens para gerenciamento de contexto.

    Fornece métodos para estimar tokens em textos e mensagens,
    permitindo gerenciamento eficiente da janela de contexto do LLM.

    Exemplo:
        counter = TokenCounter()

        # Contar tokens em texto
        tokens = counter.count_tokens("Olá, como posso ajudar?")

        # Contar tokens em mensagens
        messages = [
            {"role": "user", "content": "Qual a carência?"},
            {"role": "assistant", "content": "A carência é de 180 dias."},
        ]
        total = counter.count_messages_tokens(messages)

        # Truncar mensagens para caber no limite
        truncated = counter.truncate_messages_to_fit(
            messages=messages,
            max_tokens=4000,
            preserve_system=True,
        )
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        chars_per_token: float = CHARS_PER_TOKEN_ESTIMATE,
    ):
        """
        Inicializa o contador de tokens.

        Args:
            model: Modelo do LLM (para referência futura com tiktoken)
            chars_per_token: Estimativa de caracteres por token
        """
        self._model = model
        self._chars_per_token = chars_per_token
        self._tiktoken_encoding = None

        # Tentar carregar tiktoken para contagem precisa
        self._try_load_tiktoken()

    def _try_load_tiktoken(self) -> None:
        """Tenta carregar tiktoken para contagem precisa."""
        try:
            import tiktoken

            # Mapear modelo para encoding
            encoding_map = {
                "gpt-4o": "o200k_base",
                "gpt-4o-mini": "o200k_base",
                "gpt-4": "cl100k_base",
                "gpt-4-turbo": "cl100k_base",
                "gpt-3.5-turbo": "cl100k_base",
                "text-embedding-3-small": "cl100k_base",
                "text-embedding-3-large": "cl100k_base",
            }

            encoding_name = encoding_map.get(self._model, "cl100k_base")
            self._tiktoken_encoding = tiktoken.get_encoding(encoding_name)
            logger.debug(f"Tiktoken carregado com encoding {encoding_name}")
        except ImportError:
            logger.debug("Tiktoken não disponível, usando estimativa por caracteres")
        except Exception as e:
            logger.warning(f"Erro ao carregar tiktoken: {e}, usando estimativa")

    def count_tokens(self, text: str) -> int:
        """
        Conta tokens em um texto.

        Args:
            text: Texto para contar tokens

        Returns:
            Número estimado de tokens
        """
        if not text:
            return 0

        # Se tiktoken disponível, usar contagem precisa
        if self._tiktoken_encoding:
            try:
                return len(self._tiktoken_encoding.encode(text))
            except Exception:
                pass

        # Fallback: estimativa por caracteres
        return int(len(text) / self._chars_per_token)

    def count_messages_tokens(
        self,
        messages: List[Dict[str, str]],
        include_overhead: bool = True,
    ) -> int:
        """
        Conta tokens em uma lista de mensagens.

        Args:
            messages: Lista de mensagens com role e content
            include_overhead: Incluir overhead do formato de mensagens

        Returns:
            Total de tokens estimado
        """
        if not messages:
            return 0

        total = 0

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "user")

            # Tokens do conteúdo
            total += self.count_tokens(content)

            # Overhead por mensagem (role, delimitadores)
            # GPT-4: ~4 tokens por mensagem para metadados
            if include_overhead:
                total += 4

        # Overhead de início/fim da conversa
        if include_overhead:
            total += 3

        return total

    def estimate_response_tokens(self, expected_length: str = "medium") -> int:
        """
        Estima tokens para reservar para resposta.

        Args:
            expected_length: Tamanho esperado (short, medium, long, very_long)

        Returns:
            Tokens estimados para resposta
        """
        estimates = {
            "short": 200,
            "medium": 500,
            "long": 1000,
            "very_long": 2000,
        }
        return estimates.get(expected_length, 500)

    def truncate_messages_to_fit(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        reserve_for_response: int = 500,
        preserve_system: bool = True,
        preserve_recent: int = 2,
    ) -> List[Dict[str, str]]:
        """
        Trunca mensagens para caber no limite de tokens.

        Remove mensagens mais antigas mantendo as mais recentes e
        opcionalmente preservando mensagens do sistema.

        Args:
            messages: Lista de mensagens
            max_tokens: Limite máximo de tokens
            reserve_for_response: Tokens a reservar para resposta
            preserve_system: Manter mensagens de sistema
            preserve_recent: Número mínimo de mensagens recentes a manter

        Returns:
            Lista de mensagens truncada
        """
        if not messages:
            return []

        available_tokens = max_tokens - reserve_for_response

        # Separar mensagens de sistema das demais
        system_messages = []
        other_messages = []

        for msg in messages:
            if preserve_system and msg.get("role") == "system":
                system_messages.append(msg)
            else:
                other_messages.append(msg)

        # Calcular tokens das mensagens de sistema
        system_tokens = self.count_messages_tokens(system_messages)

        # Tokens disponíveis para outras mensagens
        available_for_other = available_tokens - system_tokens

        if available_for_other <= 0:
            # Apenas mensagens de sistema cabem
            return system_messages

        # Garantir mensagens recentes preservadas
        recent_messages = other_messages[-preserve_recent:] if preserve_recent > 0 else []
        older_messages = other_messages[:-preserve_recent] if preserve_recent > 0 else other_messages

        recent_tokens = self.count_messages_tokens(recent_messages)

        if recent_tokens > available_for_other:
            # Até mensagens recentes excedem - truncar conteúdo
            return system_messages + self._truncate_message_content(
                recent_messages,
                available_for_other,
            )

        # Adicionar mensagens antigas que couberem
        remaining_tokens = available_for_other - recent_tokens
        included_older = []

        for msg in reversed(older_messages):
            msg_tokens = self.count_messages_tokens([msg])
            if msg_tokens <= remaining_tokens:
                included_older.insert(0, msg)
                remaining_tokens -= msg_tokens
            else:
                break

        return system_messages + included_older + recent_messages

    def _truncate_message_content(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
    ) -> List[Dict[str, str]]:
        """Trunca conteúdo de mensagens para caber no limite."""
        result = []
        remaining_tokens = max_tokens

        for msg in messages:
            msg_copy = msg.copy()
            content = msg_copy.get("content", "")
            content_tokens = self.count_tokens(content)

            # Overhead por mensagem
            overhead = 4

            if content_tokens + overhead <= remaining_tokens:
                result.append(msg_copy)
                remaining_tokens -= content_tokens + overhead
            else:
                # Truncar conteúdo
                available_for_content = remaining_tokens - overhead
                if available_for_content > 50:  # Mínimo razoável
                    truncated_content = self._truncate_text_to_tokens(
                        content,
                        available_for_content,
                    )
                    msg_copy["content"] = truncated_content + "... [truncado]"
                    result.append(msg_copy)
                break

        return result

    def _truncate_text_to_tokens(self, text: str, max_tokens: int) -> str:
        """Trunca texto para número máximo de tokens."""
        if self._tiktoken_encoding:
            try:
                tokens = self._tiktoken_encoding.encode(text)
                if len(tokens) <= max_tokens:
                    return text
                truncated_tokens = tokens[:max_tokens]
                return self._tiktoken_encoding.decode(truncated_tokens)
            except Exception:
                pass

        # Fallback: estimativa por caracteres
        max_chars = int(max_tokens * self._chars_per_token)
        return text[:max_chars]

    def calculate_available_context(
        self,
        model_context_window: int = 128000,
        system_prompt_tokens: int = 500,
        response_reserve: int = 2000,
    ) -> int:
        """
        Calcula tokens disponíveis para contexto de conversa.

        Args:
            model_context_window: Janela de contexto do modelo
            system_prompt_tokens: Tokens usados pelo system prompt
            response_reserve: Tokens reservados para resposta

        Returns:
            Tokens disponíveis para histórico de conversa
        """
        return model_context_window - system_prompt_tokens - response_reserve

    def split_text_into_chunks(
        self,
        text: str,
        max_tokens_per_chunk: int = 500,
        overlap_tokens: int = 50,
    ) -> List[str]:
        """
        Divide texto em chunks de tamanho máximo de tokens.

        Args:
            text: Texto para dividir
            max_tokens_per_chunk: Máximo de tokens por chunk
            overlap_tokens: Tokens de sobreposição entre chunks

        Returns:
            Lista de chunks
        """
        if not text:
            return []

        # Dividir por parágrafos primeiro
        paragraphs = re.split(r"\n\n+", text)
        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            if current_tokens + para_tokens <= max_tokens_per_chunk:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                # Salvar chunk atual
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))

                # Se parágrafo maior que limite, dividir por sentenças
                if para_tokens > max_tokens_per_chunk:
                    para_chunks = self._split_paragraph_by_sentences(
                        para,
                        max_tokens_per_chunk,
                    )
                    chunks.extend(para_chunks)
                    current_chunk = []
                    current_tokens = 0
                else:
                    # Começar novo chunk com overlap
                    if chunks and overlap_tokens > 0:
                        overlap_text = self._get_overlap_text(
                            chunks[-1],
                            overlap_tokens,
                        )
                        current_chunk = [overlap_text, para]
                        current_tokens = self.count_tokens(overlap_text) + para_tokens
                    else:
                        current_chunk = [para]
                        current_tokens = para_tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _split_paragraph_by_sentences(
        self,
        paragraph: str,
        max_tokens: int,
    ) -> List[str]:
        """Divide parágrafo em chunks por sentenças."""
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        chunks = []
        current_chunk = []
        current_tokens = 0

        for sentence in sentences:
            sent_tokens = self.count_tokens(sentence)

            if current_tokens + sent_tokens <= max_tokens:
                current_chunk.append(sentence)
                current_tokens += sent_tokens
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sent_tokens

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _get_overlap_text(self, text: str, overlap_tokens: int) -> str:
        """Extrai texto de overlap do final de um chunk."""
        words = text.split()
        overlap_text = []
        current_tokens = 0

        for word in reversed(words):
            word_tokens = self.count_tokens(word)
            if current_tokens + word_tokens <= overlap_tokens:
                overlap_text.insert(0, word)
                current_tokens += word_tokens
            else:
                break

        return " ".join(overlap_text)


# Singleton
_token_counter: Optional[TokenCounter] = None


def get_token_counter() -> TokenCounter:
    """Retorna instância singleton do contador de tokens."""
    global _token_counter
    if _token_counter is None:
        _token_counter = TokenCounter()
    return _token_counter


def count_tokens(text: str) -> int:
    """Função de conveniência para contar tokens."""
    return get_token_counter().count_tokens(text)


def count_messages_tokens(messages: List[Dict[str, str]]) -> int:
    """Função de conveniência para contar tokens em mensagens."""
    return get_token_counter().count_messages_tokens(messages)
