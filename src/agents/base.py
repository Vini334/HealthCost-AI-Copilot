"""
Classe base para agentes do sistema multi-agente.

Este módulo implementa:
- BaseAgent: classe abstrata base para todos os agentes
- Interface comum para execução de agentes
- Integração com sistema de tools, contexto e logging
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from openai import AsyncAzureOpenAI

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from src.agents.context import ContextManager, get_context_manager
from src.agents.execution_logger import (
    AgentExecutionLogger,
    ExecutionTracker,
    get_execution_tracker,
)
from src.agents.tools import ToolRegistry, get_tool_registry

logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Classe base abstrata para agentes.

    Todos os agentes especializados devem herdar desta classe
    e implementar os métodos abstratos.

    Atributos de classe:
        agent_type: Tipo do agente (da enum AgentType)
        agent_name: Nome único do agente
        description: Descrição do que o agente faz
        system_prompt: Prompt de sistema para o LLM

    Exemplo:
        class RetrievalAgent(BaseAgent):
            agent_type = AgentType.RETRIEVAL
            agent_name = "retrieval_agent"
            description = "Busca documentos relevantes"
            system_prompt = "Você é um agente de busca..."

            def get_tools(self) -> List[str]:
                return ["search_contracts", "search_hybrid"]

            async def process(self, context: AgentContext) -> AgentExecutionResult:
                # implementação
                pass
    """

    # Atributos de classe a serem sobrescritos
    agent_type: AgentType = AgentType.ORCHESTRATOR
    agent_name: str = "base_agent"
    description: str = "Agente base"
    system_prompt: str = "Você é um assistente útil."

    # Configurações do LLM
    model_deployment: Optional[str] = None  # None = usa default das settings
    temperature: float = 0.7
    max_tokens: int = 2000

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        context_manager: Optional[ContextManager] = None,
        execution_tracker: Optional[ExecutionTracker] = None,
    ):
        """
        Inicializa o agente.

        Args:
            tool_registry: Registro de ferramentas (usa global se não fornecido)
            context_manager: Gerenciador de contexto (usa global se não fornecido)
            execution_tracker: Rastreador de execuções (usa global se não fornecido)
        """
        self._settings = get_settings()
        self._tool_registry = tool_registry or get_tool_registry()
        self._context_manager = context_manager or get_context_manager()
        self._execution_tracker = execution_tracker or get_execution_tracker()

        # Cliente Azure OpenAI
        self._client = AsyncAzureOpenAI(
            api_key=self._settings.azure_openai.api_key,
            api_version=self._settings.azure_openai.api_version,
            azure_endpoint=self._settings.azure_openai.endpoint,
        )

        # Deployment do modelo
        self._deployment = (
            self.model_deployment or self._settings.azure_openai.deployment_name
        )

        self._logger = get_logger(
            f"agent.{self.agent_name}",
            agent_type=self.agent_type.value,
        )

        self._logger.info(
            "Agente inicializado",
            agent_name=self.agent_name,
            agent_type=self.agent_type.value,
            deployment=self._deployment,
        )

    @abstractmethod
    def get_tools(self) -> List[str]:
        """
        Retorna lista de nomes das ferramentas disponíveis para este agente.

        Returns:
            Lista de nomes de ferramentas registradas no ToolRegistry
        """
        pass

    @abstractmethod
    async def process(self, context: AgentContext) -> AgentExecutionResult:
        """
        Processa uma query no contexto dado.

        Este é o método principal que implementa a lógica do agente.

        Args:
            context: Contexto de execução com query, histórico, etc.

        Returns:
            AgentExecutionResult com resposta e metadados
        """
        pass

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Retorna definições das ferramentas do agente."""
        tool_names = self.get_tools()
        return self._tool_registry.get_tool_definitions(tool_names)

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Retorna ferramentas no formato OpenAI function calling."""
        tool_names = self.get_tools()
        return self._tool_registry.get_openai_functions(tool_names)

    async def execute(
        self,
        query: str,
        client_id: str,
        contract_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionResult:
        """
        Executa o agente com uma query.

        Método de conveniência que cria contexto e chama process().

        Args:
            query: Pergunta/comando do usuário
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            conversation_id: ID da conversa (opcional)
            metadata: Metadados adicionais

        Returns:
            AgentExecutionResult com resposta e metadados
        """
        # Criar contexto
        context = self._context_manager.create_context(
            client_id=client_id,
            query=query,
            contract_id=contract_id,
            conversation_id=conversation_id,
            system_prompt=self.system_prompt,
            metadata=metadata,
        )

        try:
            # Processar
            result = await self.process(context)

            # Registrar execução
            self._execution_tracker.register(result)

            return result

        finally:
            # Limpar contexto
            self._context_manager.cleanup_context(context.execution_id)

    async def execute_with_context(
        self,
        context: AgentContext,
    ) -> AgentExecutionResult:
        """
        Executa o agente com um contexto existente.

        Útil para orquestração onde o contexto é compartilhado.

        Args:
            context: Contexto de execução existente

        Returns:
            AgentExecutionResult com resposta e metadados
        """
        result = await self.process(context)
        self._execution_tracker.register(result)
        return result

    def _create_execution_logger(
        self,
        execution_id: Optional[str] = None,
    ) -> AgentExecutionLogger:
        """Cria um logger de execução para este agente."""
        return AgentExecutionLogger(
            agent_type=self.agent_type,
            agent_name=self.agent_name,
            execution_id=execution_id,
        )

    async def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Union[str, Dict[str, Any]] = "auto",
    ) -> Dict[str, Any]:
        """
        Chama o LLM com mensagens e ferramentas.

        Args:
            messages: Lista de mensagens no formato OpenAI
            tools: Ferramentas disponíveis (formato OpenAI)
            tool_choice: Controle de uso de ferramentas

        Returns:
            Resposta do LLM
        """
        kwargs: Dict[str, Any] = {
            "model": self._deployment,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        self._logger.debug(
            "Chamando LLM",
            deployment=self._deployment,
            message_count=len(messages),
            has_tools=tools is not None,
        )

        response = await self._client.chat.completions.create(**kwargs)

        self._logger.debug(
            "Resposta do LLM recebida",
            finish_reason=response.choices[0].finish_reason,
            usage=response.usage.model_dump() if response.usage else None,
        )

        return {
            "content": response.choices[0].message.content,
            "tool_calls": response.choices[0].message.tool_calls,
            "finish_reason": response.choices[0].finish_reason,
            "usage": response.usage.model_dump() if response.usage else None,
        }

    async def _execute_tool_calls(
        self,
        tool_calls: List[Any],
        exec_logger: AgentExecutionLogger,
    ) -> List[ToolResult]:
        """
        Executa chamadas de ferramentas do LLM.

        Args:
            tool_calls: Lista de tool_calls da resposta do LLM
            exec_logger: Logger de execução

        Returns:
            Lista de ToolResult
        """
        results = []

        for tc in tool_calls:
            # Criar ToolCall
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            tool_call = ToolCall(
                id=tc.id,
                tool_name=tc.function.name,
                arguments=arguments,
            )

            exec_logger.log_tool_call(tool_call)

            # Executar
            result = await self._tool_registry.execute_call(tool_call)

            exec_logger.log_tool_result(result)

            results.append(result)

        return results

    def _format_tool_results_for_llm(
        self,
        tool_calls: List[Any],
        results: List[ToolResult],
    ) -> List[Dict[str, Any]]:
        """
        Formata resultados de ferramentas para enviar ao LLM.

        Args:
            tool_calls: Tool calls originais do LLM
            results: Resultados das execuções

        Returns:
            Lista de mensagens de resultado no formato OpenAI
        """
        messages = []

        for tc, result in zip(tool_calls, results):
            content = ""
            if result.status.value == "success":
                # Serializar resultado
                if isinstance(result.result, (dict, list)):
                    content = json.dumps(result.result, ensure_ascii=False, default=str)
                else:
                    content = str(result.result) if result.result else ""
            else:
                content = f"Erro: {result.error}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": content,
            })

        return messages

    async def _run_agent_loop(
        self,
        context: AgentContext,
        exec_logger: AgentExecutionLogger,
        max_iterations: int = 10,
    ) -> str:
        """
        Executa o loop de agente (LLM -> tools -> LLM -> ...).

        Args:
            context: Contexto de execução
            exec_logger: Logger de execução
            max_iterations: Máximo de iterações para evitar loops infinitos

        Returns:
            Resposta final do agente
        """
        # Preparar mensagens
        messages = context.get_messages_for_llm()

        # Adicionar system prompt se não presente
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        # Obter ferramentas
        tools = self.get_openai_tools()

        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            with exec_logger.step(f"Iteração {iteration} do LLM", action="think"):
                # Chamar LLM
                response = await self._call_llm(
                    messages=messages,
                    tools=tools if tools else None,
                )

                # Verificar se terminou
                if response["finish_reason"] == "stop":
                    return response["content"] or ""

                # Verificar se tem tool calls
                if not response["tool_calls"]:
                    return response["content"] or ""

                # Adicionar resposta do assistant às mensagens
                messages.append({
                    "role": "assistant",
                    "content": response["content"],
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in response["tool_calls"]
                    ],
                })

            # Executar ferramentas
            with exec_logger.step("Executando ferramentas", action="tool_call"):
                tool_results = await self._execute_tool_calls(
                    response["tool_calls"],
                    exec_logger,
                )

                # Adicionar resultados às mensagens
                tool_messages = self._format_tool_results_for_llm(
                    response["tool_calls"],
                    tool_results,
                )
                messages.extend(tool_messages)

        # Atingiu limite de iterações
        exec_logger.log_warning(
            "Limite de iterações atingido",
            max_iterations=max_iterations,
        )

        return "Desculpe, não consegui completar a análise no tempo esperado."

    def _extract_sources_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Extrai informações de fonte dos chunks para citação.

        Args:
            chunks: Lista de chunks recuperados

        Returns:
            Lista de fontes formatadas
        """
        sources = []
        seen = set()

        for chunk in chunks:
            # Criar identificador único
            source_key = (
                chunk.get("document_id", ""),
                chunk.get("page_number", ""),
                chunk.get("section_title", ""),
            )

            if source_key in seen:
                continue
            seen.add(source_key)

            sources.append({
                "document_id": chunk.get("document_id"),
                "page_number": chunk.get("page_number"),
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "section_title": chunk.get("section_title"),
                "section_type": chunk.get("section_type"),
                "content_preview": chunk.get("content", "")[:100] + "..." if chunk.get("content") else None,
            })

        return sources


class SimpleAgent(BaseAgent):
    """
    Agente simples sem uso de ferramentas.

    Útil para agentes que apenas processam texto com LLM,
    sem necessidade de chamar ferramentas externas.
    """

    def get_tools(self) -> List[str]:
        """Retorna lista vazia (sem ferramentas)."""
        return []

    async def process(self, context: AgentContext) -> AgentExecutionResult:
        """
        Processa query apenas com LLM.

        Args:
            context: Contexto de execução

        Returns:
            AgentExecutionResult com resposta
        """
        exec_logger = self._create_execution_logger(context.execution_id)

        try:
            with exec_logger.step("Processando com LLM", action="think"):
                messages = context.get_messages_for_llm()

                if not messages or messages[0].get("role") != "system":
                    messages.insert(0, {"role": "system", "content": self.system_prompt})

                response = await self._call_llm(messages)

                if response.get("usage"):
                    exec_logger.set_tokens_used(
                        response["usage"].get("total_tokens", 0)
                    )

            return exec_logger.finalize(
                status=AgentStatus.COMPLETED,
                response=response["content"],
            )

        except Exception as e:
            self._logger.error(
                "Erro no processamento",
                error=str(e),
                exc_info=True,
            )
            return exec_logger.finalize(
                status=AgentStatus.FAILED,
                error=str(e),
            )
