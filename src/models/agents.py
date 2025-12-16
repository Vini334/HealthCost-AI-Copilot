"""
Modelos e schemas para o sistema de agentes.

Define tipos, enums e schemas Pydantic para representar
agentes, ferramentas, contextos e resultados de execução.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Tipos de agentes disponíveis no sistema."""

    ORCHESTRATOR = "orchestrator"
    RETRIEVAL = "retrieval"
    CONTRACT_ANALYST = "contract_analyst"
    COST_INSIGHTS = "cost_insights"
    NEGOTIATION_ADVISOR = "negotiation_advisor"


class AgentStatus(str, Enum):
    """Status de execução de um agente."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolResultStatus(str, Enum):
    """Status do resultado de uma ferramenta."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class ToolParameter(BaseModel):
    """Parâmetro de uma ferramenta."""

    name: str = Field(..., description="Nome do parâmetro")
    type: str = Field(..., description="Tipo do parâmetro (string, int, float, bool, list, dict)")
    description: str = Field(..., description="Descrição do parâmetro")
    required: bool = Field(default=True, description="Se o parâmetro é obrigatório")
    default: Optional[Any] = Field(default=None, description="Valor padrão")


class ToolDefinition(BaseModel):
    """Definição de uma ferramenta disponível para agentes."""

    name: str = Field(..., description="Nome único da ferramenta")
    description: str = Field(..., description="Descrição do que a ferramenta faz")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Parâmetros da ferramenta")
    return_type: str = Field(default="any", description="Tipo de retorno")

    def to_openai_function(self) -> Dict[str, Any]:
        """Converte para formato de function do OpenAI."""
        properties = {}
        required = []

        for param in self.parameters:
            type_mapping = {
                "string": "string",
                "str": "string",
                "int": "integer",
                "integer": "integer",
                "float": "number",
                "number": "number",
                "bool": "boolean",
                "boolean": "boolean",
                "list": "array",
                "array": "array",
                "dict": "object",
                "object": "object",
            }

            properties[param.name] = {
                "type": type_mapping.get(param.type.lower(), "string"),
                "description": param.description,
            }

            if param.default is not None:
                properties[param.name]["default"] = param.default

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolCall(BaseModel):
    """Chamada a uma ferramenta."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="ID único da chamada")
    tool_name: str = Field(..., description="Nome da ferramenta chamada")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Argumentos passados")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Momento da chamada")


class ToolResult(BaseModel):
    """Resultado de uma chamada de ferramenta."""

    call_id: str = Field(..., description="ID da chamada correspondente")
    tool_name: str = Field(..., description="Nome da ferramenta")
    status: ToolResultStatus = Field(..., description="Status do resultado")
    result: Optional[Any] = Field(default=None, description="Resultado da execução")
    error: Optional[str] = Field(default=None, description="Mensagem de erro se houver")
    execution_time_ms: float = Field(default=0.0, description="Tempo de execução em ms")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Momento do resultado")


class AgentMessage(BaseModel):
    """Mensagem trocada com/por um agente."""

    role: str = Field(..., description="Papel: system, user, assistant, tool")
    content: Optional[str] = Field(default=None, description="Conteúdo da mensagem")
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Chamadas de ferramentas")
    tool_result: Optional[ToolResult] = Field(default=None, description="Resultado de ferramenta")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Momento da mensagem")


class AgentContext(BaseModel):
    """Contexto de execução de um agente."""

    # Identificação
    execution_id: str = Field(default_factory=lambda: str(uuid4()), description="ID único da execução")
    client_id: str = Field(..., description="ID do cliente")
    contract_id: Optional[str] = Field(default=None, description="ID do contrato (se aplicável)")
    conversation_id: Optional[str] = Field(default=None, description="ID da conversa")

    # Query original
    query: str = Field(..., description="Pergunta/comando original do usuário")

    # Histórico
    messages: List[AgentMessage] = Field(default_factory=list, description="Histórico de mensagens")

    # Dados recuperados
    retrieved_chunks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Chunks recuperados do RAG"
    )
    cost_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dados de custos carregados"
    )

    # Metadados
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados adicionais")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Momento de criação")

    def add_message(
        self,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        tool_result: Optional[ToolResult] = None,
    ) -> AgentMessage:
        """Adiciona uma mensagem ao histórico."""
        message = AgentMessage(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_result=tool_result,
        )
        self.messages.append(message)
        return message

    def get_messages_for_llm(self) -> List[Dict[str, Any]]:
        """Retorna mensagens formatadas para envio ao LLM."""
        llm_messages = []

        for msg in self.messages:
            if msg.role == "tool" and msg.tool_result:
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_result.call_id,
                    "content": str(msg.tool_result.result) if msg.tool_result.result else msg.tool_result.error or "",
                })
            elif msg.tool_calls:
                llm_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.tool_name,
                                "arguments": str(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })
            else:
                llm_messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })

        return llm_messages


class AgentExecutionStep(BaseModel):
    """Um passo de execução do agente."""

    step_number: int = Field(..., description="Número do passo")
    action: str = Field(..., description="Ação realizada (think, tool_call, respond)")
    description: str = Field(..., description="Descrição do que foi feito")
    tool_call: Optional[ToolCall] = Field(default=None, description="Chamada de ferramenta se houver")
    tool_result: Optional[ToolResult] = Field(default=None, description="Resultado da ferramenta")
    duration_ms: float = Field(default=0.0, description="Duração do passo em ms")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Momento do passo")


class AgentExecutionResult(BaseModel):
    """Resultado completo da execução de um agente."""

    # Identificação
    execution_id: str = Field(..., description="ID único da execução")
    agent_type: AgentType = Field(..., description="Tipo do agente")
    agent_name: str = Field(..., description="Nome do agente")

    # Status
    status: AgentStatus = Field(..., description="Status final")

    # Resultado
    response: Optional[str] = Field(default=None, description="Resposta textual")
    structured_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Saída estruturada se aplicável"
    )

    # Rastreamento
    steps: List[AgentExecutionStep] = Field(default_factory=list, description="Passos executados")
    tool_calls_count: int = Field(default=0, description="Total de chamadas de ferramentas")

    # Métricas
    total_duration_ms: float = Field(default=0.0, description="Duração total em ms")
    tokens_used: Optional[int] = Field(default=None, description="Tokens consumidos")

    # Fontes e evidências
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Fontes citadas (chunks, páginas)"
    )

    # Erros
    error: Optional[str] = Field(default=None, description="Mensagem de erro se houver")

    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Início")
    completed_at: Optional[datetime] = Field(default=None, description="Conclusão")

    def add_step(
        self,
        action: str,
        description: str,
        tool_call: Optional[ToolCall] = None,
        tool_result: Optional[ToolResult] = None,
        duration_ms: float = 0.0,
    ) -> AgentExecutionStep:
        """Adiciona um passo de execução."""
        step = AgentExecutionStep(
            step_number=len(self.steps) + 1,
            action=action,
            description=description,
            tool_call=tool_call,
            tool_result=tool_result,
            duration_ms=duration_ms,
        )
        self.steps.append(step)

        if tool_call:
            self.tool_calls_count += 1

        return step

    def finalize(
        self,
        status: AgentStatus,
        response: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Finaliza a execução."""
        self.status = status
        self.response = response
        self.error = error
        self.completed_at = datetime.utcnow()

        if self.completed_at and self.started_at:
            self.total_duration_ms = (
                self.completed_at - self.started_at
            ).total_seconds() * 1000


class OrchestratorDecision(BaseModel):
    """Decisão do orquestrador sobre quais agentes acionar."""

    query_intent: str = Field(..., description="Intenção detectada na query")
    agents_to_invoke: List[AgentType] = Field(..., description="Agentes a serem acionados")
    execution_mode: str = Field(
        default="parallel",
        description="Modo de execução: parallel ou sequential"
    )
    reasoning: str = Field(..., description="Raciocínio da decisão")
    priority_order: Optional[List[AgentType]] = Field(
        default=None,
        description="Ordem de prioridade se sequential"
    )
