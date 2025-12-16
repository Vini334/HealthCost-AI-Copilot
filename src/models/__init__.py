"""
Modelos de dados da aplicação.

Exporta todos os modelos Pydantic usados pela API.
"""

from src.models.documents import (
    # Enums
    DocumentType,
    DocumentStatus,
    # Modelos principais
    DocumentMetadata,
    # Modelos de API
    UploadResponse,
    UploadError,
    DocumentListResponse,
    # Constantes
    MAX_FILE_SIZE_MB,
    MAX_FILE_SIZE_BYTES,
    ALLOWED_CONTRACT_TYPES,
    ALLOWED_COST_TYPES,
    ALLOWED_CONTRACT_EXTENSIONS,
    ALLOWED_COST_EXTENSIONS,
)

from src.models.chunks import (
    # Enums
    ChunkingStrategy,
    # Modelos principais
    DocumentChunk,
    ProcessingResult,
    ChunkingConfig,
    # Configuração padrão
    DEFAULT_CHUNKING_CONFIG,
)

from src.models.costs import (
    # Enums
    CostCategory,
    UtilizationType,
    # Modelos principais
    CostRecord,
    ColumnMapping,
    ColumnValidationResult,
    CostProcessingResult,
    # Agregações
    CostSummary,
    CostSummaryByCategory,
    CostSummaryByPeriod,
    # Constantes
    COLUMN_ALIASES,
    DEFAULT_COLUMN_MAPPING,
)

from src.models.agents import (
    # Enums
    AgentType,
    AgentStatus,
    ToolResultStatus,
    # Modelos de ferramentas
    ToolParameter,
    ToolDefinition,
    ToolCall,
    ToolResult,
    # Modelos de contexto
    AgentMessage,
    AgentContext,
    # Modelos de execução
    AgentExecutionStep,
    AgentExecutionResult,
    # Orquestração
    OrchestratorDecision,
)

__all__ = [
    # Documents
    "DocumentType",
    "DocumentStatus",
    "DocumentMetadata",
    "UploadResponse",
    "UploadError",
    "DocumentListResponse",
    "MAX_FILE_SIZE_MB",
    "MAX_FILE_SIZE_BYTES",
    "ALLOWED_CONTRACT_TYPES",
    "ALLOWED_COST_TYPES",
    "ALLOWED_CONTRACT_EXTENSIONS",
    "ALLOWED_COST_EXTENSIONS",
    # Chunks
    "ChunkingStrategy",
    "DocumentChunk",
    "ProcessingResult",
    "ChunkingConfig",
    "DEFAULT_CHUNKING_CONFIG",
    # Costs
    "CostCategory",
    "UtilizationType",
    "CostRecord",
    "ColumnMapping",
    "ColumnValidationResult",
    "CostProcessingResult",
    "CostSummary",
    "CostSummaryByCategory",
    "CostSummaryByPeriod",
    "COLUMN_ALIASES",
    "DEFAULT_COLUMN_MAPPING",
    # Agents
    "AgentType",
    "AgentStatus",
    "ToolResultStatus",
    "ToolParameter",
    "ToolDefinition",
    "ToolCall",
    "ToolResult",
    "AgentMessage",
    "AgentContext",
    "AgentExecutionStep",
    "AgentExecutionResult",
    "OrchestratorDecision",
]
