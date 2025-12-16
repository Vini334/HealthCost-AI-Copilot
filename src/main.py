"""
Ponto de entrada principal da aplicação FastAPI.

HealthCost AI Copilot - Assistente de IA para auditoria de planos de saúde.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.health import router as health_router
from src.api.routes.upload import router as upload_router
from src.api.routes.documents import router as documents_router
from src.api.routes.search import router as search_router
from src.api.routes.costs import router as costs_router
from src.config.logging import setup_logging, get_logger
from src.config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gerencia o ciclo de vida da aplicação.

    Executa setup no startup e cleanup no shutdown.
    """
    # Startup
    setup_logging()
    logger = get_logger("startup")

    settings = get_settings()
    logger.info(
        "Iniciando HealthCost AI Copilot",
        environment=settings.app.env,
        debug=settings.app.debug,
    )

    yield

    # Shutdown
    logger.info("Encerrando aplicação")


def create_app() -> FastAPI:
    """
    Factory function para criar a aplicação FastAPI.

    Returns:
        Instância configurada do FastAPI
    """
    settings = get_settings()

    app = FastAPI(
        title="HealthCost AI Copilot",
        description="Assistente de IA para auditoria de contratos e custos de planos de saúde",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Configurar CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Registrar routers
    app.include_router(health_router)

    # Router para API v1
    # O prefixo /api/v1 é adicionado aqui
    app.include_router(upload_router, prefix="/api/v1")      # /api/v1/upload/*
    app.include_router(documents_router, prefix="/api/v1")   # /api/v1/documents/*
    app.include_router(search_router, prefix="/api/v1")      # /api/v1/search/*
    app.include_router(costs_router, prefix="/api/v1")       # /api/v1/costs/*

    # Routers futuros (serão ativados nas próximas fases)
    # app.include_router(chat_router, prefix="/api/v1")
    # app.include_router(clients_router, prefix="/api/v1")

    return app


# Instância da aplicação para uvicorn
app = create_app()
