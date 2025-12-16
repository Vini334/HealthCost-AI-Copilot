"""
Sistema de logging de execução para agentes.

Este módulo implementa:
- AgentExecutionLogger para rastrear execução de agentes
- Métricas de performance
- Trace de execução para debug
"""

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional
from uuid import uuid4

from src.config.logging import get_logger
from src.models.agents import (
    AgentExecutionResult,
    AgentExecutionStep,
    AgentStatus,
    AgentType,
    ToolCall,
    ToolResult,
)

logger = get_logger(__name__)


class AgentExecutionLogger:
    """
    Logger de execução para um agente específico.

    Rastreia passos de execução, ferramentas chamadas,
    tempo de execução e erros.

    Exemplo:
        logger = AgentExecutionLogger(
            agent_type=AgentType.RETRIEVAL,
            agent_name="retrieval_agent",
            execution_id="exec-123",
        )

        with logger.step("Buscando documentos") as step:
            # ... busca
            step.set_tool_call(tool_call)
            step.set_tool_result(tool_result)

        logger.finalize(
            status=AgentStatus.COMPLETED,
            response="Encontrei 5 documentos relevantes.",
        )

        result = logger.get_result()
    """

    def __init__(
        self,
        agent_type: AgentType,
        agent_name: str,
        execution_id: Optional[str] = None,
    ):
        """
        Inicializa o logger de execução.

        Args:
            agent_type: Tipo do agente
            agent_name: Nome do agente
            execution_id: ID da execução (gera novo se não fornecido)
        """
        self._execution_id = execution_id or str(uuid4())
        self._agent_type = agent_type
        self._agent_name = agent_name

        self._result = AgentExecutionResult(
            execution_id=self._execution_id,
            agent_type=agent_type,
            agent_name=agent_name,
            status=AgentStatus.RUNNING,
        )

        self._logger = get_logger(
            f"agent.{agent_name}",
            execution_id=self._execution_id,
            agent_type=agent_type.value,
        )

        self._current_step: Optional[_StepContext] = None

        self._logger.info(
            "Execução de agente iniciada",
            agent_name=agent_name,
            agent_type=agent_type.value,
        )

    @property
    def execution_id(self) -> str:
        """ID da execução."""
        return self._execution_id

    @property
    def agent_type(self) -> AgentType:
        """Tipo do agente."""
        return self._agent_type

    @property
    def agent_name(self) -> str:
        """Nome do agente."""
        return self._agent_name

    @contextmanager
    def step(self, description: str, action: str = "execute") -> Generator["_StepContext", None, None]:
        """
        Context manager para rastrear um passo de execução.

        Args:
            description: Descrição do que está sendo feito
            action: Tipo de ação (think, tool_call, respond, execute)

        Yields:
            _StepContext para configurar o passo

        Exemplo:
            with logger.step("Analisando query", action="think") as step:
                # ... análise
                pass
        """
        step_context = _StepContext(
            step_number=len(self._result.steps) + 1,
            description=description,
            action=action,
            logger=self._logger,
        )

        self._current_step = step_context

        try:
            yield step_context
        except Exception as e:
            step_context.set_error(str(e))
            raise
        finally:
            # Finalizar e adicionar step ao resultado
            step = step_context.finalize()
            self._result.steps.append(step)

            if step.tool_call:
                self._result.tool_calls_count += 1

            self._current_step = None

    def log_tool_call(self, tool_call: ToolCall) -> None:
        """
        Registra uma chamada de ferramenta.

        Args:
            tool_call: Chamada de ferramenta
        """
        self._logger.info(
            "Ferramenta chamada",
            tool_name=tool_call.tool_name,
            call_id=tool_call.id,
            arguments=tool_call.arguments,
        )

        if self._current_step:
            self._current_step.set_tool_call(tool_call)

    def log_tool_result(self, tool_result: ToolResult) -> None:
        """
        Registra o resultado de uma ferramenta.

        Args:
            tool_result: Resultado da ferramenta
        """
        self._logger.info(
            "Resultado de ferramenta",
            tool_name=tool_result.tool_name,
            call_id=tool_result.call_id,
            status=tool_result.status.value,
            execution_time_ms=round(tool_result.execution_time_ms, 2),
        )

        if self._current_step:
            self._current_step.set_tool_result(tool_result)

    def add_source(self, source: Dict[str, Any]) -> None:
        """
        Adiciona uma fonte citada.

        Args:
            source: Informações da fonte (chunk_id, page, section, etc.)
        """
        self._result.sources.append(source)

    def set_tokens_used(self, tokens: int) -> None:
        """Define o total de tokens utilizados."""
        self._result.tokens_used = tokens

    def log_info(self, message: str, **kwargs: Any) -> None:
        """Log de informação."""
        self._logger.info(message, **kwargs)

    def log_warning(self, message: str, **kwargs: Any) -> None:
        """Log de aviso."""
        self._logger.warning(message, **kwargs)

    def log_error(self, message: str, **kwargs: Any) -> None:
        """Log de erro."""
        self._logger.error(message, **kwargs)

    def log_debug(self, message: str, **kwargs: Any) -> None:
        """Log de debug."""
        self._logger.debug(message, **kwargs)

    def finalize(
        self,
        status: AgentStatus,
        response: Optional[str] = None,
        structured_output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> AgentExecutionResult:
        """
        Finaliza a execução do agente.

        Args:
            status: Status final
            response: Resposta textual
            structured_output: Saída estruturada
            error: Mensagem de erro (se falhou)

        Returns:
            AgentExecutionResult completo
        """
        self._result.status = status
        self._result.response = response
        self._result.structured_output = structured_output
        self._result.error = error
        self._result.completed_at = datetime.utcnow()

        # Calcular duração total
        self._result.total_duration_ms = (
            self._result.completed_at - self._result.started_at
        ).total_seconds() * 1000

        log_method = self._logger.info if status == AgentStatus.COMPLETED else self._logger.error

        log_method(
            "Execução de agente finalizada",
            status=status.value,
            total_duration_ms=round(self._result.total_duration_ms, 2),
            tool_calls_count=self._result.tool_calls_count,
            steps_count=len(self._result.steps),
            sources_count=len(self._result.sources),
        )

        return self._result

    def get_result(self) -> AgentExecutionResult:
        """Retorna o resultado atual da execução."""
        return self._result

    def get_trace(self) -> List[Dict[str, Any]]:
        """
        Retorna trace detalhado da execução.

        Útil para debug e análise de performance.

        Returns:
            Lista de dicionários com detalhes de cada passo
        """
        trace = []

        for step in self._result.steps:
            step_trace = {
                "step": step.step_number,
                "action": step.action,
                "description": step.description,
                "duration_ms": round(step.duration_ms, 2),
                "timestamp": step.timestamp.isoformat(),
            }

            if step.tool_call:
                step_trace["tool_call"] = {
                    "name": step.tool_call.tool_name,
                    "arguments": step.tool_call.arguments,
                }

            if step.tool_result:
                step_trace["tool_result"] = {
                    "status": step.tool_result.status.value,
                    "execution_time_ms": round(step.tool_result.execution_time_ms, 2),
                }

            trace.append(step_trace)

        return trace


class _StepContext:
    """Contexto interno para rastrear um passo de execução."""

    def __init__(
        self,
        step_number: int,
        description: str,
        action: str,
        logger: Any,
    ):
        self._step_number = step_number
        self._description = description
        self._action = action
        self._logger = logger
        self._start_time = time.time()
        self._tool_call: Optional[ToolCall] = None
        self._tool_result: Optional[ToolResult] = None
        self._error: Optional[str] = None

        self._logger.debug(
            f"Passo {step_number}: {description}",
            action=action,
        )

    def set_tool_call(self, tool_call: ToolCall) -> None:
        """Define a chamada de ferramenta do passo."""
        self._tool_call = tool_call

    def set_tool_result(self, tool_result: ToolResult) -> None:
        """Define o resultado da ferramenta."""
        self._tool_result = tool_result

    def set_error(self, error: str) -> None:
        """Define um erro ocorrido no passo."""
        self._error = error

    def finalize(self) -> AgentExecutionStep:
        """Finaliza o passo e retorna o objeto AgentExecutionStep."""
        duration_ms = (time.time() - self._start_time) * 1000

        self._logger.debug(
            f"Passo {self._step_number} concluído",
            duration_ms=round(duration_ms, 2),
            has_tool_call=self._tool_call is not None,
            has_error=self._error is not None,
        )

        return AgentExecutionStep(
            step_number=self._step_number,
            action=self._action,
            description=self._description,
            tool_call=self._tool_call,
            tool_result=self._tool_result,
            duration_ms=duration_ms,
        )


class ExecutionTracker:
    """
    Rastreador global de execuções de agentes.

    Mantém histórico de execuções para análise e debug.
    """

    def __init__(self, max_history: int = 100):
        """
        Inicializa o rastreador.

        Args:
            max_history: Número máximo de execuções a manter
        """
        self._executions: Dict[str, AgentExecutionResult] = {}
        self._history: List[str] = []
        self._max_history = max_history
        self._logger = get_logger("execution_tracker")

    def register(self, result: AgentExecutionResult) -> None:
        """
        Registra uma execução.

        Args:
            result: Resultado da execução
        """
        execution_id = result.execution_id

        self._executions[execution_id] = result
        self._history.append(execution_id)

        # Limitar histórico
        while len(self._history) > self._max_history:
            old_id = self._history.pop(0)
            if old_id in self._executions:
                del self._executions[old_id]

        self._logger.debug(
            "Execução registrada",
            execution_id=execution_id,
            agent_type=result.agent_type.value,
        )

    def get(self, execution_id: str) -> Optional[AgentExecutionResult]:
        """
        Obtém uma execução pelo ID.

        Args:
            execution_id: ID da execução

        Returns:
            AgentExecutionResult ou None
        """
        return self._executions.get(execution_id)

    def get_by_agent_type(
        self,
        agent_type: AgentType,
        limit: int = 10,
    ) -> List[AgentExecutionResult]:
        """
        Obtém execuções por tipo de agente.

        Args:
            agent_type: Tipo do agente
            limit: Número máximo de resultados

        Returns:
            Lista de execuções (mais recentes primeiro)
        """
        results = [
            self._executions[eid]
            for eid in reversed(self._history)
            if eid in self._executions
            and self._executions[eid].agent_type == agent_type
        ]
        return results[:limit]

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo de métricas de todas as execuções.

        Returns:
            Dicionário com métricas agregadas
        """
        if not self._executions:
            return {"total_executions": 0}

        total = len(self._executions)
        completed = sum(
            1 for r in self._executions.values()
            if r.status == AgentStatus.COMPLETED
        )
        failed = sum(
            1 for r in self._executions.values()
            if r.status == AgentStatus.FAILED
        )

        durations = [
            r.total_duration_ms
            for r in self._executions.values()
            if r.total_duration_ms > 0
        ]

        by_agent = {}
        for result in self._executions.values():
            agent_type = result.agent_type.value
            if agent_type not in by_agent:
                by_agent[agent_type] = {"count": 0, "completed": 0, "failed": 0}
            by_agent[agent_type]["count"] += 1
            if result.status == AgentStatus.COMPLETED:
                by_agent[agent_type]["completed"] += 1
            elif result.status == AgentStatus.FAILED:
                by_agent[agent_type]["failed"] += 1

        return {
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total if total > 0 else 0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "by_agent_type": by_agent,
        }


# Instância global
_execution_tracker: Optional[ExecutionTracker] = None


def get_execution_tracker() -> ExecutionTracker:
    """Retorna a instância global do rastreador de execuções."""
    global _execution_tracker
    if _execution_tracker is None:
        _execution_tracker = ExecutionTracker()
    return _execution_tracker
