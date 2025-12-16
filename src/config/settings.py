"""
Configurações da aplicação usando Pydantic Settings.

Carrega variáveis de ambiente e valida configurações necessárias.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureOpenAISettings(BaseSettings):
    """Configurações do Azure OpenAI."""

    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_")

    endpoint: str = Field(..., description="Endpoint do Azure OpenAI")
    api_key: str = Field(..., description="API Key do Azure OpenAI")
    api_version: str = Field(default="2024-02-01", description="Versão da API")
    deployment_name: str = Field(
        default="gpt-4o", description="Nome do deployment do modelo"
    )
    embedding_deployment: str = Field(
        default="text-embedding-3-small", description="Nome do deployment de embeddings"
    )


class AzureSearchSettings(BaseSettings):
    """Configurações do Azure AI Search."""

    model_config = SettingsConfigDict(env_prefix="AZURE_SEARCH_")

    endpoint: str = Field(..., description="Endpoint do Azure AI Search")
    api_key: str = Field(..., description="API Key do Azure AI Search")
    index_name: str = Field(
        default="contracts-index", description="Nome do índice de contratos"
    )


class AzureStorageSettings(BaseSettings):
    """Configurações do Azure Blob Storage."""

    model_config = SettingsConfigDict(env_prefix="AZURE_STORAGE_")

    connection_string: str = Field(..., description="Connection string do Storage")
    container_contracts: str = Field(
        default="contracts", description="Container para contratos"
    )
    container_costs: str = Field(default="costs", description="Container para custos")
    container_processed: str = Field(
        default="processed", description="Container para arquivos processados"
    )


class CosmosDBSettings(BaseSettings):
    """Configurações do Azure Cosmos DB."""

    model_config = SettingsConfigDict(env_prefix="COSMOS_")

    endpoint: str = Field(..., description="Endpoint do Cosmos DB")
    key: str = Field(..., description="Key do Cosmos DB")
    database: str = Field(default="healthcost", description="Nome do database")
    container_conversations: str = Field(
        default="conversations", description="Container de conversas"
    )
    container_clients: str = Field(
        default="clients", description="Container de clientes"
    )


class AppSettings(BaseSettings):
    """Configurações gerais da aplicação."""

    model_config = SettingsConfigDict(env_prefix="APP_")

    env: Literal["development", "staging", "production"] = Field(
        default="development", description="Ambiente da aplicação"
    )
    debug: bool = Field(default=False, description="Modo debug")
    log_level: str = Field(default="INFO", description="Nível de log")


class Settings(BaseSettings):
    """Configurações consolidadas da aplicação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-configurações
    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    azure_search: AzureSearchSettings = Field(default_factory=AzureSearchSettings)
    azure_storage: AzureStorageSettings = Field(default_factory=AzureStorageSettings)
    cosmos: CosmosDBSettings = Field(default_factory=CosmosDBSettings)
    app: AppSettings = Field(default_factory=AppSettings)

    # API Key para proteger endpoints
    api_key: str = Field(
        default="change-me-in-production", description="API Key para endpoints"
    )

    @property
    def is_development(self) -> bool:
        """Verifica se está em ambiente de desenvolvimento."""
        return self.app.env == "development"

    @property
    def is_production(self) -> bool:
        """Verifica se está em ambiente de produção."""
        return self.app.env == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.

    Usar esta função ao invés de instanciar Settings diretamente
    para aproveitar o cache e evitar múltiplas leituras do .env.
    """
    return Settings()
