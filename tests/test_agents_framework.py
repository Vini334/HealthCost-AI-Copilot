"""
Testes para o framework de agentes.

Testa:
- Sistema de ferramentas (tools)
- Gerenciador de contexto
- Logger de execução
- Modelos e schemas
"""

import asyncio
import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolResultStatus,
)
from src.agents.tools import (
    AgentTool,
    FunctionTool,
    ToolRegistry,
    get_tool_registry,
    tool,
)
from src.agents.context import ContextManager, get_context_manager
from src.agents.execution_logger import (
    AgentExecutionLogger,
    ExecutionTracker,
    get_execution_tracker,
)


# ============================================
# Testes de Modelos
# ============================================


class TestToolDefinition:
    """Testes para ToolDefinition."""

    def test_to_openai_function(self):
        """Testa conversão para formato OpenAI."""
        tool_def = ToolDefinition(
            name="search",
            description="Busca documentos",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Texto de busca",
                    required=True,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Limite de resultados",
                    required=False,
                    default=10,
                ),
            ],
        )

        openai_func = tool_def.to_openai_function()

        assert openai_func["type"] == "function"
        assert openai_func["function"]["name"] == "search"
        assert openai_func["function"]["description"] == "Busca documentos"
        assert "query" in openai_func["function"]["parameters"]["properties"]
        assert "limit" in openai_func["function"]["parameters"]["properties"]
        assert "query" in openai_func["function"]["parameters"]["required"]
        assert "limit" not in openai_func["function"]["parameters"]["required"]


class TestAgentContext:
    """Testes para AgentContext."""

    def test_create_context(self):
        """Testa criação de contexto."""
        context = AgentContext(
            client_id="cliente-123",
            query="Qual o prazo de carência?",
            contract_id="contrato-456",
        )

        assert context.client_id == "cliente-123"
        assert context.query == "Qual o prazo de carência?"
        assert context.contract_id == "contrato-456"
        assert context.execution_id is not None
        assert len(context.messages) == 0

    def test_add_message(self):
        """Testa adição de mensagens."""
        context = AgentContext(
            client_id="cliente-123",
            query="Teste",
        )

        context.add_message(role="user", content="Olá")
        context.add_message(role="assistant", content="Como posso ajudar?")

        assert len(context.messages) == 2
        assert context.messages[0].role == "user"
        assert context.messages[1].role == "assistant"

    def test_get_messages_for_llm(self):
        """Testa formatação de mensagens para LLM."""
        context = AgentContext(
            client_id="cliente-123",
            query="Teste",
        )

        context.add_message(role="system", content="Você é um assistente.")
        context.add_message(role="user", content="Olá")

        llm_messages = context.get_messages_for_llm()

        assert len(llm_messages) == 2
        assert llm_messages[0]["role"] == "system"
        assert llm_messages[1]["role"] == "user"


class TestAgentExecutionResult:
    """Testes para AgentExecutionResult."""

    def test_add_step(self):
        """Testa adição de passos."""
        result = AgentExecutionResult(
            execution_id="exec-123",
            agent_type=AgentType.RETRIEVAL,
            agent_name="retrieval_agent",
            status=AgentStatus.RUNNING,
        )

        result.add_step(
            action="think",
            description="Analisando query",
            duration_ms=50.0,
        )

        assert len(result.steps) == 1
        assert result.steps[0].step_number == 1
        assert result.steps[0].action == "think"

    def test_finalize(self):
        """Testa finalização."""
        result = AgentExecutionResult(
            execution_id="exec-123",
            agent_type=AgentType.RETRIEVAL,
            agent_name="retrieval_agent",
            status=AgentStatus.RUNNING,
        )

        result.finalize(
            status=AgentStatus.COMPLETED,
            response="Resultado encontrado",
        )

        assert result.status == AgentStatus.COMPLETED
        assert result.response == "Resultado encontrado"
        assert result.completed_at is not None
        assert result.total_duration_ms >= 0


# ============================================
# Testes de Tools
# ============================================


class SampleTool(AgentTool):
    """Ferramenta de exemplo para testes."""

    name = "sample_tool"
    description = "Ferramenta de teste"

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="text",
                type="string",
                description="Texto de entrada",
                required=True,
            ),
        ]

    async def execute(self, **kwargs: Any) -> Any:
        text = kwargs.get("text", "")
        return f"Processado: {text}"


class ErrorTool(AgentTool):
    """Ferramenta que sempre falha."""

    name = "error_tool"
    description = "Ferramenta que causa erro"

    def get_parameters(self) -> List[ToolParameter]:
        return []

    async def execute(self, **kwargs: Any) -> Any:
        raise ValueError("Erro simulado")


class TestAgentTool:
    """Testes para AgentTool."""

    def test_get_definition(self):
        """Testa obtenção de definição."""
        tool = SampleTool()
        definition = tool.get_definition()

        assert definition.name == "sample_tool"
        assert definition.description == "Ferramenta de teste"
        assert len(definition.parameters) == 1

    def test_validate_arguments_valid(self):
        """Testa validação de argumentos válidos."""
        tool = SampleTool()
        valid, error = tool.validate_arguments({"text": "teste"})

        assert valid is True
        assert error is None

    def test_validate_arguments_missing_required(self):
        """Testa validação com parâmetro obrigatório ausente."""
        tool = SampleTool()
        valid, error = tool.validate_arguments({})

        assert valid is False
        assert "obrigatório" in error

    def test_validate_arguments_unknown(self):
        """Testa validação com parâmetro desconhecido."""
        tool = SampleTool()
        valid, error = tool.validate_arguments({"text": "teste", "unknown": "value"})

        assert valid is False
        assert "desconhecido" in error

    @pytest.mark.asyncio
    async def test_run_success(self):
        """Testa execução com sucesso."""
        tool = SampleTool()
        call = ToolCall(tool_name="sample_tool", arguments={"text": "hello"})

        result = await tool.run(call)

        assert result.status == ToolResultStatus.SUCCESS
        assert result.result == "Processado: hello"
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_run_error(self):
        """Testa execução com erro."""
        tool = ErrorTool()
        call = ToolCall(tool_name="error_tool", arguments={})

        result = await tool.run(call)

        assert result.status == ToolResultStatus.ERROR
        assert "Erro simulado" in result.error


class TestFunctionTool:
    """Testes para FunctionTool."""

    def test_create_from_sync_function(self):
        """Testa criação a partir de função síncrona."""
        def add(a: int, b: int) -> int:
            """Soma dois números."""
            return a + b

        tool = FunctionTool(func=add)

        assert tool.name == "add"
        assert "Soma" in tool.description
        assert len(tool.get_parameters()) == 2

    def test_create_from_async_function(self):
        """Testa criação a partir de função assíncrona."""
        async def fetch(url: str) -> str:
            """Busca conteúdo."""
            return f"Content from {url}"

        tool = FunctionTool(func=fetch)

        assert tool.name == "fetch"
        assert tool._is_async is True

    @pytest.mark.asyncio
    async def test_execute_sync_function(self):
        """Testa execução de função síncrona."""
        def multiply(x: int, y: int) -> int:
            return x * y

        tool = FunctionTool(func=multiply)
        result = await tool.execute(x=3, y=4)

        assert result == 12

    @pytest.mark.asyncio
    async def test_execute_async_function(self):
        """Testa execução de função assíncrona."""
        async def greet(name: str) -> str:
            return f"Olá, {name}!"

        tool = FunctionTool(func=greet)
        result = await tool.execute(name="Maria")

        assert result == "Olá, Maria!"


class TestToolDecorator:
    """Testes para o decorador @tool."""

    def test_tool_decorator(self):
        """Testa criação de ferramenta via decorador."""
        @tool(name="custom_search", description="Busca customizada")
        async def search(query: str, limit: int = 5) -> List[str]:
            return [query] * limit

        assert isinstance(search, FunctionTool)
        assert search.name == "custom_search"
        assert search.description == "Busca customizada"


class TestToolRegistry:
    """Testes para ToolRegistry."""

    def test_register_and_get(self):
        """Testa registro e obtenção de ferramenta."""
        registry = ToolRegistry()
        registry.register(SampleTool())

        tool = registry.get("sample_tool")

        assert tool is not None
        assert tool.name == "sample_tool"

    def test_list_tools(self):
        """Testa listagem de ferramentas."""
        registry = ToolRegistry()
        registry.register(SampleTool())
        registry.register(ErrorTool())

        tools = registry.list_tools()

        assert "sample_tool" in tools
        assert "error_tool" in tools

    def test_get_tool_definitions(self):
        """Testa obtenção de definições."""
        registry = ToolRegistry()
        registry.register(SampleTool())

        definitions = registry.get_tool_definitions()

        assert len(definitions) == 1
        assert definitions[0].name == "sample_tool"

    def test_get_openai_functions(self):
        """Testa obtenção de funções no formato OpenAI."""
        registry = ToolRegistry()
        registry.register(SampleTool())

        functions = registry.get_openai_functions()

        assert len(functions) == 1
        assert functions[0]["type"] == "function"
        assert functions[0]["function"]["name"] == "sample_tool"

    @pytest.mark.asyncio
    async def test_execute(self):
        """Testa execução por nome."""
        registry = ToolRegistry()
        registry.register(SampleTool())

        result = await registry.execute("sample_tool", {"text": "teste"})

        assert result.status == ToolResultStatus.SUCCESS
        assert result.result == "Processado: teste"

    @pytest.mark.asyncio
    async def test_execute_not_found(self):
        """Testa execução de ferramenta inexistente."""
        registry = ToolRegistry()

        result = await registry.execute("unknown_tool", {})

        assert result.status == ToolResultStatus.ERROR
        assert "não encontrada" in result.error

    @pytest.mark.asyncio
    async def test_execute_calls_parallel(self):
        """Testa execução paralela."""
        registry = ToolRegistry()
        registry.register(SampleTool())

        calls = [
            ToolCall(tool_name="sample_tool", arguments={"text": "a"}),
            ToolCall(tool_name="sample_tool", arguments={"text": "b"}),
            ToolCall(tool_name="sample_tool", arguments={"text": "c"}),
        ]

        results = await registry.execute_calls_parallel(calls)

        assert len(results) == 3
        assert all(r.status == ToolResultStatus.SUCCESS for r in results)


# ============================================
# Testes de ContextManager
# ============================================


class TestContextManager:
    """Testes para ContextManager."""

    def test_create_context(self):
        """Testa criação de contexto."""
        manager = ContextManager()

        context = manager.create_context(
            client_id="cliente-123",
            query="Qual o prazo?",
            contract_id="contrato-456",
        )

        assert context.client_id == "cliente-123"
        assert context.query == "Qual o prazo?"
        assert len(context.messages) == 1  # mensagem do usuário
        assert context.messages[0].role == "user"

    def test_create_context_with_system_prompt(self):
        """Testa criação de contexto com system prompt."""
        manager = ContextManager()

        context = manager.create_context(
            client_id="cliente-123",
            query="Teste",
            system_prompt="Você é um assistente.",
        )

        assert len(context.messages) == 2
        assert context.messages[0].role == "system"
        assert context.messages[1].role == "user"

    def test_get_context(self):
        """Testa obtenção de contexto."""
        manager = ContextManager()

        context = manager.create_context(
            client_id="cliente-123",
            query="Teste",
        )

        retrieved = manager.get_context(context.execution_id)

        assert retrieved is not None
        assert retrieved.execution_id == context.execution_id

    def test_add_message(self):
        """Testa adição de mensagem."""
        manager = ContextManager()

        context = manager.create_context(
            client_id="cliente-123",
            query="Teste",
        )

        message = manager.add_message(
            execution_id=context.execution_id,
            role="assistant",
            content="Resposta",
        )

        assert message is not None
        assert len(context.messages) == 2

    def test_set_retrieved_chunks(self):
        """Testa definição de chunks."""
        manager = ContextManager()

        context = manager.create_context(
            client_id="cliente-123",
            query="Teste",
        )

        chunks = [{"id": "1", "content": "chunk 1"}]
        result = manager.set_retrieved_chunks(context.execution_id, chunks)

        assert result is True
        assert len(context.retrieved_chunks) == 1

    def test_shared_data(self):
        """Testa dados compartilhados."""
        manager = ContextManager()

        context = manager.create_context(
            client_id="cliente-123",
            query="Teste",
        )

        manager.set_shared_data(context.execution_id, "key1", "value1")
        manager.set_shared_data(context.execution_id, "key2", {"nested": True})

        assert manager.get_shared_data(context.execution_id, "key1") == "value1"
        assert manager.get_shared_data(context.execution_id, "key2") == {"nested": True}
        assert manager.get_shared_data(context.execution_id, "unknown", "default") == "default"

    def test_cleanup_context(self):
        """Testa limpeza de contexto."""
        manager = ContextManager()

        context = manager.create_context(
            client_id="cliente-123",
            query="Teste",
        )

        execution_id = context.execution_id
        result = manager.cleanup_context(execution_id)

        assert result is True
        assert manager.get_context(execution_id) is None

    def test_build_context_summary(self):
        """Testa construção de resumo."""
        manager = ContextManager()

        context = manager.create_context(
            client_id="cliente-123",
            query="Teste",
            contract_id="contrato-456",
        )

        manager.set_retrieved_chunks(
            context.execution_id,
            [{"content": "conteúdo do chunk", "page_number": 5}]
        )

        summary = manager.build_context_summary(context.execution_id)

        assert "cliente-123" in summary
        assert "contrato-456" in summary
        assert "1 trechos" in summary


# ============================================
# Testes de ExecutionLogger
# ============================================


class TestAgentExecutionLogger:
    """Testes para AgentExecutionLogger."""

    def test_create_logger(self):
        """Testa criação de logger."""
        logger = AgentExecutionLogger(
            agent_type=AgentType.RETRIEVAL,
            agent_name="test_agent",
        )

        assert logger.agent_type == AgentType.RETRIEVAL
        assert logger.agent_name == "test_agent"
        assert logger.execution_id is not None

    def test_step_context_manager(self):
        """Testa context manager de passo."""
        exec_logger = AgentExecutionLogger(
            agent_type=AgentType.RETRIEVAL,
            agent_name="test_agent",
        )

        with exec_logger.step("Analisando", action="think"):
            pass  # simula processamento

        result = exec_logger.get_result()
        assert len(result.steps) == 1
        assert result.steps[0].description == "Analisando"

    def test_finalize_success(self):
        """Testa finalização com sucesso."""
        exec_logger = AgentExecutionLogger(
            agent_type=AgentType.RETRIEVAL,
            agent_name="test_agent",
        )

        result = exec_logger.finalize(
            status=AgentStatus.COMPLETED,
            response="Resultado",
        )

        assert result.status == AgentStatus.COMPLETED
        assert result.response == "Resultado"
        assert result.total_duration_ms >= 0

    def test_finalize_error(self):
        """Testa finalização com erro."""
        exec_logger = AgentExecutionLogger(
            agent_type=AgentType.RETRIEVAL,
            agent_name="test_agent",
        )

        result = exec_logger.finalize(
            status=AgentStatus.FAILED,
            error="Erro de teste",
        )

        assert result.status == AgentStatus.FAILED
        assert result.error == "Erro de teste"

    def test_add_source(self):
        """Testa adição de fonte."""
        exec_logger = AgentExecutionLogger(
            agent_type=AgentType.RETRIEVAL,
            agent_name="test_agent",
        )

        exec_logger.add_source({"page": 5, "section": "Carência"})

        result = exec_logger.get_result()
        assert len(result.sources) == 1

    def test_get_trace(self):
        """Testa obtenção de trace."""
        exec_logger = AgentExecutionLogger(
            agent_type=AgentType.RETRIEVAL,
            agent_name="test_agent",
        )

        with exec_logger.step("Passo 1", action="think"):
            pass

        with exec_logger.step("Passo 2", action="execute"):
            pass

        trace = exec_logger.get_trace()

        assert len(trace) == 2
        assert trace[0]["step"] == 1
        assert trace[1]["step"] == 2


class TestExecutionTracker:
    """Testes para ExecutionTracker."""

    def test_register_and_get(self):
        """Testa registro e obtenção."""
        tracker = ExecutionTracker()

        result = AgentExecutionResult(
            execution_id="exec-123",
            agent_type=AgentType.RETRIEVAL,
            agent_name="test_agent",
            status=AgentStatus.COMPLETED,
        )

        tracker.register(result)

        retrieved = tracker.get("exec-123")
        assert retrieved is not None
        assert retrieved.execution_id == "exec-123"

    def test_get_by_agent_type(self):
        """Testa obtenção por tipo de agente."""
        tracker = ExecutionTracker()

        result1 = AgentExecutionResult(
            execution_id="exec-1",
            agent_type=AgentType.RETRIEVAL,
            agent_name="retrieval",
            status=AgentStatus.COMPLETED,
        )
        result2 = AgentExecutionResult(
            execution_id="exec-2",
            agent_type=AgentType.CONTRACT_ANALYST,
            agent_name="analyst",
            status=AgentStatus.COMPLETED,
        )

        tracker.register(result1)
        tracker.register(result2)

        retrieval_results = tracker.get_by_agent_type(AgentType.RETRIEVAL)

        assert len(retrieval_results) == 1
        assert retrieval_results[0].agent_type == AgentType.RETRIEVAL

    def test_get_metrics_summary(self):
        """Testa resumo de métricas."""
        tracker = ExecutionTracker()

        for i in range(5):
            result = AgentExecutionResult(
                execution_id=f"exec-{i}",
                agent_type=AgentType.RETRIEVAL,
                agent_name="test",
                status=AgentStatus.COMPLETED if i < 4 else AgentStatus.FAILED,
            )
            result.total_duration_ms = 100.0 * (i + 1)
            tracker.register(result)

        metrics = tracker.get_metrics_summary()

        assert metrics["total_executions"] == 5
        assert metrics["completed"] == 4
        assert metrics["failed"] == 1
        assert metrics["success_rate"] == 0.8

    def test_max_history_limit(self):
        """Testa limite de histórico."""
        tracker = ExecutionTracker(max_history=3)

        for i in range(5):
            result = AgentExecutionResult(
                execution_id=f"exec-{i}",
                agent_type=AgentType.RETRIEVAL,
                agent_name="test",
                status=AgentStatus.COMPLETED,
            )
            tracker.register(result)

        # Apenas os 3 mais recentes devem existir
        assert tracker.get("exec-0") is None
        assert tracker.get("exec-1") is None
        assert tracker.get("exec-2") is not None
        assert tracker.get("exec-3") is not None
        assert tracker.get("exec-4") is not None
