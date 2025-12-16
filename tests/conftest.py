"""
Configuração de fixtures para testes pytest.
"""

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Configurar variáveis de ambiente para testes ANTES de importar a app
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_SEARCH_ENDPOINT", "https://test.search.windows.net")
os.environ.setdefault("AZURE_SEARCH_API_KEY", "test-key")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
os.environ.setdefault("COSMOS_ENDPOINT", "https://test.documents.azure.com:443/")
os.environ.setdefault("COSMOS_KEY", "test-key")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_DEBUG", "true")

from src.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Fixture que fornece um cliente de teste para a API.

    Yields:
        TestClient configurado para a aplicação
    """
    with TestClient(app) as test_client:
        yield test_client
