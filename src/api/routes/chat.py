"""
Endpoints de chat conversacional.

Endpoint principal para interação com o sistema multi-agentes.
Recebe mensagens do usuário, processa através do orquestrador
e retorna respostas consolidadas com fontes e metadados.

As conversas são automaticamente persistidas no Cosmos DB,
permitindo histórico e continuidade entre sessões.
"""

import asyncio
import json
import time
from typing import AsyncGenerator, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.agents import create_orchestrator_agent, AgentStatus
from src.config.logging import get_logger
from src.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatError,
    SourceReference,
    AgentTrace,
    AgentTraceStep,
    StreamEventType,
)
from src.services.conversation_service import get_conversation_service

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _convert_sources(sources: list) -> list[SourceReference]:
    """
    Converte fontes do resultado do agente para o formato da API.

    Suporta múltiplos nomes de campos para compatibilidade com versões antigas.
    """
    converted = []
    for source in sources:
        # Fallback para diferentes nomes de campo de conteúdo
        content = (
            source.get("content_snippet") or
            source.get("content_preview") or  # Nome antigo
            source.get("content", "")[:200] if source.get("content") else None
        )

        # Fallback para diferentes nomes de campo de score
        score = (
            source.get("relevance_score") or
            source.get("score") or
            source.get("reranker_score") or
            source.get("vector_score")
        )

        converted.append(
            SourceReference(
                document_id=source.get("document_id"),
                document_name=source.get("document_name"),
                page_number=source.get("page_number"),
                section_title=source.get("section_title"),
                section_number=source.get("section_number"),
                content_snippet=content,
                relevance_score=float(score) if score else None,
            )
        )
    return converted


def _build_agent_trace(result, structured_output: dict) -> AgentTrace:
    """Constrói o trace de execução dos agentes para debug."""
    steps = []
    for step in result.steps:
        tool_calls = None
        if step.tool_call:
            tool_calls = [
                {
                    "tool_name": step.tool_call.tool_name,
                    "arguments": step.tool_call.arguments,
                }
            ]
        steps.append(
            AgentTraceStep(
                agent_name=result.agent_name,
                action=step.action,
                description=step.description,
                duration_ms=step.duration_ms,
                tool_calls=tool_calls,
            )
        )

    return AgentTrace(
        intent=structured_output.get("intent", "unknown"),
        intent_confidence=structured_output.get("intent_confidence"),
        agents_invoked=structured_output.get("agents_invoked", []),
        execution_mode=structured_output.get("execution_mode", "unknown"),
        steps=steps,
        tokens_used=result.tokens_used,
    )


@router.post(
    "/",
    response_model=ChatResponse,
    summary="Enviar mensagem ao assistente",
    description="""
Envia uma mensagem para o assistente HealthCost AI Copilot.

O sistema analisa a intenção da pergunta e aciona automaticamente
os agentes especializados apropriados.

## Persistência de Conversas

As conversas são **automaticamente salvas** no banco de dados:
- Se `conversation_id` não for fornecido, uma nova conversa é criada
- Se `conversation_id` for fornecido, a conversa existente é carregada
- O histórico é usado automaticamente para dar contexto às respostas
- Não é necessário enviar `conversation_history` manualmente

## Tipos de perguntas suportadas

### Perguntas sobre contratos
- "Qual o prazo de carência para cirurgias?"
- "O que diz a cláusula sobre cobertura hospitalar?"
- "Quais são as exclusões do plano?"

### Perguntas sobre custos
- "Quanto gastamos com internações em 2024?"
- "Qual a tendência de custos nos últimos 6 meses?"
- "Quais os procedimentos mais caros?"

### Perguntas sobre renegociação
- "Onde podemos economizar no próximo contrato?"
- "Quais cláusulas podem ser renegociadas?"
- "Qual o potencial de economia?"

## Parâmetros opcionais

- **contract_id**: Especifica um contrato específico para análise
- **conversation_id**: Continua uma conversa existente (busca histórico automaticamente)
- **conversation_history**: Histórico manual (ignorado se conversation_id existir)
- **include_sources**: Inclui referências de fontes na resposta (padrão: true)
- **include_debug**: Inclui informações de debug sobre execução dos agentes

## Exemplo de uso

```json
{
    "message": "Qual o prazo de carência para cirurgias?",
    "client_id": "cliente-123",
    "contract_id": "contrato-456"
}
```

## Continuando uma conversa

```json
{
    "message": "E para internações?",
    "client_id": "cliente-123",
    "conversation_id": "conv-abc123"
}
```
    """,
    responses={
        200: {
            "description": "Resposta do assistente",
            "model": ChatResponse,
        },
        400: {
            "description": "Erro de validação na requisição",
            "model": ChatError,
        },
        500: {
            "description": "Erro interno do servidor",
            "model": ChatError,
        },
    },
)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Processa uma mensagem do usuário e retorna a resposta do assistente.

    O endpoint coordena múltiplos agentes especializados para fornecer
    respostas precisas e fundamentadas sobre contratos e custos.

    As conversas são automaticamente persistidas, permitindo histórico
    e continuidade entre sessões.
    """
    start_time = time.time()

    logger.info(
        "Requisição de chat recebida",
        client_id=request.client_id,
        contract_id=request.contract_id,
        conversation_id=request.conversation_id,
        message_preview=request.message[:100] if len(request.message) > 100 else request.message,
    )

    try:
        # Obter serviço de conversas
        conversation_service = get_conversation_service()

        # Buscar ou criar conversa
        conversation = await conversation_service.get_or_create_conversation(
            client_id=request.client_id,
            conversation_id=request.conversation_id,
            contract_id=request.contract_id,
        )

        # Adicionar mensagem do usuário à conversa
        await conversation_service.add_user_message(
            conversation=conversation,
            content=request.message,
        )

        # Preparar contexto inteligente para o LLM
        # Usa o novo sistema de contexto com sumarização automática
        conversation_context = None
        conversation_history = None
        conversation_summary = None
        key_entities = None

        if conversation.message_count > 1:
            # Obter contexto otimizado com resumo + mensagens recentes
            conversation_context = await conversation_service.get_conversation_context(
                conversation=conversation,
                max_tokens=8000,  # Limite de tokens para histórico
                max_messages=15,  # Máximo de mensagens recentes
                include_summary=True,
                auto_summarize=True,  # Gera resumo automaticamente se necessário
            )

            # Extrair componentes do contexto
            conversation_history = conversation_context.get("messages", [])
            conversation_summary = conversation_context.get("summary")
            key_entities = conversation_context.get("key_entities")

            # Remove a última mensagem se for a atual (para não duplicar)
            if conversation_history and conversation_history[-1]["content"] == request.message:
                conversation_history = conversation_history[:-1]

            logger.debug(
                "Contexto de conversa preparado",
                has_summary=conversation_context.get("has_summary", False),
                message_count=len(conversation_history),
                total_tokens=conversation_context.get("total_tokens", 0),
            )

        elif request.conversation_history:
            # Usa histórico manual se não houver histórico persistido
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]

        # Criar o orquestrador
        orchestrator = create_orchestrator_agent()

        # Executar o orquestrador com contexto enriquecido
        if conversation_history or conversation_summary:
            result = await orchestrator.process_with_history(
                query=request.message,
                client_id=request.client_id,
                contract_id=request.contract_id,
                conversation_history=conversation_history,
                conversation_summary=conversation_summary,
                key_entities=key_entities,
            )
        else:
            result = await orchestrator.execute(
                query=request.message,
                client_id=request.client_id,
                contract_id=request.contract_id,
                conversation_id=str(conversation.id),
            )

        # Calcular tempo de execução
        execution_time_ms = (time.time() - start_time) * 1000

        # Verificar se a execução foi bem-sucedida
        if result.status == AgentStatus.FAILED:
            logger.error(
                "Falha na execução do orquestrador",
                error=result.error,
                execution_id=result.execution_id,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao processar mensagem: {result.error}",
            )

        # Extrair informações do resultado
        intent = result.structured_output.get("intent") if result.structured_output else None
        agents_invoked = result.structured_output.get("agents_invoked", []) if result.structured_output else []

        # Converter fontes para formato de lista de dicts para persistência
        sources_for_storage = result.sources if result.sources else []

        # Adicionar resposta do assistente à conversa
        await conversation_service.add_assistant_message(
            conversation=conversation,
            content=result.response or "Desculpe, não foi possível gerar uma resposta.",
            execution_id=result.execution_id,
            intent=intent,
            agents_invoked=agents_invoked,
            sources=sources_for_storage,
            tokens_used=result.tokens_used,
            execution_time_ms=execution_time_ms,
        )

        # Preparar fontes para a resposta
        sources = []
        if request.include_sources and result.sources:
            sources = _convert_sources(result.sources)

        # Preparar trace de debug
        agent_trace = None
        if request.include_debug and result.structured_output:
            agent_trace = _build_agent_trace(result, result.structured_output)

        # Construir resposta
        response = ChatResponse(
            response=result.response or "Desculpe, não foi possível gerar uma resposta.",
            conversation_id=str(conversation.id),
            execution_id=result.execution_id,
            sources=sources,
            agent_trace=agent_trace,
            execution_time_ms=execution_time_ms,
        )

        logger.info(
            "Chat processado com sucesso",
            conversation_id=str(conversation.id),
            execution_id=result.execution_id,
            execution_time_ms=execution_time_ms,
            intent=intent,
            agents_count=len(agents_invoked),
            total_messages=conversation.message_count,
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "Erro inesperado no chat",
            error=str(e),
            client_id=request.client_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar mensagem: {str(e)}",
        )


@router.post(
    "/simple",
    response_model=ChatResponse,
    summary="Chat simplificado (sem persistência)",
    description="""
Versão simplificada do endpoint de chat para testes rápidos.

**Atenção:** Esta versão NÃO persiste a conversa.
Use o endpoint principal `/chat` para funcionalidades completas.
    """,
)
async def chat_simple(
    message: str = Query(..., description="Mensagem do usuário"),
    client_id: str = Query(..., description="ID do cliente"),
    contract_id: Optional[str] = Query(None, description="ID do contrato"),
) -> ChatResponse:
    """Chat simplificado para testes rápidos (sem persistência)."""
    start_time = time.time()

    try:
        orchestrator = create_orchestrator_agent()

        result = await orchestrator.execute(
            query=message,
            client_id=client_id,
            contract_id=contract_id,
        )

        execution_time_ms = (time.time() - start_time) * 1000

        if result.status == AgentStatus.FAILED:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao processar mensagem: {result.error}",
            )

        sources = _convert_sources(result.sources) if result.sources else []

        return ChatResponse(
            response=result.response or "Desculpe, não foi possível gerar uma resposta.",
            conversation_id=str(uuid4()),  # ID temporário
            execution_id=result.execution_id,
            sources=sources,
            agent_trace=None,
            execution_time_ms=execution_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro no chat simples", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}",
        )


@router.post(
    "/stream",
    summary="Chat com streaming de status",
    description="""
Envia uma mensagem para o assistente com streaming de status em tempo real.

Retorna eventos Server-Sent Events (SSE) com atualizações de progresso
enquanto processa a solicitação, seguido da resposta final.

## Tipos de eventos

- **status**: Atualização de status do processamento
- **complete**: Resposta final com todos os dados
- **error**: Erro durante processamento

## Exemplo de uso (JavaScript)

```javascript
const eventSource = new EventSource('/api/v1/chat/stream?...');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.event === 'status') {
        showStatus(data.data.message);
    } else if (data.event === 'complete') {
        showResponse(data.data.response);
        eventSource.close();
    }
};
```
    """,
)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Chat com streaming de status em tempo real via SSE.

    Envia eventos de progresso durante o processamento e
    a resposta final quando concluído.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        """Gera eventos SSE durante o processamento."""
        start_time = time.time()
        event_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(step: str, message: str, agent: Optional[str]) -> None:
            """Callback que envia eventos de status."""
            event_data = {
                "event": StreamEventType.STATUS,
                "data": {
                    "step": step,
                    "message": message,
                    "agent": agent,
                }
            }
            await event_queue.put(event_data)

        async def process_chat() -> dict:
            """Processa o chat e retorna o resultado."""
            try:
                conversation_service = get_conversation_service()

                # Buscar ou criar conversa
                conversation = await conversation_service.get_or_create_conversation(
                    client_id=request.client_id,
                    conversation_id=request.conversation_id,
                    contract_id=request.contract_id,
                )

                # Adicionar mensagem do usuário
                await conversation_service.add_user_message(
                    conversation=conversation,
                    content=request.message,
                )

                # Preparar contexto
                conversation_history = None
                conversation_summary = None
                key_entities = None

                if conversation.message_count > 1:
                    conversation_context = await conversation_service.get_conversation_context(
                        conversation=conversation,
                        max_tokens=8000,
                        max_messages=15,
                        include_summary=True,
                        auto_summarize=True,
                    )
                    conversation_history = conversation_context.get("messages", [])
                    conversation_summary = conversation_context.get("summary")
                    key_entities = conversation_context.get("key_entities")

                    if conversation_history and conversation_history[-1]["content"] == request.message:
                        conversation_history = conversation_history[:-1]

                elif request.conversation_history:
                    conversation_history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in request.conversation_history
                    ]

                # Criar orquestrador e executar com callback de progresso
                orchestrator = create_orchestrator_agent()

                if conversation_history or conversation_summary:
                    result = await orchestrator.process_with_history(
                        query=request.message,
                        client_id=request.client_id,
                        contract_id=request.contract_id,
                        conversation_history=conversation_history,
                        conversation_summary=conversation_summary,
                        key_entities=key_entities,
                        progress_callback=progress_callback,
                    )
                else:
                    # Para execução sem histórico, configurar callback diretamente
                    orchestrator._progress_callback = progress_callback
                    result = await orchestrator.execute(
                        query=request.message,
                        client_id=request.client_id,
                        contract_id=request.contract_id,
                        conversation_id=str(conversation.id),
                    )

                execution_time_ms = (time.time() - start_time) * 1000

                # Verificar sucesso
                if result.status == AgentStatus.FAILED:
                    return {
                        "success": False,
                        "error": result.error or "Erro desconhecido",
                    }

                # Extrair informações
                intent = result.structured_output.get("intent") if result.structured_output else None
                agents_invoked = result.structured_output.get("agents_invoked", []) if result.structured_output else []
                sources_for_storage = result.sources if result.sources else []

                # Persistir resposta
                await conversation_service.add_assistant_message(
                    conversation=conversation,
                    content=result.response or "Desculpe, não foi possível gerar uma resposta.",
                    execution_id=result.execution_id,
                    intent=intent,
                    agents_invoked=agents_invoked,
                    sources=sources_for_storage,
                    tokens_used=result.tokens_used,
                    execution_time_ms=execution_time_ms,
                )

                # Converter fontes
                sources = []
                if request.include_sources and result.sources:
                    sources = [s.model_dump() if hasattr(s, 'model_dump') else s for s in _convert_sources(result.sources)]

                return {
                    "success": True,
                    "response": result.response or "Desculpe, não foi possível gerar uma resposta.",
                    "conversation_id": str(conversation.id),
                    "execution_id": result.execution_id,
                    "sources": sources,
                    "execution_time_ms": execution_time_ms,
                }

            except Exception as e:
                logger.error("Erro no chat stream", error=str(e), exc_info=True)
                return {
                    "success": False,
                    "error": str(e),
                }

        # Iniciar processamento em background
        process_task = asyncio.create_task(process_chat())

        # Enviar eventos de status enquanto processa
        try:
            while not process_task.done():
                try:
                    # Aguardar evento com timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    continue

            # Processar eventos restantes na fila
            while not event_queue.empty():
                event = await event_queue.get()
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # Obter resultado final
            result = await process_task

            if result["success"]:
                complete_event = {
                    "event": StreamEventType.COMPLETE,
                    "data": {
                        "response": result["response"],
                        "conversation_id": result["conversation_id"],
                        "execution_id": result["execution_id"],
                        "sources": result["sources"],
                        "execution_time_ms": result["execution_time_ms"],
                    }
                }
            else:
                complete_event = {
                    "event": StreamEventType.ERROR,
                    "data": {
                        "error": "processing_error",
                        "message": result["error"],
                    }
                }

            yield f"data: {json.dumps(complete_event, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("Erro no stream SSE", error=str(e), exc_info=True)
            error_event = {
                "event": StreamEventType.ERROR,
                "data": {
                    "error": "stream_error",
                    "message": str(e),
                }
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Desabilita buffering no nginx
        },
    )
