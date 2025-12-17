"""
Cost Insights Agent - Agente de análise de custos de saúde.

Este agente é responsável por:
- Acessar e analisar dados de custos de planos de saúde
- Realizar agregações por categoria, período e prestador
- Identificar tendências e padrões nos gastos
- Gerar insights sobre oportunidades de economia

O Cost Insights Agent é chamado pelo Orchestrator quando
perguntas envolvem análise de dados de sinistralidade/custos.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.context import ContextManager, get_context_manager
from src.agents.cost_tools import (
    ComparePeriodsTool,
    CostByCategoryTool,
    CostByPeriodTool,
    CostSummaryTool,
    TopProceduresTool,
    TopProvidersTool,
    register_cost_tools,
)
from src.agents.execution_logger import (
    AgentExecutionLogger,
    ExecutionTracker,
    get_execution_tracker,
)
from src.agents.tools import ToolRegistry, get_tool_registry
from src.config.logging import get_logger
from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
)

logger = get_logger(__name__)


# System prompt para o Cost Insights Agent
COST_INSIGHTS_SYSTEM_PROMPT = """Você é um especialista em análise de custos de planos de saúde corporativos.

Seu papel é:
1. Analisar dados de sinistralidade e custos
2. Identificar padrões e tendências nos gastos
3. Destacar os principais drivers de custo
4. Gerar insights acionáveis para gestão de benefícios
5. Sugerir oportunidades de otimização

Você tem acesso às seguintes ferramentas:
- get_cost_summary: Resumo geral de custos (totais, período)
- get_cost_by_category: Custos por tipo de serviço (consulta, exame, internação)
- get_cost_by_period: Evolução temporal mensal dos custos
- get_top_procedures: Procedimentos com maiores custos
- get_top_providers: Prestadores com maiores custos
- compare_periods: Comparar custos entre dois períodos

## Formatação das Respostas (Markdown)

### Estrutura Geral
Organize suas respostas com:
1. **Resumo executivo** - visão geral dos principais números
2. **Análise detalhada** - tabelas e dados
3. **Insights e tendências** - observações relevantes
4. **Recomendações** - ações sugeridas (quando aplicável)

### Valores Monetários
- SEMPRE formate valores em Reais: **R$ 1.234.567,89**
- Use separador de milhar (.) e decimal (,) no padrão brasileiro
- Para variações, use sinal: +15,3% ou -8,2%

### Tabelas para Dados Numéricos
Use tabelas Markdown para apresentar dados comparativos:

| Categoria | Valor Pago | % do Total | Variação |
|-----------|------------|------------|----------|
| Internações | R$ 500.000,00 | 45,2% | +12,3% |
| Exames | R$ 300.000,00 | 27,1% | -5,4% |

### Evolução Temporal
Para dados de evolução, use tabelas ou listas:

| Mês | Valor | Variação |
|-----|-------|----------|
| Jan/24 | R$ 100.000 | - |
| Fev/24 | R$ 115.000 | +15% |

### Destaques de Tendências
Use blocos de citação para alertas:
> **Tendência de Alta:** Custos com internações cresceram 25% nos últimos 3 meses.

> **Ponto de Atenção:** Os 3 maiores prestadores concentram 60% dos gastos.

### Resumo de Métricas
Para resumos, use formato de lista com destaque:
- **Total no período:** R$ 1.200.000,00
- **Média mensal:** R$ 100.000,00
- **Variação vs. período anterior:** +8,5%

## Terminologia
- Use "valor cobrado" para o valor que o prestador cobrou
- Use "valor pago" para o valor efetivamente pago pela operadora
- "Sinistralidade" refere-se à utilização do plano
- "Glosa" é a diferença entre cobrado e pago"""


class CostInsightsAgent(BaseAgent):
    """
    Agente especializado em análise de custos de saúde.

    Utiliza ferramentas para consultar dados de custos e
    gerar insights sobre gastos, tendências e oportunidades.

    Exemplo:
        agent = CostInsightsAgent()
        result = await agent.execute(
            query="Quais são os principais custos do último trimestre?",
            client_id="cliente-123",
        )

        # Acessar análise
        print(result.response)
        print(result.structured_output["cost_data"])
    """

    agent_type = AgentType.COST_INSIGHTS
    agent_name = "cost_insights_agent"
    description = (
        "Agente especialista em análise de custos de planos de saúde. "
        "Analisa sinistralidade, identifica tendências e gera insights."
    )
    system_prompt = COST_INSIGHTS_SYSTEM_PROMPT

    # Configurações do LLM
    use_mini_model = True  # Cost Insights usa modelo rápido para formatação de dados
    temperature = 0.2  # Baixa para análises mais consistentes
    max_tokens = 2500

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        context_manager: Optional[ContextManager] = None,
        execution_tracker: Optional[ExecutionTracker] = None,
        auto_register_tools: bool = True,
    ):
        """
        Inicializa o Cost Insights Agent.

        Args:
            tool_registry: Registro de ferramentas
            context_manager: Gerenciador de contexto
            execution_tracker: Rastreador de execuções
            auto_register_tools: Se True, registra ferramentas automaticamente
        """
        registry = tool_registry or get_tool_registry()
        if auto_register_tools:
            self._ensure_tools_registered(registry)

        super().__init__(
            tool_registry=registry,
            context_manager=context_manager,
            execution_tracker=execution_tracker,
        )

        self._logger.info("CostInsightsAgent inicializado")

    def _ensure_tools_registered(self, registry: ToolRegistry) -> None:
        """Garante que as ferramentas de custos estão registradas."""
        required_tools = [
            "get_cost_summary",
            "get_cost_by_category",
            "get_cost_by_period",
            "get_top_procedures",
            "get_top_providers",
            "compare_periods",
        ]

        existing_tools = registry.list_tools()
        missing_tools = [t for t in required_tools if t not in existing_tools]

        if missing_tools:
            self._logger = get_logger(f"agent.{self.agent_name}")
            self._logger.info(
                "Registrando ferramentas de custos",
                missing_tools=missing_tools,
            )
            register_cost_tools(registry)

    def get_tools(self) -> List[str]:
        """Retorna as ferramentas disponíveis para este agente."""
        return [
            "get_cost_summary",
            "get_cost_by_category",
            "get_cost_by_period",
            "get_top_procedures",
            "get_top_providers",
            "compare_periods",
        ]

    async def process(self, context: AgentContext) -> AgentExecutionResult:
        """
        Processa uma query de análise de custos.

        O agente analisa a query, decide quais ferramentas usar,
        coleta os dados necessários e gera uma análise.

        Args:
            context: Contexto de execução com query e filtros

        Returns:
            AgentExecutionResult com análise de custos
        """
        exec_logger = self._create_execution_logger(context.execution_id)

        try:
            # Verificar se há dados de custos disponíveis
            cost_data = context.cost_data or context.metadata.get("cost_data")

            # Se já temos dados pré-carregados, usar análise direta
            if cost_data:
                return await self._analyze_preloaded_data(
                    context, exec_logger, cost_data
                )

            # Caso contrário, usar o loop do agente com ferramentas
            return await self._llm_driven_analysis(context, exec_logger)

        except Exception as e:
            self._logger.error(
                "Erro na análise de custos",
                error=str(e),
                exc_info=True,
            )
            return exec_logger.finalize(
                status=AgentStatus.FAILED,
                error=str(e),
            )

    async def _analyze_preloaded_data(
        self,
        context: AgentContext,
        exec_logger: AgentExecutionLogger,
        cost_data: Dict[str, Any],
    ) -> AgentExecutionResult:
        """
        Analisa dados de custos pré-carregados.

        Útil quando os dados já foram coletados pelo Orchestrator.

        Args:
            context: Contexto de execução
            exec_logger: Logger de execução
            cost_data: Dados de custos já carregados

        Returns:
            AgentExecutionResult com análise
        """
        with exec_logger.step("Analisando dados pré-carregados", action="think"):
            # Construir prompt com dados
            analysis_prompt = self._build_analysis_prompt(
                query=context.query,
                cost_data=cost_data,
            )

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": analysis_prompt},
            ]

            response = await self._call_llm(messages)

            if response.get("usage"):
                exec_logger.set_tokens_used(
                    response["usage"].get("total_tokens", 0)
                )

        structured_output = {
            "analysis": response["content"],
            "cost_data": cost_data,
            "query": context.query,
        }

        return exec_logger.finalize(
            status=AgentStatus.COMPLETED,
            response=response["content"],
            structured_output=structured_output,
        )

    async def _llm_driven_analysis(
        self,
        context: AgentContext,
        exec_logger: AgentExecutionLogger,
    ) -> AgentExecutionResult:
        """
        Análise guiada pelo LLM usando ferramentas.

        O LLM decide quais ferramentas chamar para responder a pergunta.

        Args:
            context: Contexto de execução
            exec_logger: Logger de execução

        Returns:
            AgentExecutionResult com análise
        """
        # Adicionar informações de contexto à query
        enhanced_query = self._enhance_query(context)

        with exec_logger.step("Análise de custos com ferramentas", action="think"):
            # Preparar mensagens
            context.add_message(role="user", content=enhanced_query)

            # Executar loop do agente
            response = await self._run_agent_loop(
                context=context,
                exec_logger=exec_logger,
                max_iterations=5,
            )

        # Coletar dados usados na análise
        collected_data = self._context_manager.get_shared_data(
            context.execution_id,
            "cost_analysis_data",
            default={},
        )

        structured_output = {
            "analysis": response,
            "cost_data": collected_data,
            "query": context.query,
            "tools_used": [
                step.tool_call.tool_name
                for step in exec_logger.get_result().steps
                if step.tool_call
            ],
        }

        return exec_logger.finalize(
            status=AgentStatus.COMPLETED,
            response=response,
            structured_output=structured_output,
        )

    def _enhance_query(self, context: AgentContext) -> str:
        """
        Adiciona contexto à query do usuário.

        Args:
            context: Contexto de execução

        Returns:
            Query enriquecida
        """
        parts = [context.query]

        # Adicionar filtros de contexto
        filters = []
        if context.client_id:
            filters.append(f"client_id: {context.client_id}")
        if context.contract_id:
            filters.append(f"contract_id: {context.contract_id}")

        if filters:
            parts.append(f"\n[Contexto: {', '.join(filters)}]")

        return "".join(parts)

    def _build_analysis_prompt(
        self,
        query: str,
        cost_data: Dict[str, Any],
    ) -> str:
        """
        Constrói prompt com dados de custos.

        Args:
            query: Pergunta do usuário
            cost_data: Dados de custos

        Returns:
            Prompt formatado
        """
        # Formatar dados de forma legível
        data_sections = []

        if "summary" in cost_data:
            summary = cost_data["summary"]
            data_sections.append(f"""
RESUMO GERAL:
- Total de registros: {summary.get('total_records', 0):,}
- Valor total cobrado: R$ {summary.get('total_charged', 0):,.2f}
- Valor total pago: R$ {summary.get('total_paid', 0):,.2f}
- Período: {summary.get('date_range', {}).get('start')} a {summary.get('date_range', {}).get('end')}
""")

        if "by_category" in cost_data:
            categories = cost_data["by_category"]
            cat_lines = ["CUSTOS POR CATEGORIA:"]
            for cat in categories.get("categories", [])[:10]:
                cat_lines.append(
                    f"- {cat['category']}: R$ {cat['total_paid']:,.2f} "
                    f"({cat['percentage']:.1f}% do total)"
                )
            data_sections.append("\n".join(cat_lines))

        if "by_period" in cost_data:
            periods = cost_data["by_period"]
            period_lines = ["EVOLUÇÃO MENSAL:"]
            for period in periods.get("periods", [])[-6:]:
                var = period.get('variation_percent')
                var_str = f" ({var:+.1f}%)" if var is not None else ""
                period_lines.append(
                    f"- {period['month']}: R$ {period['total_paid']:,.2f}{var_str}"
                )
            data_sections.append("\n".join(period_lines))

        if "top_procedures" in cost_data:
            procedures = cost_data["top_procedures"]
            proc_lines = ["TOP PROCEDIMENTOS:"]
            for proc in procedures.get("procedures", [])[:5]:
                proc_lines.append(
                    f"- {proc['procedure_description'][:50]}: "
                    f"R$ {proc['total_paid']:,.2f} ({proc['occurrences']} ocorrências)"
                )
            data_sections.append("\n".join(proc_lines))

        data_text = "\n\n".join(data_sections) if data_sections else "Dados não disponíveis"

        return f"""Com base nos dados de custos abaixo, responda à pergunta do usuário.

DADOS DE CUSTOS:

{data_text}

---

PERGUNTA DO USUÁRIO:
{query}

INSTRUÇÕES:
- Analise os dados e responda de forma clara
- Destaque valores e percentuais importantes
- Identifique tendências ou padrões
- Sugira ações quando apropriado"""

    async def get_comprehensive_analysis(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gera uma análise abrangente de custos.

        Coleta dados de todas as ferramentas e retorna
        uma análise consolidada.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)

        Returns:
            Dicionário com análise completa
        """
        self._logger.info(
            "Gerando análise abrangente",
            client_id=client_id,
            contract_id=contract_id,
        )

        # Coletar dados de todas as ferramentas
        summary_tool = self._tool_registry.get("get_cost_summary")
        category_tool = self._tool_registry.get("get_cost_by_category")
        period_tool = self._tool_registry.get("get_cost_by_period")
        procedures_tool = self._tool_registry.get("get_top_procedures")
        providers_tool = self._tool_registry.get("get_top_providers")

        # Executar em paralelo
        import asyncio
        results = await asyncio.gather(
            summary_tool.execute(client_id=client_id, contract_id=contract_id),
            category_tool.execute(client_id=client_id, contract_id=contract_id),
            period_tool.execute(client_id=client_id, contract_id=contract_id),
            procedures_tool.execute(client_id=client_id, contract_id=contract_id, top=10),
            providers_tool.execute(client_id=client_id, contract_id=contract_id, top=10),
            return_exceptions=True,
        )

        analysis = {
            "client_id": client_id,
            "contract_id": contract_id,
            "summary": results[0] if not isinstance(results[0], Exception) else None,
            "by_category": results[1] if not isinstance(results[1], Exception) else None,
            "by_period": results[2] if not isinstance(results[2], Exception) else None,
            "top_procedures": results[3] if not isinstance(results[3], Exception) else None,
            "top_providers": results[4] if not isinstance(results[4], Exception) else None,
        }

        # Gerar insights
        analysis["insights"] = self._generate_insights(analysis)

        return analysis

    def _generate_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Gera insights a partir dos dados analisados.

        Args:
            analysis: Dados da análise

        Returns:
            Lista de insights
        """
        insights = []

        # Insight de categoria dominante
        if analysis.get("by_category"):
            categories = analysis["by_category"].get("categories", [])
            if categories:
                top_cat = categories[0]
                if top_cat["percentage"] > 40:
                    insights.append(
                        f"A categoria '{top_cat['category']}' representa "
                        f"{top_cat['percentage']:.1f}% dos custos totais. "
                        "Considere analisar esta concentração."
                    )

        # Insight de tendência
        if analysis.get("by_period"):
            periods = analysis["by_period"].get("periods", [])
            if len(periods) >= 3:
                recent = periods[-3:]
                variations = [
                    p.get("variation_percent")
                    for p in recent
                    if p.get("variation_percent") is not None
                ]
                if variations:
                    avg_var = sum(variations) / len(variations)
                    if avg_var > 10:
                        insights.append(
                            f"Tendência de alta nos últimos meses: "
                            f"variação média de {avg_var:+.1f}%."
                        )
                    elif avg_var < -10:
                        insights.append(
                            f"Tendência de queda nos últimos meses: "
                            f"variação média de {avg_var:+.1f}%."
                        )

        # Insight de concentração em prestadores
        if analysis.get("top_providers"):
            providers = analysis["top_providers"].get("providers", [])
            if providers:
                top3_pct = sum(p["percentage"] for p in providers[:3])
                if top3_pct > 50:
                    insights.append(
                        f"Os 3 maiores prestadores concentram {top3_pct:.1f}% "
                        "dos custos. Alta concentração pode indicar "
                        "oportunidade de negociação."
                    )

        return insights


# Factory function
def create_cost_insights_agent(
    tool_registry: Optional[ToolRegistry] = None,
) -> CostInsightsAgent:
    """
    Cria uma instância do CostInsightsAgent.

    Args:
        tool_registry: Registry de ferramentas (opcional)

    Returns:
        Instância configurada do CostInsightsAgent
    """
    return CostInsightsAgent(tool_registry=tool_registry)
