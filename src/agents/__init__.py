"""
Sistema multi-agente para o HealthCost AI Copilot.

Este módulo implementa a arquitetura de agentes especializados:
- BaseAgent: classe base para todos os agentes
- RetrievalAgent: agente de recuperação de informações
- Sistema de Tools: ferramentas disponíveis para agentes
- ContextManager: gerenciamento de contexto de execução
- ExecutionLogger: logging e rastreamento de execuções

Uso básico:
    from src.agents import RetrievalAgent, get_tool_registry

    # Criar e executar o agente de recuperação
    agent = RetrievalAgent()
    result = await agent.execute(
        query="Qual o prazo de carência?",
        client_id="cliente-123",
        contract_id="contrato-456",
    )

    # Acessar chunks recuperados
    chunks = result.structured_output["chunks"]

Criar agente personalizado:
    from src.agents import BaseAgent, AgentType

    class MyAgent(BaseAgent):
        agent_type = AgentType.CONTRACT_ANALYST
        agent_name = "my_agent"
        system_prompt = "Você é um agente especializado..."

        def get_tools(self) -> List[str]:
            return ["search_hybrid"]

        async def process(self, context: AgentContext) -> AgentExecutionResult:
            # implementação
            pass
"""

# Classe base e agentes
from src.agents.base import BaseAgent, SimpleAgent

# Agentes especializados
from src.agents.retrieval_agent import RetrievalAgent, create_retrieval_agent
from src.agents.contract_analyst_agent import ContractAnalystAgent, create_contract_analyst_agent
from src.agents.cost_insights_agent import CostInsightsAgent, create_cost_insights_agent
from src.agents.negotiation_advisor_agent import NegotiationAdvisorAgent, create_negotiation_advisor_agent
from src.agents.orchestrator_agent import OrchestratorAgent, create_orchestrator_agent

# Sistema de ferramentas
from src.agents.tools import (
    AgentTool,
    FunctionTool,
    ToolRegistry,
    get_tool_registry,
    tool,
)

# Ferramentas de busca
from src.agents.search_tools import (
    HybridSearchTool,
    VectorSearchTool,
    KeywordSearchTool,
    SimilarChunksTool,
    register_search_tools,
)

# Ferramentas de análise de custos
from src.agents.cost_tools import (
    CostSummaryTool,
    CostByCategoryTool,
    CostByPeriodTool,
    TopProceduresTool,
    TopProvidersTool,
    ComparePeriodsTool,
    register_cost_tools,
)

# Ferramentas de análise de renegociação
from src.agents.negotiation_tools import (
    IdentifyRenegotiationOpportunitiesTool,
    EstimateSavingsTool,
    PrioritizeNegotiationPointsTool,
    GenerateNegotiationReportTool,
    register_negotiation_tools,
)

# Gerenciamento de contexto
from src.agents.context import (
    ContextManager,
    get_context_manager,
)

# Logging de execução
from src.agents.execution_logger import (
    AgentExecutionLogger,
    ExecutionTracker,
    get_execution_tracker,
)

# Re-exportar tipos do models
from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentExecutionStep,
    AgentMessage,
    AgentStatus,
    AgentType,
    OrchestratorDecision,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolResultStatus,
)

__all__ = [
    # Classes base
    "BaseAgent",
    "SimpleAgent",
    # Agentes especializados
    "RetrievalAgent",
    "create_retrieval_agent",
    "ContractAnalystAgent",
    "create_contract_analyst_agent",
    "CostInsightsAgent",
    "create_cost_insights_agent",
    "NegotiationAdvisorAgent",
    "create_negotiation_advisor_agent",
    "OrchestratorAgent",
    "create_orchestrator_agent",
    # Ferramentas base
    "AgentTool",
    "FunctionTool",
    "ToolRegistry",
    "get_tool_registry",
    "tool",
    # Ferramentas de busca
    "HybridSearchTool",
    "VectorSearchTool",
    "KeywordSearchTool",
    "SimilarChunksTool",
    "register_search_tools",
    # Ferramentas de custos
    "CostSummaryTool",
    "CostByCategoryTool",
    "CostByPeriodTool",
    "TopProceduresTool",
    "TopProvidersTool",
    "ComparePeriodsTool",
    "register_cost_tools",
    # Ferramentas de negociação
    "IdentifyRenegotiationOpportunitiesTool",
    "EstimateSavingsTool",
    "PrioritizeNegotiationPointsTool",
    "GenerateNegotiationReportTool",
    "register_negotiation_tools",
    # Contexto
    "ContextManager",
    "get_context_manager",
    # Logging
    "AgentExecutionLogger",
    "ExecutionTracker",
    "get_execution_tracker",
    # Tipos
    "AgentContext",
    "AgentExecutionResult",
    "AgentExecutionStep",
    "AgentMessage",
    "AgentStatus",
    "AgentType",
    "OrchestratorDecision",
    "ToolCall",
    "ToolDefinition",
    "ToolParameter",
    "ToolResult",
    "ToolResultStatus",
]
