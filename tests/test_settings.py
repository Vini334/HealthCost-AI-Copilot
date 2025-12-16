"""
Testes para configurações da aplicação.
"""

import os
from unittest.mock import patch

import pytest


def test_settings_loads_from_env() -> None:
    """Testa se as configurações são carregadas das variáveis de ambiente."""
    # Limpar cache para forçar nova leitura
    from src.config.settings import get_settings
    get_settings.cache_clear()

    settings = get_settings()

    # Verifica que as configurações básicas estão presentes
    assert settings.azure_openai is not None
    assert settings.azure_search is not None
    assert settings.azure_storage is not None
    assert settings.cosmos is not None
    assert settings.app is not None


def test_settings_development_mode() -> None:
    """Testa a detecção de modo de desenvolvimento."""
    from src.config.settings import get_settings
    get_settings.cache_clear()

    settings = get_settings()

    # Em testes, deve estar em desenvolvimento
    assert settings.is_development is True
    assert settings.is_production is False


def test_azure_openai_settings() -> None:
    """Testa as configurações do Azure OpenAI."""
    from src.config.settings import get_settings
    get_settings.cache_clear()

    settings = get_settings()

    # Verifica que os campos existem
    assert hasattr(settings.azure_openai, "endpoint")
    assert hasattr(settings.azure_openai, "api_key")
    assert hasattr(settings.azure_openai, "deployment_name")
    assert hasattr(settings.azure_openai, "embedding_deployment")


def test_app_settings_defaults() -> None:
    """Testa os valores padrão das configurações da aplicação."""
    from src.config.settings import AppSettings

    # Criar com valores padrão (sem env vars)
    with patch.dict(os.environ, {}, clear=False):
        app_settings = AppSettings()

        assert app_settings.env in ["development", "staging", "production"]
        assert isinstance(app_settings.debug, bool)
        assert isinstance(app_settings.log_level, str)
