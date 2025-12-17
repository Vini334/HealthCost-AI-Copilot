"""
Endpoints de gerenciamento de conversas.

Permite listar, visualizar e gerenciar conversas de chat
persistidas no Cosmos DB.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from src.config.logging import get_logger
from src.models.conversations import (
    Conversation,
    ConversationStatus,
    ConversationListResponse,
    ConversationDetailResponse,
    ConversationSummary,
    CreateConversationRequest,
    UpdateConversationRequest,
)
from src.services.conversation_service import get_conversation_service

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get(
    "/",
    response_model=ConversationListResponse,
    summary="Listar conversas",
    description="""
Lista todas as conversas de um cliente.

## Filtros disponíveis

- **contract_id**: Filtra por contrato específico
- **status**: Filtra por status (active, archived, deleted)

## Paginação

Use `limit` e `offset` para paginar resultados.

## Exemplo de resposta

```json
{
    "conversations": [
        {
            "id": "conv-123",
            "client_id": "cliente-123",
            "title": "Qual o prazo de carência...",
            "message_count": 5,
            "last_message_at": "2024-12-16T10:30:00Z"
        }
    ],
    "total_count": 42,
    "has_more": true
}
```
    """,
)
async def list_conversations(
    client_id: str = Query(..., description="ID do cliente"),
    contract_id: Optional[str] = Query(None, description="Filtrar por contrato"),
    status: Optional[ConversationStatus] = Query(None, description="Filtrar por status"),
    limit: int = Query(20, ge=1, le=100, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Pular primeiros N resultados"),
) -> ConversationListResponse:
    """Lista conversas de um cliente."""
    logger.info(
        "Listando conversas",
        client_id=client_id,
        contract_id=contract_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    try:
        conversation_service = get_conversation_service()

        summaries, total, has_more = await conversation_service.list_conversations(
            client_id=client_id,
            contract_id=contract_id,
            status=status,
            limit=limit,
            offset=offset,
        )

        return ConversationListResponse(
            conversations=summaries,
            total_count=total,
            has_more=has_more,
        )

    except Exception as e:
        logger.error("Erro ao listar conversas", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar conversas: {str(e)}",
        )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Obter conversa",
    description="""
Retorna detalhes completos de uma conversa, incluindo todas as mensagens.

## Parâmetros

- **conversation_id**: ID da conversa
- **client_id**: ID do cliente (necessário para validação de acesso)

## Resposta

Inclui todas as mensagens com metadados de execução (intent, agentes, fontes).
    """,
)
async def get_conversation(
    conversation_id: str,
    client_id: str = Query(..., description="ID do cliente"),
) -> ConversationDetailResponse:
    """Retorna detalhes de uma conversa."""
    logger.info(
        "Buscando conversa",
        conversation_id=conversation_id,
        client_id=client_id,
    )

    try:
        conversation_service = get_conversation_service()

        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            client_id=client_id,
        )

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversa não encontrada: {conversation_id}",
            )

        return ConversationDetailResponse(
            id=conversation.id,
            client_id=conversation.client_id,
            contract_id=conversation.contract_id,
            title=conversation.title,
            status=conversation.status,
            messages=conversation.messages,
            message_count=conversation.message_count,
            total_tokens_used=conversation.total_tokens_used,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao buscar conversa", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar conversa: {str(e)}",
        )


@router.post(
    "/",
    response_model=ConversationDetailResponse,
    summary="Criar conversa",
    description="""
Cria uma nova conversa vazia.

Normalmente não é necessário usar este endpoint, pois o endpoint
`/chat` cria conversas automaticamente. Use apenas se precisar
criar uma conversa sem enviar mensagem.
    """,
)
async def create_conversation(
    request: CreateConversationRequest,
) -> ConversationDetailResponse:
    """Cria uma nova conversa."""
    logger.info(
        "Criando conversa",
        client_id=request.client_id,
        contract_id=request.contract_id,
    )

    try:
        conversation_service = get_conversation_service()

        conversation = await conversation_service.create_conversation(
            client_id=request.client_id,
            contract_id=request.contract_id,
            title=request.title,
            initial_message=request.initial_message,
        )

        return ConversationDetailResponse(
            id=conversation.id,
            client_id=conversation.client_id,
            contract_id=conversation.contract_id,
            title=conversation.title,
            status=conversation.status,
            messages=conversation.messages,
            message_count=conversation.message_count,
            total_tokens_used=conversation.total_tokens_used,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    except Exception as e:
        logger.error("Erro ao criar conversa", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao criar conversa: {str(e)}",
        )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Atualizar conversa",
    description="""
Atualiza título ou status de uma conversa.

## Exemplos de uso

### Renomear conversa
```json
{
    "title": "Análise de carências do contrato X"
}
```

### Arquivar conversa
```json
{
    "status": "archived"
}
```
    """,
)
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    client_id: str = Query(..., description="ID do cliente"),
) -> ConversationDetailResponse:
    """Atualiza uma conversa."""
    logger.info(
        "Atualizando conversa",
        conversation_id=conversation_id,
        client_id=client_id,
        title=request.title,
        status=request.status,
    )

    try:
        conversation_service = get_conversation_service()

        # Busca conversa atual
        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            client_id=client_id,
        )

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversa não encontrada: {conversation_id}",
            )

        # Atualiza campos
        if request.title is not None:
            conversation = await conversation_service.update_conversation_title(
                conversation_id=conversation_id,
                client_id=client_id,
                title=request.title,
            )

        if request.status is not None:
            if request.status == ConversationStatus.ARCHIVED:
                conversation = await conversation_service.archive_conversation(
                    conversation_id=conversation_id,
                    client_id=client_id,
                )
            # Outros status podem ser implementados conforme necessário

        # Busca conversa atualizada
        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            client_id=client_id,
        )

        return ConversationDetailResponse(
            id=conversation.id,
            client_id=conversation.client_id,
            contract_id=conversation.contract_id,
            title=conversation.title,
            status=conversation.status,
            messages=conversation.messages,
            message_count=conversation.message_count,
            total_tokens_used=conversation.total_tokens_used,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao atualizar conversa", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao atualizar conversa: {str(e)}",
        )


@router.delete(
    "/{conversation_id}",
    summary="Remover conversa",
    description="""
Remove permanentemente uma conversa e todo seu histórico.

**Atenção:** Esta ação é irreversível.
    """,
)
async def delete_conversation(
    conversation_id: str,
    client_id: str = Query(..., description="ID do cliente"),
) -> dict:
    """Remove uma conversa."""
    logger.info(
        "Removendo conversa",
        conversation_id=conversation_id,
        client_id=client_id,
    )

    try:
        conversation_service = get_conversation_service()

        deleted = await conversation_service.delete_conversation(
            conversation_id=conversation_id,
            client_id=client_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Conversa não encontrada: {conversation_id}",
            )

        return {
            "message": "Conversa removida com sucesso",
            "conversation_id": conversation_id,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao remover conversa", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao remover conversa: {str(e)}",
        )


@router.delete(
    "/{conversation_id}/messages/{message_id}",
    summary="Remover mensagem",
    description="""
Remove uma mensagem específica de uma conversa.

**Atenção:** Esta ação é irreversível. A mensagem e todos os seus
metadados (fontes, execução, etc.) serão permanentemente removidos.

Se a mensagem removida era uma pergunta do usuário, a resposta
correspondente permanece (e vice-versa).
    """,
)
async def delete_message(
    conversation_id: str,
    message_id: str,
    client_id: str = Query(..., description="ID do cliente"),
) -> dict:
    """Remove uma mensagem de uma conversa."""
    logger.info(
        "Removendo mensagem",
        conversation_id=conversation_id,
        message_id=message_id,
        client_id=client_id,
    )

    try:
        conversation_service = get_conversation_service()

        deleted = await conversation_service.delete_message(
            conversation_id=conversation_id,
            client_id=client_id,
            message_id=message_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Mensagem não encontrada: {message_id}",
            )

        return {
            "message": "Mensagem removida com sucesso",
            "conversation_id": conversation_id,
            "message_id": message_id,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao remover mensagem", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao remover mensagem: {str(e)}",
        )


@router.get(
    "/{conversation_id}/messages",
    summary="Listar mensagens",
    description="""
Lista mensagens de uma conversa com paginação.

Útil para conversas muito longas onde não se deseja
carregar todas as mensagens de uma vez.
    """,
)
async def list_messages(
    conversation_id: str,
    client_id: str = Query(..., description="ID do cliente"),
    limit: int = Query(50, ge=1, le=100, description="Máximo de mensagens"),
    offset: int = Query(0, ge=0, description="Pular primeiras N mensagens"),
) -> dict:
    """Lista mensagens de uma conversa."""
    logger.info(
        "Listando mensagens",
        conversation_id=conversation_id,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )

    try:
        conversation_service = get_conversation_service()

        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            client_id=client_id,
        )

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversa não encontrada: {conversation_id}",
            )

        # Aplica paginação
        total = len(conversation.messages)
        messages = conversation.messages[offset:offset + limit]
        has_more = (offset + len(messages)) < total

        return {
            "conversation_id": conversation_id,
            "messages": [msg.model_dump(mode="json") for msg in messages],
            "total_count": total,
            "has_more": has_more,
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Erro ao listar mensagens", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar mensagens: {str(e)}",
        )
