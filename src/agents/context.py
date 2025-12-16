"""
Gerenciador de contexto para agentes.

Este módulo implementa:
- ContextManager para gerenciar contexto de execução
- Gerenciamento de memória de curto prazo
- Compartilhamento de dados entre agentes
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.config.logging import get_logger
from src.models.agents import AgentContext, AgentMessage, ToolCall, ToolResult

logger = get_logger(__name__)


class ContextManager:
    """
    Gerenciador de contexto para execução de agentes.

    Responsável por:
    - Criar e gerenciar contextos de execução
    - Manter histórico de mensagens
    - Compartilhar dados entre agentes
    - Gerenciar memória de curto prazo

    Exemplo:
        manager = ContextManager()

        # Criar contexto
        ctx = manager.create_context(
            client_id="cliente-123",
            query="Qual o prazo de carência?"
        )

        # Adicionar mensagens
        manager.add_message(ctx.execution_id, role="user", content="...")
        manager.add_message(ctx.execution_id, role="assistant", content="...")

        # Compartilhar dados
        manager.set_shared_data(ctx.execution_id, "chunks", [...])
    """

    def __init__(self, max_history_size: int = 20):
        """
        Inicializa o gerenciador.

        Args:
            max_history_size: Tamanho máximo do histórico de mensagens
        """
        self._contexts: Dict[str, AgentContext] = {}
        self._shared_data: Dict[str, Dict[str, Any]] = {}
        self._max_history_size = max_history_size
        self._logger = get_logger("context_manager")

    def create_context(
        self,
        client_id: str,
        query: str,
        contract_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentContext:
        """
        Cria um novo contexto de execução.

        Args:
            client_id: ID do cliente
            query: Query/pergunta do usuário
            contract_id: ID do contrato (opcional)
            conversation_id: ID da conversa (opcional)
            system_prompt: Prompt de sistema (opcional)
            metadata: Metadados adicionais

        Returns:
            AgentContext criado
        """
        execution_id = str(uuid4())

        context = AgentContext(
            execution_id=execution_id,
            client_id=client_id,
            contract_id=contract_id,
            conversation_id=conversation_id,
            query=query,
            metadata=metadata or {},
        )

        # Adicionar mensagem de sistema se fornecida
        if system_prompt:
            context.add_message(role="system", content=system_prompt)

        # Adicionar query como mensagem do usuário
        context.add_message(role="user", content=query)

        # Armazenar
        self._contexts[execution_id] = context
        self._shared_data[execution_id] = {}

        self._logger.info(
            "Contexto criado",
            execution_id=execution_id,
            client_id=client_id,
            contract_id=contract_id,
        )

        return context

    def get_context(self, execution_id: str) -> Optional[AgentContext]:
        """
        Obtém um contexto pelo ID de execução.

        Args:
            execution_id: ID da execução

        Returns:
            AgentContext ou None
        """
        return self._contexts.get(execution_id)

    def add_message(
        self,
        execution_id: str,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        tool_result: Optional[ToolResult] = None,
    ) -> Optional[AgentMessage]:
        """
        Adiciona uma mensagem ao contexto.

        Args:
            execution_id: ID da execução
            role: Papel da mensagem (system, user, assistant, tool)
            content: Conteúdo da mensagem
            tool_calls: Chamadas de ferramentas (se assistant)
            tool_result: Resultado de ferramenta (se tool)

        Returns:
            AgentMessage adicionada ou None se contexto não existe
        """
        context = self._contexts.get(execution_id)
        if not context:
            self._logger.warning(
                "Contexto não encontrado para adicionar mensagem",
                execution_id=execution_id,
            )
            return None

        message = context.add_message(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_result=tool_result,
        )

        # Limitar tamanho do histórico mantendo mensagem de sistema
        self._trim_history(context)

        return message

    def _trim_history(self, context: AgentContext) -> None:
        """Remove mensagens antigas se exceder limite."""
        if len(context.messages) <= self._max_history_size:
            return

        # Preservar mensagem de sistema (primeira se for system)
        system_messages = []
        other_messages = []

        for msg in context.messages:
            if msg.role == "system":
                system_messages.append(msg)
            else:
                other_messages.append(msg)

        # Manter as N mensagens mais recentes (exceto system)
        keep_count = self._max_history_size - len(system_messages)
        recent_messages = other_messages[-keep_count:] if keep_count > 0 else []

        # Reconstruir lista
        context.messages = system_messages + recent_messages

        self._logger.debug(
            "Histórico truncado",
            execution_id=context.execution_id,
            new_size=len(context.messages),
        )

    def set_retrieved_chunks(
        self,
        execution_id: str,
        chunks: List[Dict[str, Any]],
    ) -> bool:
        """
        Define os chunks recuperados no contexto.

        Args:
            execution_id: ID da execução
            chunks: Lista de chunks recuperados

        Returns:
            True se sucesso, False se contexto não existe
        """
        context = self._contexts.get(execution_id)
        if not context:
            return False

        context.retrieved_chunks = chunks
        self._logger.debug(
            "Chunks definidos no contexto",
            execution_id=execution_id,
            chunk_count=len(chunks),
        )
        return True

    def set_cost_data(
        self,
        execution_id: str,
        cost_data: Dict[str, Any],
    ) -> bool:
        """
        Define os dados de custos no contexto.

        Args:
            execution_id: ID da execução
            cost_data: Dados de custos

        Returns:
            True se sucesso, False se contexto não existe
        """
        context = self._contexts.get(execution_id)
        if not context:
            return False

        context.cost_data = cost_data
        self._logger.debug(
            "Dados de custos definidos no contexto",
            execution_id=execution_id,
        )
        return True

    def set_shared_data(
        self,
        execution_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """
        Define um dado compartilhado entre agentes.

        Args:
            execution_id: ID da execução
            key: Chave do dado
            value: Valor a armazenar

        Returns:
            True se sucesso, False se execução não existe
        """
        if execution_id not in self._shared_data:
            return False

        self._shared_data[execution_id][key] = value
        self._logger.debug(
            "Dado compartilhado definido",
            execution_id=execution_id,
            key=key,
        )
        return True

    def get_shared_data(
        self,
        execution_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Obtém um dado compartilhado.

        Args:
            execution_id: ID da execução
            key: Chave do dado
            default: Valor padrão se não existir

        Returns:
            Valor armazenado ou default
        """
        if execution_id not in self._shared_data:
            return default

        return self._shared_data[execution_id].get(key, default)

    def get_all_shared_data(self, execution_id: str) -> Dict[str, Any]:
        """
        Obtém todos os dados compartilhados de uma execução.

        Args:
            execution_id: ID da execução

        Returns:
            Dicionário com todos os dados compartilhados
        """
        return self._shared_data.get(execution_id, {}).copy()

    def update_metadata(
        self,
        execution_id: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Atualiza metadados do contexto.

        Args:
            execution_id: ID da execução
            metadata: Metadados a adicionar/atualizar

        Returns:
            True se sucesso, False se contexto não existe
        """
        context = self._contexts.get(execution_id)
        if not context:
            return False

        context.metadata.update(metadata)
        return True

    def get_messages_for_llm(
        self,
        execution_id: str,
        include_system: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Obtém mensagens formatadas para envio ao LLM.

        Args:
            execution_id: ID da execução
            include_system: Se deve incluir mensagens de sistema

        Returns:
            Lista de mensagens no formato esperado pelo LLM
        """
        context = self._contexts.get(execution_id)
        if not context:
            return []

        messages = context.get_messages_for_llm()

        if not include_system:
            messages = [m for m in messages if m.get("role") != "system"]

        return messages

    def build_context_summary(self, execution_id: str) -> str:
        """
        Constrói um resumo do contexto para inclusão em prompts.

        Útil para passar contexto resumido para agentes.

        Args:
            execution_id: ID da execução

        Returns:
            String com resumo do contexto
        """
        context = self._contexts.get(execution_id)
        if not context:
            return ""

        parts = []

        # Informações básicas
        parts.append(f"Cliente: {context.client_id}")
        if context.contract_id:
            parts.append(f"Contrato: {context.contract_id}")

        # Chunks recuperados
        if context.retrieved_chunks:
            parts.append(f"\n{len(context.retrieved_chunks)} trechos relevantes encontrados:")
            for i, chunk in enumerate(context.retrieved_chunks[:5], 1):
                content = chunk.get("content", "")[:200]
                page = chunk.get("page_number", "?")
                section = chunk.get("section_title", "")
                parts.append(f"\n[Trecho {i}] Página {page}")
                if section:
                    parts.append(f" - Seção: {section}")
                parts.append(f"\n{content}...")

        # Dados de custos
        if context.cost_data:
            parts.append("\nDados de custos disponíveis.")

        return "\n".join(parts)

    def cleanup_context(self, execution_id: str) -> bool:
        """
        Remove um contexto e seus dados.

        Args:
            execution_id: ID da execução

        Returns:
            True se removido, False se não existia
        """
        removed = False

        if execution_id in self._contexts:
            del self._contexts[execution_id]
            removed = True

        if execution_id in self._shared_data:
            del self._shared_data[execution_id]

        if removed:
            self._logger.debug(
                "Contexto removido",
                execution_id=execution_id,
            )

        return removed

    def cleanup_old_contexts(self, max_age_minutes: int = 60) -> int:
        """
        Remove contextos antigos.

        Args:
            max_age_minutes: Idade máxima em minutos

        Returns:
            Número de contextos removidos
        """
        now = datetime.utcnow()
        to_remove = []

        for execution_id, context in self._contexts.items():
            age = (now - context.created_at).total_seconds() / 60
            if age > max_age_minutes:
                to_remove.append(execution_id)

        for execution_id in to_remove:
            self.cleanup_context(execution_id)

        if to_remove:
            self._logger.info(
                "Contextos antigos removidos",
                count=len(to_remove),
            )

        return len(to_remove)


# Instância global
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Retorna a instância global do gerenciador de contexto."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
