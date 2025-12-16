"""
Configuração de logging estruturado usando structlog.

Fornece logs em formato JSON para ambientes de produção
e formato colorido legível para desenvolvimento.
"""

import logging
import sys
from typing import Any, List, Optional

import structlog
from structlog.types import Processor

from src.config.settings import get_settings


def setup_logging() -> None:
    """
    Configura o logging estruturado da aplicação.

    Em desenvolvimento: logs coloridos e legíveis
    Em produção: logs em JSON para processamento
    """
    settings = get_settings()

    # Processadores compartilhados
    shared_processors: List[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if settings.is_development:
        # Desenvolvimento: logs coloridos e legíveis
        structlog.configure(
            processors=shared_processors
            + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                logging.getLevelName(settings.app.log_level)
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Produção: logs em JSON
        structlog.configure(
            processors=shared_processors
            + [
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                logging.getLevelName(settings.app.log_level)
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Configurar logging padrão do Python para integração
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.app.log_level),
    )

    # Silenciar logs verbosos de bibliotecas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None, **initial_context: Any) -> structlog.BoundLogger:
    """
    Retorna um logger configurado.

    Args:
        name: Nome do módulo/componente para o logger
        **initial_context: Contexto inicial para adicionar aos logs

    Returns:
        Logger estruturado configurado
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger
