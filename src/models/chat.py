"""
Modelos e schemas para o sistema de chat.

Define tipos e schemas Pydantic para representar
requisições e respostas do endpoint de chat.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessageHistory(BaseModel):
    """Mensagem no histórico da conversa."""

    role: str = Field(
        ...,
        description="Papel: 'user' ou 'assistant'",
        pattern="^(user|assistant)$",
    )
    content: str = Field(..., description="Conteúdo da mensagem")
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Momento da mensagem (opcional)"
    )


class ChatRequest(BaseModel):
    """Requisição para o endpoint de chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Mensagem do usuário",
    )
    client_id: str = Field(
        ...,
        min_length=1,
        description="ID do cliente para filtrar dados",
    )
    contract_id: Optional[str] = Field(
        default=None,
        description="ID do contrato específico (opcional)",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="ID da conversa para continuidade (opcional)",
    )
    conversation_history: Optional[List[ChatMessageHistory]] = Field(
        default=None,
        description="Histórico de mensagens anteriores (opcional)",
    )
    include_sources: bool = Field(
        default=True,
        description="Incluir fontes/citações na resposta",
    )
    include_debug: bool = Field(
        default=False,
        description="Incluir informações de debug (agent_trace)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Qual o prazo de carência para cirurgias?",
                    "client_id": "cliente-123",
                    "contract_id": "contrato-456",
                },
                {
                    "message": "Quanto gastamos com internações em 2024?",
                    "client_id": "cliente-123",
                    "include_sources": True,
                    "include_debug": False,
                },
            ]
        }
    }


class SourceReference(BaseModel):
    """Referência a uma fonte usada na resposta."""

    document_id: Optional[str] = Field(
        default=None,
        description="ID do documento fonte",
    )
    document_name: Optional[str] = Field(
        default=None,
        description="Nome do documento",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Número da página",
    )
    section_title: Optional[str] = Field(
        default=None,
        description="Título da seção",
    )
    section_number: Optional[str] = Field(
        default=None,
        description="Número da seção/cláusula",
    )
    content_snippet: Optional[str] = Field(
        default=None,
        description="Trecho relevante do conteúdo",
    )
    relevance_score: Optional[float] = Field(
        default=None,
        description="Score de relevância (0-1)",
    )


class AgentTraceStep(BaseModel):
    """Passo de execução de um agente (para debug)."""

    agent_name: str = Field(..., description="Nome do agente")
    action: str = Field(..., description="Ação realizada")
    description: str = Field(..., description="Descrição do passo")
    duration_ms: float = Field(default=0.0, description="Duração em ms")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Chamadas de ferramentas realizadas",
    )


class AgentTrace(BaseModel):
    """Trace completo da execução dos agentes (para debug)."""

    intent: str = Field(..., description="Intenção detectada")
    intent_confidence: Optional[float] = Field(
        default=None,
        description="Confiança na detecção de intent (0-1)",
    )
    agents_invoked: List[str] = Field(
        default_factory=list,
        description="Lista de agentes acionados",
    )
    execution_mode: str = Field(
        default="unknown",
        description="Modo de execução (parallel, sequential, etc)",
    )
    steps: List[AgentTraceStep] = Field(
        default_factory=list,
        description="Passos de execução",
    )
    tokens_used: Optional[int] = Field(
        default=None,
        description="Total de tokens consumidos",
    )


class ChatResponse(BaseModel):
    """Resposta do endpoint de chat."""

    response: str = Field(
        ...,
        description="Resposta do assistente",
    )
    conversation_id: str = Field(
        ...,
        description="ID da conversa (novo ou existente)",
    )
    execution_id: str = Field(
        ...,
        description="ID único desta execução",
    )
    sources: List[SourceReference] = Field(
        default_factory=list,
        description="Fontes citadas na resposta",
    )
    agent_trace: Optional[AgentTrace] = Field(
        default=None,
        description="Informações de debug (se solicitado)",
    )
    execution_time_ms: float = Field(
        ...,
        description="Tempo total de execução em ms",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Momento da resposta",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "response": "O prazo de carência para cirurgias é de 180 dias, conforme estabelecido na Cláusula 5.2 do contrato.",
                    "conversation_id": "conv-789",
                    "execution_id": "exec-abc123",
                    "sources": [
                        {
                            "document_name": "Contrato_2024.pdf",
                            "page_number": 12,
                            "section_title": "Das Carências",
                            "section_number": "5.2",
                        }
                    ],
                    "execution_time_ms": 2345.6,
                    "created_at": "2024-12-16T10:30:00Z",
                }
            ]
        }
    }


class ChatError(BaseModel):
    """Resposta de erro do endpoint de chat."""

    error: str = Field(..., description="Tipo do erro")
    message: str = Field(..., description="Mensagem de erro")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detalhes adicionais do erro",
    )
