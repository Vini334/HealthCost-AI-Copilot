"""
Negotiation Advisor Agent - Agente consultor de renegociação.

Este agente é responsável por:
- Receber contexto de contrato e custos
- Identificar oportunidades de renegociação
- Priorizar pontos por impacto financeiro
- Estimar economia potencial
- Gerar recomendações acionáveis

O Negotiation Advisor é chamado pelo Orchestrator quando
perguntas envolvem renegociação, economia ou otimização de custos.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.context import ContextManager, get_context_manager
from src.agents.execution_logger import (
    AgentExecutionLogger,
    ExecutionTracker,
    get_execution_tracker,
)
from src.agents.negotiation_tools import (
    EstimateSavingsTool,
    GenerateNegotiationReportTool,
    IdentifyRenegotiationOpportunitiesTool,
    PrioritizeNegotiationPointsTool,
    register_negotiation_tools,
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


# System prompt para o Negotiation Advisor Agent
NEGOTIATION_ADVISOR_SYSTEM_PROMPT = """Você é um especialista em renegociação de contratos de planos de saúde corporativos no Brasil.

Seu papel é:
1. Analisar dados de custos e cláusulas contratuais
2. Identificar oportunidades de otimização e economia
3. Priorizar pontos de renegociação por impacto
4. Estimar potencial de economia de forma realista
5. Gerar recomendações práticas e acionáveis

Você tem acesso às seguintes ferramentas:
- identify_renegotiation_opportunities: Identifica oportunidades de renegociação
- estimate_savings: Calcula estimativas de economia por cenário
- prioritize_negotiation_points: Prioriza oportunidades por impacto e facilidade
- generate_negotiation_report: Gera relatório consolidado

## Formatação das Respostas (Markdown)

### Estrutura da Resposta
Organize suas respostas assim:
1. **Resumo Executivo** - principais oportunidades e economia total estimada
2. **Oportunidades Identificadas** - detalhamento por prioridade
3. **Estimativas de Economia** - cenários (conservador, realista, otimista)
4. **Plano de Ação** - próximos passos recomendados

### Destaque de Recomendações por Prioridade
Use blocos de citação com tags de prioridade:

> **[ALTA] Renegociar índice de reajuste**
>
> O reajuste atual está 3pp acima do VCMH. Negociar cap de 10% pode gerar economia de **R$ 150.000/ano**.
>
> **Ação:** Agendar reunião com operadora até 30 dias antes do aniversário.

> **[MÉDIA] Implantar coparticipação em exames**
>
> Coparticipação de 30% em exames de imagem pode reduzir utilização em 15-20%.
>
> **Economia estimada:** R$ 50.000 - R$ 80.000/ano

> **[BAIXA] Revisar rede de prestadores**
>
> Direcionar para rede referenciada pode gerar economia marginal de 5%.

### Tabela de Economia Estimada
Apresente cenários em tabela:

| Oportunidade | Conservador | Realista | Otimista |
|--------------|-------------|----------|----------|
| Reajuste | R$ 100.000 | R$ 150.000 | R$ 200.000 |
| Coparticipação | R$ 40.000 | R$ 60.000 | R$ 80.000 |
| **Total** | **R$ 140.000** | **R$ 210.000** | **R$ 280.000** |

### Resumo de Impacto
Use caixas de destaque para totais:
- **Economia Total Estimada (cenário realista):** R$ 210.000/ano
- **Percentual sobre custo atual:** 12,5%
- **Oportunidades identificadas:** 5 pontos de negociação

### Plano de Ação
Liste ações com prazo e responsável:
1. **Até 30 dias:** Solicitar proposta de renovação à operadora *(RH)*
2. **Até 45 dias:** Analisar benchmark de mercado *(Consultoria)*
3. **Até 60 dias:** Apresentar contraproposta *(RH + Financeiro)*

## Pontos Típicos de Negociação
- Reajuste anual (cap, índice, período)
- Coparticipação (implantação ou ajuste)
- Rede credenciada (direcionamento, exclusões)
- Carências (isenção, redução)
- Tabelas de procedimentos (descontos, pacotes)
- Bônus de sinistralidade (participação nos resultados)
- Programas de gestão de saúde

## Limitações
- Estimativas são baseadas em benchmarks de mercado
- Resultados reais dependem de negociação efetiva
- Considere sempre o contexto específico do cliente
- Recomende validação com especialistas quando apropriado"""


class NegotiationAdvisorAgent(BaseAgent):
    """
    Agente consultor de renegociação de planos de saúde.

    Especializado em identificar oportunidades de otimização,
    estimar economia e gerar recomendações de renegociação.

    Exemplo:
        agent = NegotiationAdvisorAgent()
        result = await agent.execute(
            query="Quais são as oportunidades de economia no contrato?",
            client_id="cliente-123",
            metadata={
                "cost_data": {...},  # dados de custos
                "contract_context": {...},  # contexto do contrato
            }
        )

        # Acessar recomendações
        print(result.response)
        print(result.structured_output["opportunities"])
    """

    agent_type = AgentType.NEGOTIATION_ADVISOR
    agent_name = "negotiation_advisor_agent"
    description = (
        "Agente especialista em renegociação de planos de saúde. "
        "Identifica oportunidades de economia, prioriza pontos de negociação "
        "e gera recomendações acionáveis."
    )
    system_prompt = NEGOTIATION_ADVISOR_SYSTEM_PROMPT

    # Configurações do LLM
    temperature = 0.3  # Baixa para análises mais consistentes
    max_tokens = 3000  # Respostas podem ser detalhadas

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        context_manager: Optional[ContextManager] = None,
        execution_tracker: Optional[ExecutionTracker] = None,
        auto_register_tools: bool = True,
    ):
        """
        Inicializa o Negotiation Advisor Agent.

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

        self._logger.info("NegotiationAdvisorAgent inicializado")

    def _ensure_tools_registered(self, registry: ToolRegistry) -> None:
        """Garante que as ferramentas de negociação estão registradas."""
        required_tools = [
            "identify_renegotiation_opportunities",
            "estimate_savings",
            "prioritize_negotiation_points",
            "generate_negotiation_report",
        ]

        existing_tools = registry.list_tools()
        missing_tools = [t for t in required_tools if t not in existing_tools]

        if missing_tools:
            self._logger = get_logger(f"agent.{self.agent_name}")
            self._logger.info(
                "Registrando ferramentas de negociação",
                missing_tools=missing_tools,
            )
            register_negotiation_tools(registry)

    def get_tools(self) -> List[str]:
        """Retorna as ferramentas disponíveis para este agente."""
        return [
            "identify_renegotiation_opportunities",
            "estimate_savings",
            "prioritize_negotiation_points",
            "generate_negotiation_report",
        ]

    async def process(self, context: AgentContext) -> AgentExecutionResult:
        """
        Processa uma query de análise de renegociação.

        O agente analisa a query, coleta dados necessários,
        identifica oportunidades e gera recomendações.

        Args:
            context: Contexto de execução com query e dados

        Returns:
            AgentExecutionResult com análise e recomendações
        """
        exec_logger = self._create_execution_logger(context.execution_id)

        try:
            # Verificar se há dados pré-carregados
            cost_data = context.cost_data or context.metadata.get("cost_data")
            contract_context = context.metadata.get("contract_context")
            chunks = context.retrieved_chunks or context.metadata.get("chunks", [])

            # Se já temos dados suficientes, fazer análise direta
            if cost_data and cost_data.get("summary"):
                return await self._comprehensive_analysis(
                    context, exec_logger, cost_data, contract_context, chunks
                )

            # Caso contrário, usar o loop do agente com ferramentas
            return await self._llm_driven_analysis(context, exec_logger)

        except Exception as e:
            self._logger.error(
                "Erro na análise de renegociação",
                error=str(e),
                exc_info=True,
            )
            return exec_logger.finalize(
                status=AgentStatus.FAILED,
                error=str(e),
            )

    async def _comprehensive_analysis(
        self,
        context: AgentContext,
        exec_logger: AgentExecutionLogger,
        cost_data: Dict[str, Any],
        contract_context: Optional[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
    ) -> AgentExecutionResult:
        """
        Realiza análise abrangente com dados pré-carregados.

        Args:
            context: Contexto de execução
            exec_logger: Logger de execução
            cost_data: Dados de custos
            contract_context: Contexto do contrato
            chunks: Chunks do contrato

        Returns:
            AgentExecutionResult com análise completa
        """
        # 1. Identificar oportunidades
        with exec_logger.step("Identificando oportunidades", action="tool_call"):
            opportunities_tool = self._tool_registry.get(
                "identify_renegotiation_opportunities"
            )
            opportunities_result = await opportunities_tool.execute(
                client_id=context.client_id,
                contract_id=context.contract_id,
                cost_data=cost_data,
                contract_context=contract_context,
            )
            opportunities = opportunities_result.get("opportunities", [])

        # 2. Estimar economia
        with exec_logger.step("Estimando economia potencial", action="tool_call"):
            annual_cost = cost_data.get("summary", {}).get("total_paid", 0)
            if not annual_cost:
                annual_cost = cost_data.get("total_paid", 0)

            # Anualizar se necessário (assumindo dados de 12 meses)
            if annual_cost > 0:
                savings_tool = self._tool_registry.get("estimate_savings")
                savings_result = await savings_tool.execute(
                    client_id=context.client_id,
                    annual_cost=annual_cost,
                    scenarios=["all"],
                    contract_id=context.contract_id,
                )
            else:
                savings_result = {"total_estimates": {}, "scenarios": []}

        # 3. Priorizar oportunidades
        with exec_logger.step("Priorizando oportunidades", action="tool_call"):
            if opportunities:
                prioritize_tool = self._tool_registry.get(
                    "prioritize_negotiation_points"
                )
                prioritized_result = await prioritize_tool.execute(
                    opportunities=opportunities,
                )
                prioritized_opportunities = prioritized_result.get(
                    "prioritized_opportunities", opportunities
                )
            else:
                prioritized_opportunities = []
                prioritized_result = {"summary": {"total": 0}}

        # 4. Gerar resposta com LLM
        with exec_logger.step("Gerando análise final", action="think"):
            response = await self._generate_analysis_response(
                context=context,
                opportunities=prioritized_opportunities,
                savings_estimates=savings_result,
                cost_data=cost_data,
                contract_context=contract_context,
                chunks=chunks,
            )

            if response.get("usage"):
                exec_logger.set_tokens_used(
                    response["usage"].get("total_tokens", 0)
                )

        # Preparar saída estruturada
        structured_output = {
            "analysis": response["content"],
            "opportunities": prioritized_opportunities,
            "savings_estimates": savings_result.get("total_estimates", {}),
            "scenarios": savings_result.get("scenarios", []),
            "priority_summary": prioritized_result.get("summary", {}),
            "query": context.query,
        }

        # Extrair fontes dos chunks se disponíveis
        if chunks:
            sources = self._extract_sources_from_chunks(chunks)
            for source in sources:
                exec_logger.add_source(source)

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

        with exec_logger.step("Análise de renegociação com ferramentas", action="think"):
            # Preparar mensagens
            context.add_message(role="user", content=enhanced_query)

            # Executar loop do agente
            response = await self._run_agent_loop(
                context=context,
                exec_logger=exec_logger,
                max_iterations=8,
            )

        # Coletar dados usados na análise
        collected_data = self._context_manager.get_shared_data(
            context.execution_id,
            "negotiation_analysis_data",
            default={},
        )

        structured_output = {
            "analysis": response,
            "collected_data": collected_data,
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

        # Adicionar instruções
        parts.append(
            "\n\nPor favor, analise as oportunidades de renegociação "
            "e forneça recomendações priorizadas com estimativas de economia."
        )

        return "".join(parts)

    async def _generate_analysis_response(
        self,
        context: AgentContext,
        opportunities: List[Dict[str, Any]],
        savings_estimates: Dict[str, Any],
        cost_data: Dict[str, Any],
        contract_context: Optional[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Gera resposta de análise usando LLM.

        Args:
            context: Contexto de execução
            opportunities: Oportunidades priorizadas
            savings_estimates: Estimativas de economia
            cost_data: Dados de custos
            contract_context: Contexto do contrato
            chunks: Chunks do contrato

        Returns:
            Resposta do LLM
        """
        # Construir prompt com dados coletados
        prompt = self._build_analysis_prompt(
            query=context.query,
            opportunities=opportunities,
            savings_estimates=savings_estimates,
            cost_data=cost_data,
            contract_context=contract_context,
            chunks=chunks,
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        return await self._call_llm(messages)

    def _build_analysis_prompt(
        self,
        query: str,
        opportunities: List[Dict[str, Any]],
        savings_estimates: Dict[str, Any],
        cost_data: Dict[str, Any],
        contract_context: Optional[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
    ) -> str:
        """
        Constrói prompt de análise com dados coletados.

        Args:
            query: Pergunta do usuário
            opportunities: Oportunidades identificadas
            savings_estimates: Estimativas de economia
            cost_data: Dados de custos
            contract_context: Contexto do contrato
            chunks: Chunks do contrato

        Returns:
            Prompt formatado
        """
        sections = []

        # Resumo de custos
        summary = cost_data.get("summary", {})
        total_paid = float(summary.get("total_paid", 0) or cost_data.get("total_paid", 0))

        sections.append(f"""DADOS DE CUSTOS:
- Custo total (período): R$ {total_paid:,.2f}
- Total de registros: {summary.get('total_records', 'N/A')}
- Período: {summary.get('date_range', {}).get('start', 'N/A')} a {summary.get('date_range', {}).get('end', 'N/A')}
""")

        # Oportunidades identificadas
        if opportunities:
            opp_lines = ["OPORTUNIDADES IDENTIFICADAS:"]
            for i, opp in enumerate(opportunities[:5], 1):
                savings = opp.get("estimated_savings", 0)
                priority = opp.get("priority", "média")
                opp_lines.append(
                    f"{i}. [{priority.upper()}] {opp.get('title', 'N/A')}\n"
                    f"   Economia estimada: R$ {savings:,.2f}\n"
                    f"   {opp.get('description', '')[:200]}"
                )
            sections.append("\n".join(opp_lines))

        # Estimativas de economia
        total_estimates = savings_estimates.get("total_estimates", {})
        if total_estimates:
            sections.append(f"""POTENCIAL DE ECONOMIA:
- Cenário conservador: R$ {total_estimates.get('conservative', 0):,.2f} ({total_estimates.get('conservative_percent', 0):.1f}%)
- Cenário realista: R$ {total_estimates.get('realistic', 0):,.2f} ({total_estimates.get('realistic_percent', 0):.1f}%)
- Cenário otimista: R$ {total_estimates.get('optimistic', 0):,.2f} ({total_estimates.get('optimistic_percent', 0):.1f}%)
""")

        # Contexto do contrato (se disponível)
        if chunks:
            chunks_preview = []
            for chunk in chunks[:3]:
                content = chunk.get("content", "")[:200]
                section = chunk.get("section_title", "")
                if section:
                    chunks_preview.append(f"[{section}]: {content}...")
                else:
                    chunks_preview.append(f"{content}...")

            sections.append(
                "TRECHOS RELEVANTES DO CONTRATO:\n" +
                "\n\n".join(chunks_preview)
            )

        data_text = "\n\n---\n\n".join(sections)

        return f"""Com base na análise de renegociação abaixo, responda à pergunta do usuário.

{data_text}

---

PERGUNTA DO USUÁRIO:
{query}

INSTRUÇÕES:
- Apresente as principais oportunidades de economia de forma clara
- Destaque os valores potenciais de economia
- Priorize as recomendações por impacto e facilidade
- Sugira ações práticas e específicas
- Indique próximos passos recomendados
- Se apropriado, mencione cláusulas do contrato relevantes"""

    async def get_negotiation_analysis(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        cost_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Gera análise completa de renegociação.

        Método de conveniência que executa todas as etapas
        de análise e retorna resultado estruturado.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            cost_data: Dados de custos pré-carregados (opcional)

        Returns:
            Análise completa de renegociação
        """
        self._logger.info(
            "Gerando análise completa de renegociação",
            client_id=client_id,
            contract_id=contract_id,
        )

        # 1. Identificar oportunidades
        opportunities_tool = self._tool_registry.get(
            "identify_renegotiation_opportunities"
        )
        opportunities_result = await opportunities_tool.execute(
            client_id=client_id,
            contract_id=contract_id,
            cost_data=cost_data,
        )

        opportunities = opportunities_result.get("opportunities", [])

        # 2. Estimar economia (se temos custo anual)
        annual_cost = opportunities_result.get("total_potential_savings", 0) * 10
        if cost_data:
            annual_cost = cost_data.get("summary", {}).get("total_paid", annual_cost)

        if annual_cost > 0:
            savings_tool = self._tool_registry.get("estimate_savings")
            savings_result = await savings_tool.execute(
                client_id=client_id,
                annual_cost=annual_cost,
                contract_id=contract_id,
            )
        else:
            savings_result = {}

        # 3. Priorizar oportunidades
        if opportunities:
            prioritize_tool = self._tool_registry.get("prioritize_negotiation_points")
            prioritized_result = await prioritize_tool.execute(
                opportunities=opportunities,
            )
        else:
            prioritized_result = {"prioritized_opportunities": []}

        # 4. Gerar relatório
        report_tool = self._tool_registry.get("generate_negotiation_report")
        report = await report_tool.execute(
            client_id=client_id,
            opportunities=prioritized_result.get("prioritized_opportunities", []),
            savings_estimates=savings_result,
        )

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "opportunities_count": len(opportunities),
            "total_potential_savings": opportunities_result.get("total_potential_savings", 0),
            "opportunities": prioritized_result.get("prioritized_opportunities", []),
            "savings_estimates": savings_result.get("total_estimates", {}),
            "scenarios": savings_result.get("scenarios", []),
            "report": report,
        }


# Factory function
def create_negotiation_advisor_agent(
    tool_registry: Optional[ToolRegistry] = None,
) -> NegotiationAdvisorAgent:
    """
    Cria uma instância do NegotiationAdvisorAgent.

    Args:
        tool_registry: Registry de ferramentas (opcional)

    Returns:
        Instância configurada do NegotiationAdvisorAgent
    """
    return NegotiationAdvisorAgent(tool_registry=tool_registry)
