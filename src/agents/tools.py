"""
Sistema de ferramentas (tools) para agentes.

Este módulo implementa:
- Classe base AgentTool para criar ferramentas
- ToolRegistry para registro e descoberta de ferramentas
- Decorador @tool para criar ferramentas de forma declarativa
"""

import asyncio
import functools
import inspect
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, get_type_hints

from src.config.logging import get_logger
from src.models.agents import (
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolResultStatus,
)

logger = get_logger(__name__)

T = TypeVar("T")


class AgentTool(ABC):
    """
    Classe base abstrata para ferramentas de agentes.

    Cada ferramenta deve:
    1. Ter um nome único
    2. Ter uma descrição clara
    3. Definir seus parâmetros
    4. Implementar o método execute

    Exemplo:
        class SearchTool(AgentTool):
            name = "search_contracts"
            description = "Busca contratos por texto"

            def get_parameters(self) -> List[ToolParameter]:
                return [
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Texto de busca",
                        required=True,
                    ),
                ]

            async def execute(self, **kwargs) -> Any:
                query = kwargs.get("query")
                # ... implementação
                return results
    """

    name: str = ""
    description: str = ""

    def __init__(self):
        """Inicializa a ferramenta."""
        if not self.name:
            self.name = self.__class__.__name__.lower()
        if not self.description:
            self.description = self.__doc__ or f"Ferramenta {self.name}"

        self._logger = get_logger(f"tool.{self.name}")

    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """
        Retorna a lista de parâmetros da ferramenta.

        Returns:
            Lista de ToolParameter definindo os parâmetros aceitos
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """
        Executa a ferramenta com os argumentos fornecidos.

        Args:
            **kwargs: Argumentos nomeados conforme os parâmetros definidos

        Returns:
            Resultado da execução (qualquer tipo)
        """
        pass

    def validate_arguments(self, arguments: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Valida os argumentos fornecidos contra os parâmetros definidos.

        Args:
            arguments: Dicionário de argumentos

        Returns:
            Tupla (válido, mensagem_erro)
        """
        params = {p.name: p for p in self.get_parameters()}

        # Verificar parâmetros obrigatórios
        for param_name, param in params.items():
            if param.required and param_name not in arguments:
                return False, f"Parâmetro obrigatório ausente: {param_name}"

        # Verificar parâmetros desconhecidos
        for arg_name in arguments:
            if arg_name not in params:
                return False, f"Parâmetro desconhecido: {arg_name}"

        return True, None

    def get_definition(self) -> ToolDefinition:
        """Retorna a definição completa da ferramenta."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.get_parameters(),
        )

    async def run(self, call: ToolCall) -> ToolResult:
        """
        Executa a ferramenta a partir de uma chamada.

        Wrapper que adiciona validação, logging e medição de tempo.

        Args:
            call: Chamada de ferramenta com argumentos

        Returns:
            ToolResult com o resultado ou erro
        """
        start_time = time.time()

        self._logger.info(
            "Executando ferramenta",
            tool_name=self.name,
            call_id=call.id,
            arguments=call.arguments,
        )

        # Validar argumentos
        valid, error_msg = self.validate_arguments(call.arguments)
        if not valid:
            self._logger.warning(
                "Argumentos inválidos",
                tool_name=self.name,
                error=error_msg,
            )
            return ToolResult(
                call_id=call.id,
                tool_name=self.name,
                status=ToolResultStatus.ERROR,
                error=error_msg,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Executar
            result = await self.execute(**call.arguments)

            execution_time = (time.time() - start_time) * 1000

            self._logger.info(
                "Ferramenta executada com sucesso",
                tool_name=self.name,
                call_id=call.id,
                execution_time_ms=round(execution_time, 2),
            )

            return ToolResult(
                call_id=call.id,
                tool_name=self.name,
                status=ToolResultStatus.SUCCESS,
                result=result,
                execution_time_ms=execution_time,
            )

        except asyncio.TimeoutError:
            execution_time = (time.time() - start_time) * 1000
            self._logger.error(
                "Timeout na execução da ferramenta",
                tool_name=self.name,
                call_id=call.id,
            )
            return ToolResult(
                call_id=call.id,
                tool_name=self.name,
                status=ToolResultStatus.TIMEOUT,
                error="Timeout na execução",
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._logger.error(
                "Erro na execução da ferramenta",
                tool_name=self.name,
                call_id=call.id,
                error=str(e),
                exc_info=True,
            )
            return ToolResult(
                call_id=call.id,
                tool_name=self.name,
                status=ToolResultStatus.ERROR,
                error=str(e),
                execution_time_ms=execution_time,
            )


class FunctionTool(AgentTool):
    """
    Ferramenta criada a partir de uma função.

    Permite criar ferramentas de forma mais simples usando funções
    ao invés de classes.
    """

    def __init__(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[List[ToolParameter]] = None,
    ):
        """
        Inicializa a ferramenta a partir de uma função.

        Args:
            func: Função a ser executada
            name: Nome da ferramenta (default: nome da função)
            description: Descrição (default: docstring da função)
            parameters: Parâmetros (default: inferido da assinatura)
        """
        self._func = func
        self._is_async = asyncio.iscoroutinefunction(func)

        # Nome e descrição
        self.name = name or func.__name__
        self.description = description or func.__doc__ or f"Ferramenta {self.name}"

        # Parâmetros
        self._parameters = parameters or self._infer_parameters(func)

        super().__init__()

    def _infer_parameters(self, func: Callable) -> List[ToolParameter]:
        """Infere parâmetros a partir da assinatura da função."""
        parameters = []
        sig = inspect.signature(func)
        type_hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}

        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            List: "array",
            Dict: "object",
        }

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            # Tipo do parâmetro
            param_type = type_hints.get(param_name, Any)
            type_str = type_mapping.get(param_type, "string")

            # Se é genérico, extrair o tipo base
            if hasattr(param_type, "__origin__"):
                origin = param_type.__origin__
                type_str = type_mapping.get(origin, "string")

            # Verificar se é obrigatório
            required = param.default == inspect.Parameter.empty

            # Valor default
            default = None if param.default == inspect.Parameter.empty else param.default

            parameters.append(
                ToolParameter(
                    name=param_name,
                    type=type_str,
                    description=f"Parâmetro {param_name}",
                    required=required,
                    default=default,
                )
            )

        return parameters

    def get_parameters(self) -> List[ToolParameter]:
        """Retorna os parâmetros da ferramenta."""
        return self._parameters

    async def execute(self, **kwargs: Any) -> Any:
        """Executa a função."""
        if self._is_async:
            return await self._func(**kwargs)
        else:
            # Executar função síncrona em thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: self._func(**kwargs))


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[List[ToolParameter]] = None,
) -> Callable[[Callable[..., T]], FunctionTool]:
    """
    Decorador para criar ferramentas a partir de funções.

    Exemplo:
        @tool(
            name="search",
            description="Busca documentos",
        )
        async def search_documents(query: str, limit: int = 10) -> List[dict]:
            # implementação
            return results

        # Uso
        registry.register(search_documents)
    """

    def decorator(func: Callable[..., T]) -> FunctionTool:
        return FunctionTool(
            func=func,
            name=name,
            description=description,
            parameters=parameters,
        )

    return decorator


class ToolRegistry:
    """
    Registro central de ferramentas disponíveis.

    Permite registrar, descobrir e executar ferramentas.

    Exemplo:
        registry = ToolRegistry()

        # Registrar ferramenta
        registry.register(SearchTool())

        # Obter definições para LLM
        tools = registry.get_tool_definitions()

        # Executar ferramenta
        result = await registry.execute("search_contracts", query="carência")
    """

    def __init__(self):
        """Inicializa o registro."""
        self._tools: Dict[str, AgentTool] = {}
        self._logger = get_logger("tool_registry")

    def register(self, tool: Union[AgentTool, Type[AgentTool]]) -> None:
        """
        Registra uma ferramenta.

        Args:
            tool: Instância ou classe de AgentTool
        """
        # Se for uma classe, instanciar
        if isinstance(tool, type):
            tool = tool()

        if tool.name in self._tools:
            self._logger.warning(
                "Substituindo ferramenta existente",
                tool_name=tool.name,
            )

        self._tools[tool.name] = tool
        self._logger.debug(
            "Ferramenta registrada",
            tool_name=tool.name,
        )

    def unregister(self, name: str) -> bool:
        """
        Remove uma ferramenta do registro.

        Args:
            name: Nome da ferramenta

        Returns:
            True se removida, False se não existia
        """
        if name in self._tools:
            del self._tools[name]
            self._logger.debug("Ferramenta removida", tool_name=name)
            return True
        return False

    def get(self, name: str) -> Optional[AgentTool]:
        """
        Obtém uma ferramenta pelo nome.

        Args:
            name: Nome da ferramenta

        Returns:
            AgentTool ou None se não encontrada
        """
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """Lista nomes de todas as ferramentas registradas."""
        return list(self._tools.keys())

    def get_tool_definitions(self, tool_names: Optional[List[str]] = None) -> List[ToolDefinition]:
        """
        Retorna definições das ferramentas.

        Args:
            tool_names: Lista de nomes (None = todas)

        Returns:
            Lista de ToolDefinition
        """
        if tool_names is None:
            tools = self._tools.values()
        else:
            tools = [self._tools[name] for name in tool_names if name in self._tools]

        return [tool.get_definition() for tool in tools]

    def get_openai_functions(self, tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Retorna ferramentas no formato OpenAI function calling.

        Args:
            tool_names: Lista de nomes (None = todas)

        Returns:
            Lista de definições no formato OpenAI
        """
        definitions = self.get_tool_definitions(tool_names)
        return [d.to_openai_function() for d in definitions]

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Executa uma ferramenta pelo nome.

        Args:
            tool_name: Nome da ferramenta
            arguments: Argumentos para execução

        Returns:
            ToolResult com o resultado
        """
        tool = self.get(tool_name)

        if tool is None:
            self._logger.error("Ferramenta não encontrada", tool_name=tool_name)
            return ToolResult(
                call_id="",
                tool_name=tool_name,
                status=ToolResultStatus.ERROR,
                error=f"Ferramenta não encontrada: {tool_name}",
            )

        call = ToolCall(tool_name=tool_name, arguments=arguments)
        return await tool.run(call)

    async def execute_call(self, call: ToolCall) -> ToolResult:
        """
        Executa uma chamada de ferramenta.

        Args:
            call: ToolCall com nome e argumentos

        Returns:
            ToolResult com o resultado
        """
        tool = self.get(call.tool_name)

        if tool is None:
            self._logger.error("Ferramenta não encontrada", tool_name=call.tool_name)
            return ToolResult(
                call_id=call.id,
                tool_name=call.tool_name,
                status=ToolResultStatus.ERROR,
                error=f"Ferramenta não encontrada: {call.tool_name}",
            )

        return await tool.run(call)

    async def execute_calls_parallel(self, calls: List[ToolCall]) -> List[ToolResult]:
        """
        Executa múltiplas chamadas em paralelo.

        Args:
            calls: Lista de ToolCall

        Returns:
            Lista de ToolResult na mesma ordem
        """
        tasks = [self.execute_call(call) for call in calls]
        return await asyncio.gather(*tasks)


# Instância global do registro
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Retorna a instância global do registro de ferramentas."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
