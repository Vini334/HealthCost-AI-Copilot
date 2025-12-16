"""
Rotas da API v1.

Organiza os endpoints em módulos por funcionalidade.
"""

from src.api.routes.upload import router as upload_router
from src.api.routes.documents import router as documents_router
from src.api.routes.costs import router as costs_router

__all__ = ["upload_router", "documents_router", "costs_router"]
