"""
Endpoints de health check da aplicação.

Fornece endpoints para verificação de saúde do serviço,
utilizados pelo orquestrador de containers e monitoramento.
"""

from typing import Dict

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Resposta do endpoint de health check."""

    status: str
    version: str


class ReadinessResponse(BaseModel):
    """Resposta do endpoint de readiness com detalhes dos serviços."""

    status: str
    version: str
    services: Dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check básico da aplicação.

    Retorna status "healthy" se a aplicação está rodando.
    Este endpoint não verifica dependências externas.
    """
    return HealthResponse(status="healthy", version="0.1.0")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """
    Readiness check com verificação de dependências.

    Verifica se todos os serviços necessários estão acessíveis.
    Usado pelo Kubernetes/Container Apps para determinar se o pod
    está pronto para receber tráfego.
    """
    # TODO: Implementar verificação real das dependências Azure
    # Por enquanto retorna status básico
    services = {
        "azure_openai": "not_checked",
        "azure_search": "not_checked",
        "azure_storage": "not_checked",
        "cosmos_db": "not_checked",
    }

    return ReadinessResponse(
        status="ready",
        version="0.1.0",
        services=services,
    )
