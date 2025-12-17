"""
Orchestrator Agent - Agente orquestrador do sistema multi-agentes.

Este agente é responsável por:
- Analisar a intenção (intent) da pergunta do usuário
- Decidir quais agentes especializados acionar
- Coordenar a execução dos agentes (paralela ou sequencial)
- Consolidar as respostas dos agentes
- Gerar uma resposta final coerente e completa

O Orchestrator é o ponto de entrada principal para todas as queries
do usuário no sistema de chat.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from src.agents.base import BaseAgent
from src.agents.context import ContextManager, get_context_manager
from src.agents.contract_analyst_agent import ContractAnalystAgent
from src.agents.cost_insights_agent import CostInsightsAgent
from src.agents.execution_logger import (
    AgentExecutionLogger,
    ExecutionTracker,
    get_execution_tracker,
)
from src.agents.negotiation_advisor_agent import NegotiationAdvisorAgent
from src.agents.retrieval_agent import RetrievalAgent
from src.agents.tools import ToolRegistry, get_tool_registry
from src.config.logging import get_logger
from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
    OrchestratorDecision,
)

logger = get_logger(__name__)


# Mapeamento de intents para agentes
INTENT_AGENT_MAPPING = {
    "contract_query": [AgentType.RETRIEVAL, AgentType.CONTRACT_ANALYST],
    "cost_analysis": [AgentType.COST_INSIGHTS],
    "negotiation": [AgentType.RETRIEVAL, AgentType.COST_INSIGHTS, AgentType.NEGOTIATION_ADVISOR],
    "cost_and_contract": [AgentType.RETRIEVAL, AgentType.CONTRACT_ANALYST, AgentType.COST_INSIGHTS],
    "general": [AgentType.RETRIEVAL, AgentType.CONTRACT_ANALYST],
}

# Keywords para detecção de intent
INTENT_KEYWORDS = {
    "contract_query": [
        "contrato", "cláusula", "carência", "cobertura", "exclusão",
        "reajuste contratual", "rede credenciada", "coparticipação",
        "portabilidade", "rescisão", "prazo", "vigência", "aditivo",
        "termos", "condições", "obrigações", "direitos", "beneficiário",
        "mensalidade", "plano", "titular", "dependente", "faixa etária",
        "tabela de preços", "valor do plano", "preço", "parcela",
    ],
    "cost_analysis": [
        "custo", "gasto", "sinistralidade", "despesa",
        "total gasto", "média de gastos", "evolução", "tendência",
        "comparar gastos", "período", "mês", "ano", "categoria",
        "procedimento realizado", "prestador", "hospital", "laboratório",
        "exame realizado", "consulta realizada", "internação realizada",
        "sinistro", "utilização", "frequência",
    ],
    "negotiation": [
        "renegociar", "renegociação", "economizar", "economia",
        "reduzir", "redução", "otimizar", "otimização",
        "oportunidade", "melhorar", "desconto", "negociar",
        "proposta", "alternativa", "benchmark", "mercado",
    ],
}


# System prompt para o Orchestrator
ORCHESTRATOR_SYSTEM_PROMPT = """Você é o orquestrador de um sistema de análise de planos de saúde corporativos.

Sua função é:
1. Analisar a pergunta do usuário e identificar a intenção principal
2. Coordenar agentes especializados para obter as informações necessárias
3. Consolidar as respostas em uma resposta única, coerente e completa

Agentes disponíveis:
- **Retrieval Agent**: Busca informações em documentos de contratos
- **Contract Analyst**: Interpreta cláusulas contratuais
- **Cost Insights**: Analisa dados de custos e sinistralidade
- **Negotiation Advisor**: Identifica oportunidades de renegociação

Tipos de perguntas e como tratá-las:

1. **Perguntas sobre contrato** (carência, cobertura, cláusulas):
   - Acionar: Retrieval → Contract Analyst
   - Modo: Sequencial (Retrieval primeiro para buscar chunks)

2. **Perguntas sobre custos** (valores, tendências, top procedures):
   - Acionar: Cost Insights
   - Modo: Direto

3. **Perguntas sobre renegociação/economia**:
   - Acionar: Retrieval + Cost Insights → Negotiation Advisor
   - Modo: Paralelo (Retrieval e Cost) → Sequencial (Negotiation)

4. **Perguntas mistas** (contrato + custos):
   - Acionar: Todos os agentes relevantes
   - Modo: Conforme necessidade

Ao consolidar respostas:
- Integre informações de múltiplos agentes de forma coesa
- Cite fontes quando disponíveis (página, seção do contrato)
- Destaque pontos importantes e recomendações
- Mantenha a resposta focada na pergunta original
- Use formatação clara (tópicos, negrito) quando apropriado"""


# System prompt para análise de intent
INTENT_ANALYSIS_PROMPT = """Analise a pergunta do usuário e classifique a intenção.

Categorias de intenção:
- contract_query: Perguntas sobre cláusulas, coberturas, carências, termos do contrato
- cost_analysis: Perguntas sobre custos, gastos, sinistralidade, valores, tendências
- negotiation: Perguntas sobre economia, renegociação, oportunidades, otimização
- cost_and_contract: Perguntas que envolvem tanto contrato quanto custos
- general: Perguntas gerais ou que não se encaixam nas categorias acima

Responda APENAS com um JSON no formato:
{
    "intent": "categoria_da_intencao",
    "confidence": 0.0 a 1.0,
    "reasoning": "breve explicação",
    "requires_retrieval": true/false,
    "requires_cost_data": true/false,
    "execution_mode": "parallel" ou "sequential"
}"""


# System prompt para consolidação
CONSOLIDATION_PROMPT = """Você recebeu respostas de múltiplos agentes especializados.
Sua tarefa é consolidar essas informações em uma resposta única, coerente e completa.

## Diretrizes de Conteúdo
1. Integre as informações de forma fluida, sem repetições
2. Mantenha o foco na pergunta original do usuário
3. Se houver informações conflitantes, indique claramente
4. Mantenha um tom profissional e objetivo

## Formatação da Resposta (Markdown)

### Estrutura
Organize sua resposta em seções claras quando houver múltiplos tópicos:
- Use títulos (##, ###) para separar seções
- Use **negrito** para termos importantes e valores-chave
- Use listas (- ou 1.) para enumerar itens

### Citações de Fontes
SEMPRE cite fontes disponíveis no formato:
- Inline: "conforme a **Cláusula 5.2** (Página 12)"
- Ou ao final: *(Fonte: Documento X, Página Y)*

### Dados Numéricos
Apresente dados numéricos em tabelas quando houver 3+ itens:
| Item | Valor | Observação |
|------|-------|------------|

### Valores Monetários
- Formate em Reais: **R$ 1.234.567,89**
- Use separadores brasileiros (milhar: . | decimal: ,)
- Para variações: +15,3% ou -8,2%

### Destaques e Alertas
Use blocos de citação (>) para pontos importantes:
> **Atenção:** Informação crítica que requer ação.

> **Recomendação:** Sugestão de próximo passo.

### Recomendações
Se houver recomendações, destaque por prioridade:
> **[ALTA] Título da recomendação**
> Descrição e ação sugerida.

## Notas
- Se algum agente não encontrou informações, omita sem mencionar
- Ao final, inclua uma seção "Fontes" se houver citações de documentos"""


class OrchestratorAgent(BaseAgent):
    """
    Agente orquestrador que coordena o sistema multi-agentes.

    Responsável por analisar perguntas, decidir quais agentes acionar,
    coordenar a execução e consolidar as respostas.

    Exemplo:
        orchestrator = OrchestratorAgent()
        result = await orchestrator.execute(
            query="Qual a carência para cirurgias e quanto gastamos com internações?",
            client_id="cliente-123",
            contract_id="contrato-456",
        )

        print(result.response)  # Resposta consolidada
        print(result.structured_output["agents_invoked"])  # Agentes acionados
    """

    agent_type = AgentType.ORCHESTRATOR
    agent_name = "orchestrator_agent"
    description = (
        "Agente orquestrador que coordena o sistema multi-agentes. "
        "Analisa a intenção da pergunta, aciona agentes especializados "
        "e consolida as respostas."
    )
    system_prompt = ORCHESTRATOR_SYSTEM_PROMPT

    # Configurações do LLM
    use_mini_model = True  # Orquestração e intent detection usam modelo rápido
    temperature = 0.3
    max_tokens = 3500

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        context_manager: Optional[ContextManager] = None,
        execution_tracker: Optional[ExecutionTracker] = None,
        retrieval_agent: Optional[RetrievalAgent] = None,
        contract_analyst: Optional[ContractAnalystAgent] = None,
        cost_insights: Optional[CostInsightsAgent] = None,
        negotiation_advisor: Optional[NegotiationAdvisorAgent] = None,
    ):
        """
        Inicializa o Orchestrator Agent.

        Args:
            tool_registry: Registro de ferramentas
            context_manager: Gerenciador de contexto
            execution_tracker: Rastreador de execuções
            retrieval_agent: Agente de retrieval (opcional, cria se não fornecido)
            contract_analyst: Agente de análise de contratos
            cost_insights: Agente de análise de custos
            negotiation_advisor: Agente de negociação
        """
        super().__init__(
            tool_registry=tool_registry or get_tool_registry(),
            context_manager=context_manager,
            execution_tracker=execution_tracker,
        )

        # Inicializar agentes especializados (lazy loading)
        self._retrieval_agent = retrieval_agent
        self._contract_analyst = contract_analyst
        self._cost_insights = cost_insights
        self._negotiation_advisor = negotiation_advisor

        self._logger.info("OrchestratorAgent inicializado")

    @property
    def retrieval_agent(self) -> RetrievalAgent:
        """Retorna o agente de retrieval (lazy loading)."""
        if self._retrieval_agent is None:
            self._retrieval_agent = RetrievalAgent(
                tool_registry=self._tool_registry,
                context_manager=self._context_manager,
                execution_tracker=self._execution_tracker,
            )
        return self._retrieval_agent

    @property
    def contract_analyst(self) -> ContractAnalystAgent:
        """Retorna o agente de análise de contratos (lazy loading)."""
        if self._contract_analyst is None:
            self._contract_analyst = ContractAnalystAgent(
                tool_registry=self._tool_registry,
                context_manager=self._context_manager,
                execution_tracker=self._execution_tracker,
            )
        return self._contract_analyst

    @property
    def cost_insights(self) -> CostInsightsAgent:
        """Retorna o agente de análise de custos (lazy loading)."""
        if self._cost_insights is None:
            self._cost_insights = CostInsightsAgent(
                tool_registry=self._tool_registry,
                context_manager=self._context_manager,
                execution_tracker=self._execution_tracker,
            )
        return self._cost_insights

    @property
    def negotiation_advisor(self) -> NegotiationAdvisorAgent:
        """Retorna o agente de negociação (lazy loading)."""
        if self._negotiation_advisor is None:
            self._negotiation_advisor = NegotiationAdvisorAgent(
                tool_registry=self._tool_registry,
                context_manager=self._context_manager,
                execution_tracker=self._execution_tracker,
            )
        return self._negotiation_advisor

    def get_tools(self) -> List[str]:
        """
        Retorna ferramentas disponíveis.

        O Orchestrator não usa ferramentas diretamente,
        ele coordena outros agentes.
        """
        return []

    async def process(self, context: AgentContext) -> AgentExecutionResult:
        """
        Processa uma query orquestrando agentes especializados.

        Args:
            context: Contexto de execução com query e metadados

        Returns:
            AgentExecutionResult com resposta consolidada
        """
        exec_logger = self._create_execution_logger(context.execution_id)

        try:
            # 1. Analisar intent da pergunta
            with exec_logger.step("Analisando intenção da pergunta", action="think"):
                decision = await self._analyze_intent(context.query)
                self._logger.info(
                    "Intent identificado",
                    intent=decision.query_intent,
                    agents=decision.agents_to_invoke,
                    mode=decision.execution_mode,
                )

            # 2. Executar agentes conforme decisão
            with exec_logger.step("Executando agentes especializados", action="tool_call"):
                agent_results = await self._execute_agents(
                    context=context,
                    decision=decision,
                    exec_logger=exec_logger,
                )

            # 3. Consolidar respostas
            with exec_logger.step("Consolidando respostas", action="think"):
                final_response = await self._consolidate_responses(
                    query=context.query,
                    decision=decision,
                    agent_results=agent_results,
                )

                if final_response.get("usage"):
                    exec_logger.set_tokens_used(
                        final_response["usage"].get("total_tokens", 0)
                    )

            # Coletar e deduplicar fontes de todos os agentes
            all_sources = self._deduplicate_sources(agent_results)

            for source in all_sources:
                exec_logger.add_source(source)

            # Preparar saída estruturada
            structured_output = {
                "query": context.query,
                "intent": decision.query_intent,
                "agents_invoked": [a.value for a in decision.agents_to_invoke],
                "execution_mode": decision.execution_mode,
                "agent_results": {
                    agent_type.value: {
                        "status": result.status.value,
                        "response_preview": result.response[:200] if result.response else None,
                        "tokens_used": result.tokens_used,
                    }
                    for agent_type, result in agent_results.items()
                },
                "sources": all_sources,
            }

            return exec_logger.finalize(
                status=AgentStatus.COMPLETED,
                response=final_response["content"],
                structured_output=structured_output,
            )

        except Exception as e:
            self._logger.error(
                "Erro na orquestração",
                error=str(e),
                exc_info=True,
            )
            return exec_logger.finalize(
                status=AgentStatus.FAILED,
                error=str(e),
            )

    async def _analyze_intent(self, query: str) -> OrchestratorDecision:
        """
        Analisa a intenção da pergunta do usuário.

        Usa uma combinação de análise por keywords e LLM
        para determinar qual intent melhor se aplica.

        Args:
            query: Pergunta do usuário

        Returns:
            OrchestratorDecision com intent e agentes a acionar
        """
        # Primeiro, tentar detecção por keywords (mais rápido)
        keyword_intent = self._detect_intent_by_keywords(query)

        # Se a confiança for alta, usar resultado direto
        if keyword_intent["confidence"] >= 0.6:
            return self._build_decision_from_intent(
                intent=keyword_intent["intent"],
                confidence=keyword_intent["confidence"],
                reasoning=f"Detectado por keywords: {keyword_intent['keywords_found']}",
            )

        # Caso contrário, usar LLM para análise mais precisa
        try:
            llm_intent = await self._analyze_intent_with_llm(query)
            return self._build_decision_from_intent(
                intent=llm_intent.get("intent", "general"),
                confidence=llm_intent.get("confidence", 0.5),
                reasoning=llm_intent.get("reasoning", "Análise por LLM"),
                execution_mode=llm_intent.get("execution_mode", "sequential"),
            )
        except Exception as e:
            self._logger.warning(
                "Erro na análise de intent por LLM, usando keywords",
                error=str(e),
            )
            return self._build_decision_from_intent(
                intent=keyword_intent["intent"],
                confidence=keyword_intent["confidence"],
                reasoning=f"Fallback para keywords: {keyword_intent['keywords_found']}",
            )

    def _detect_intent_by_keywords(self, query: str) -> Dict[str, Any]:
        """
        Detecta intent por análise de keywords.

        Args:
            query: Pergunta do usuário

        Returns:
            Dicionário com intent, confiança e keywords encontradas
        """
        query_lower = query.lower()
        scores = {}
        keywords_found = {}

        for intent, keywords in INTENT_KEYWORDS.items():
            found = [kw for kw in keywords if kw in query_lower]
            scores[intent] = len(found)
            keywords_found[intent] = found

        # Determinar intent com maior score
        if not any(scores.values()):
            return {
                "intent": "general",
                "confidence": 0.3,
                "keywords_found": [],
            }

        # Verificar se há múltiplos intents com scores altos
        max_score = max(scores.values())
        high_score_intents = [i for i, s in scores.items() if s == max_score]

        if len(high_score_intents) > 1:
            # Múltiplos intents - verificar combinações
            if "contract_query" in high_score_intents and "cost_analysis" in high_score_intents:
                return {
                    "intent": "cost_and_contract",
                    "confidence": 0.7,
                    "keywords_found": keywords_found["contract_query"] + keywords_found["cost_analysis"],
                }
            if "negotiation" in high_score_intents:
                return {
                    "intent": "negotiation",
                    "confidence": 0.7,
                    "keywords_found": keywords_found["negotiation"],
                }

        best_intent = high_score_intents[0]
        confidence = min(0.9, 0.5 + (max_score * 0.1))

        return {
            "intent": best_intent,
            "confidence": confidence,
            "keywords_found": keywords_found[best_intent],
        }

    async def _analyze_intent_with_llm(self, query: str) -> Dict[str, Any]:
        """
        Analisa intent usando LLM para casos ambíguos.

        Args:
            query: Pergunta do usuário

        Returns:
            Dicionário com análise de intent
        """
        messages = [
            {"role": "system", "content": INTENT_ANALYSIS_PROMPT},
            {"role": "user", "content": f"Pergunta: {query}"},
        ]

        response = await self._call_llm(messages)
        content = response.get("content", "")

        # Tentar extrair JSON da resposta
        try:
            # Procurar por JSON na resposta
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Fallback se não conseguir parsear JSON
        return {
            "intent": "general",
            "confidence": 0.5,
            "reasoning": "Não foi possível determinar intent específico",
            "execution_mode": "sequential",
        }

    def _build_decision_from_intent(
        self,
        intent: str,
        confidence: float,
        reasoning: str,
        execution_mode: str = "sequential",
    ) -> OrchestratorDecision:
        """
        Constrói OrchestratorDecision a partir do intent.

        Args:
            intent: Intent identificado
            confidence: Confiança na classificação
            reasoning: Raciocínio da decisão
            execution_mode: Modo de execução

        Returns:
            OrchestratorDecision configurada
        """
        agents = INTENT_AGENT_MAPPING.get(intent, INTENT_AGENT_MAPPING["general"])

        # Determinar modo de execução baseado nos agentes
        if len(agents) == 1:
            mode = "direct"
        elif intent == "negotiation":
            mode = "mixed"  # Parallel para dados, sequential para análise
        else:
            mode = execution_mode

        # Definir ordem de prioridade
        priority_order = None
        if intent == "contract_query":
            priority_order = [AgentType.RETRIEVAL, AgentType.CONTRACT_ANALYST]
        elif intent == "negotiation":
            priority_order = [
                AgentType.RETRIEVAL,
                AgentType.COST_INSIGHTS,
                AgentType.NEGOTIATION_ADVISOR,
            ]

        return OrchestratorDecision(
            query_intent=intent,
            agents_to_invoke=agents,
            execution_mode=mode,
            reasoning=f"{reasoning} (confiança: {confidence:.0%})",
            priority_order=priority_order,
        )

    async def _execute_agents(
        self,
        context: AgentContext,
        decision: OrchestratorDecision,
        exec_logger: AgentExecutionLogger,
    ) -> Dict[AgentType, AgentExecutionResult]:
        """
        Executa os agentes conforme a decisão do orchestrator.

        Args:
            context: Contexto de execução
            decision: Decisão de orquestração
            exec_logger: Logger de execução

        Returns:
            Dicionário com resultados por tipo de agente
        """
        results: Dict[AgentType, AgentExecutionResult] = {}

        if decision.execution_mode == "direct" or len(decision.agents_to_invoke) == 1:
            # Execução direta de um único agente
            agent_type = decision.agents_to_invoke[0]
            result = await self._execute_single_agent(
                agent_type=agent_type,
                context=context,
            )
            results[agent_type] = result

        elif decision.execution_mode == "parallel":
            # Execução paralela de todos os agentes
            results = await self._execute_agents_parallel(
                agent_types=decision.agents_to_invoke,
                context=context,
            )

        elif decision.execution_mode == "sequential":
            # Execução sequencial respeitando dependências
            results = await self._execute_agents_sequential(
                agent_types=decision.agents_to_invoke,
                context=context,
                priority_order=decision.priority_order,
            )

        elif decision.execution_mode == "mixed":
            # Execução mista (paralelo para coleta, sequencial para análise)
            results = await self._execute_agents_mixed(
                context=context,
                decision=decision,
            )

        return results

    async def _execute_single_agent(
        self,
        agent_type: AgentType,
        context: AgentContext,
    ) -> AgentExecutionResult:
        """Executa um único agente."""
        agent = self._get_agent(agent_type)
        return await agent.execute_with_context(context)

    async def _execute_agents_parallel(
        self,
        agent_types: List[AgentType],
        context: AgentContext,
    ) -> Dict[AgentType, AgentExecutionResult]:
        """Executa múltiplos agentes em paralelo."""
        tasks = {}
        for agent_type in agent_types:
            agent = self._get_agent(agent_type)
            # Criar contexto separado para cada agente
            agent_context = self._create_agent_context(context, agent_type)
            tasks[agent_type] = agent.execute_with_context(agent_context)

        # Executar em paralelo
        results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)

        results = {}
        for agent_type, result in zip(tasks.keys(), results_list):
            if isinstance(result, Exception):
                self._logger.error(
                    f"Erro no agente {agent_type.value}",
                    error=str(result),
                )
                results[agent_type] = self._create_error_result(agent_type, str(result))
            else:
                results[agent_type] = result

        return results

    async def _execute_agents_sequential(
        self,
        agent_types: List[AgentType],
        context: AgentContext,
        priority_order: Optional[List[AgentType]] = None,
    ) -> Dict[AgentType, AgentExecutionResult]:
        """Executa agentes sequencialmente, passando contexto entre eles."""
        results = {}
        order = priority_order or agent_types

        for agent_type in order:
            if agent_type not in agent_types:
                continue

            agent = self._get_agent(agent_type)

            # Enriquecer contexto com resultados anteriores
            enriched_context = self._enrich_context(context, results)

            try:
                result = await agent.execute_with_context(enriched_context)
                results[agent_type] = result

                # Propagar chunks recuperados
                if agent_type == AgentType.RETRIEVAL and result.structured_output:
                    chunks = result.structured_output.get("chunks", [])
                    context.retrieved_chunks = chunks

                # Propagar dados de custos
                if agent_type == AgentType.COST_INSIGHTS and result.structured_output:
                    cost_data = result.structured_output.get("cost_data", {})
                    context.cost_data = cost_data

            except Exception as e:
                self._logger.error(
                    f"Erro no agente {agent_type.value}",
                    error=str(e),
                )
                results[agent_type] = self._create_error_result(agent_type, str(e))

        return results

    async def _execute_agents_mixed(
        self,
        context: AgentContext,
        decision: OrchestratorDecision,
    ) -> Dict[AgentType, AgentExecutionResult]:
        """
        Execução mista: coleta de dados em paralelo, análise sequencial.

        Usado principalmente para queries de negociação.
        """
        results = {}

        # Fase 1: Coleta de dados em paralelo (Retrieval + Cost Insights)
        data_agents = [
            a for a in decision.agents_to_invoke
            if a in [AgentType.RETRIEVAL, AgentType.COST_INSIGHTS]
        ]

        if data_agents:
            data_results = await self._execute_agents_parallel(data_agents, context)
            results.update(data_results)

            # Extrair dados para o contexto
            if AgentType.RETRIEVAL in data_results:
                retrieval_result = data_results[AgentType.RETRIEVAL]
                if retrieval_result.structured_output:
                    context.retrieved_chunks = retrieval_result.structured_output.get("chunks", [])

            if AgentType.COST_INSIGHTS in data_results:
                cost_result = data_results[AgentType.COST_INSIGHTS]
                if cost_result.structured_output:
                    context.cost_data = cost_result.structured_output.get("cost_data", {})

        # Fase 2: Agentes de análise sequencial
        analysis_agents = [
            a for a in decision.agents_to_invoke
            if a not in data_agents
        ]

        for agent_type in analysis_agents:
            agent = self._get_agent(agent_type)
            enriched_context = self._enrich_context(context, results)

            try:
                result = await agent.execute_with_context(enriched_context)
                results[agent_type] = result
            except Exception as e:
                self._logger.error(
                    f"Erro no agente {agent_type.value}",
                    error=str(e),
                )
                results[agent_type] = self._create_error_result(agent_type, str(e))

        return results

    def _get_agent(self, agent_type: AgentType) -> BaseAgent:
        """Retorna instância do agente pelo tipo."""
        agent_map = {
            AgentType.RETRIEVAL: self.retrieval_agent,
            AgentType.CONTRACT_ANALYST: self.contract_analyst,
            AgentType.COST_INSIGHTS: self.cost_insights,
            AgentType.NEGOTIATION_ADVISOR: self.negotiation_advisor,
        }

        agent = agent_map.get(agent_type)
        if agent is None:
            raise ValueError(f"Agente não suportado: {agent_type}")

        return agent

    def _create_agent_context(
        self,
        base_context: AgentContext,
        agent_type: AgentType,
    ) -> AgentContext:
        """Cria contexto específico para um agente."""
        return AgentContext(
            client_id=base_context.client_id,
            contract_id=base_context.contract_id,
            conversation_id=base_context.conversation_id,
            query=base_context.query,
            retrieved_chunks=base_context.retrieved_chunks.copy() if base_context.retrieved_chunks else [],
            cost_data=base_context.cost_data.copy() if base_context.cost_data else None,
            metadata=base_context.metadata.copy(),
        )

    def _enrich_context(
        self,
        context: AgentContext,
        previous_results: Dict[AgentType, AgentExecutionResult],
    ) -> AgentContext:
        """Enriquece contexto com resultados de agentes anteriores."""
        enriched = self._create_agent_context(context, AgentType.ORCHESTRATOR)

        for agent_type, result in previous_results.items():
            if result.status != AgentStatus.COMPLETED:
                continue

            output = result.structured_output or {}

            if agent_type == AgentType.RETRIEVAL:
                chunks = output.get("chunks", [])
                if chunks:
                    enriched.retrieved_chunks = chunks
                    enriched.metadata["retrieval_result"] = result.response

            elif agent_type == AgentType.COST_INSIGHTS:
                cost_data = output.get("cost_data", {})
                if cost_data:
                    enriched.cost_data = cost_data
                    enriched.metadata["cost_analysis"] = result.response

            elif agent_type == AgentType.CONTRACT_ANALYST:
                enriched.metadata["contract_analysis"] = result.response

        return enriched

    def _create_error_result(
        self,
        agent_type: AgentType,
        error: str,
    ) -> AgentExecutionResult:
        """Cria resultado de erro para um agente."""
        return AgentExecutionResult(
            execution_id="error",
            agent_type=agent_type,
            agent_name=agent_type.value,
            status=AgentStatus.FAILED,
            error=error,
        )

    def _deduplicate_sources(
        self,
        agent_results: Dict[AgentType, AgentExecutionResult],
    ) -> List[Dict[str, Any]]:
        """
        Deduplica fontes de múltiplos agentes, mantendo a de maior score.

        Quando múltiplos agentes processam os mesmos chunks (ex: Retrieval e
        Contract Analyst), as fontes podem aparecer duplicadas. Este método
        remove duplicatas mantendo a fonte com maior relevance_score.

        Args:
            agent_results: Resultados dos agentes executados

        Returns:
            Lista de fontes únicas ordenadas por relevância (maior primeiro)
        """
        # Dicionário para armazenar fonte única por chave
        unique_sources: Dict[tuple, Dict[str, Any]] = {}

        for result in agent_results.values():
            if not result.sources:
                continue

            for source in result.sources:
                # Criar chave única baseada em documento + localização
                source_key = (
                    source.get("document_id", ""),
                    source.get("page_number"),
                    source.get("section_title", ""),
                    source.get("section_number", ""),
                )

                # Extrair score para comparação
                current_score = (
                    source.get("relevance_score") or
                    source.get("score") or
                    source.get("reranker_score") or
                    0.0
                )

                # Verificar se já existe
                if source_key in unique_sources:
                    existing = unique_sources[source_key]
                    existing_score = (
                        existing.get("relevance_score") or
                        existing.get("score") or
                        existing.get("reranker_score") or
                        0.0
                    )
                    # Manter o de maior score
                    if current_score > existing_score:
                        unique_sources[source_key] = source
                else:
                    unique_sources[source_key] = source

        # Converter para lista e ordenar por relevância (maior primeiro)
        deduplicated = list(unique_sources.values())
        deduplicated.sort(
            key=lambda s: s.get("relevance_score") or s.get("score") or 0.0,
            reverse=True
        )

        # Log de deduplicação
        original_count = sum(len(r.sources or []) for r in agent_results.values())
        self._logger.info(
            "Fontes deduplicadas",
            original_count=original_count,
            unique_count=len(deduplicated),
        )

        return deduplicated

    async def _consolidate_responses(
        self,
        query: str,
        decision: OrchestratorDecision,
        agent_results: Dict[AgentType, AgentExecutionResult],
    ) -> Dict[str, Any]:
        """
        Consolida respostas de múltiplos agentes.

        Args:
            query: Pergunta original
            decision: Decisão de orquestração
            agent_results: Resultados dos agentes

        Returns:
            Resposta consolidada do LLM
        """
        # Se apenas um agente foi acionado, usar resposta diretamente
        successful_results = {
            k: v for k, v in agent_results.items()
            if v.status == AgentStatus.COMPLETED and v.response
        }

        if len(successful_results) == 1:
            result = list(successful_results.values())[0]
            return {
                "content": result.response,
                "usage": {"total_tokens": result.tokens_used or 0},
            }

        if not successful_results:
            return {
                "content": (
                    "Não foi possível encontrar informações relevantes para sua pergunta. "
                    "Por favor, tente reformular ou verifique se os dados estão disponíveis no sistema."
                ),
                "usage": {"total_tokens": 0},
            }

        # Múltiplos agentes - consolidar via LLM
        consolidation_prompt = self._build_consolidation_prompt(
            query=query,
            agent_results=successful_results,
        )

        messages = [
            {"role": "system", "content": CONSOLIDATION_PROMPT},
            {"role": "user", "content": consolidation_prompt},
        ]

        return await self._call_llm(messages)

    def _build_consolidation_prompt(
        self,
        query: str,
        agent_results: Dict[AgentType, AgentExecutionResult],
    ) -> str:
        """Constrói prompt para consolidação de respostas."""
        sections = [f"PERGUNTA DO USUÁRIO:\n{query}\n"]

        for agent_type, result in agent_results.items():
            agent_name = {
                AgentType.RETRIEVAL: "Agente de Busca",
                AgentType.CONTRACT_ANALYST: "Analista de Contrato",
                AgentType.COST_INSIGHTS: "Analista de Custos",
                AgentType.NEGOTIATION_ADVISOR: "Consultor de Negociação",
            }.get(agent_type, agent_type.value)

            sections.append(f"---\n\nRESPOSTA DO {agent_name.upper()}:\n{result.response}\n")

        sections.append(
            "---\n\n"
            "Por favor, consolide as informações acima em uma resposta única, "
            "coerente e completa para o usuário."
        )

        return "\n".join(sections)

    async def process_with_history(
        self,
        query: str,
        client_id: str,
        contract_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        conversation_summary: Optional[str] = None,
        key_entities: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionResult:
        """
        Processa query considerando histórico de conversa.

        Args:
            query: Pergunta atual
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            conversation_history: Histórico de mensagens anteriores
            conversation_summary: Resumo de mensagens antigas (opcional)
            key_entities: Entidades-chave extraídas da conversa (opcional)

        Returns:
            AgentExecutionResult com resposta
        """
        # Construir system prompt enriquecido com contexto
        enriched_system_prompt = self.system_prompt

        # Adicionar resumo da conversa se disponível
        if conversation_summary:
            enriched_system_prompt += f"\n\n## Contexto da Conversa\n{conversation_summary}"

        # Adicionar entidades-chave se disponíveis
        if key_entities:
            entities_text = self._format_key_entities(key_entities)
            if entities_text:
                enriched_system_prompt += f"\n\n## Informações Relevantes\n{entities_text}"

        # Criar contexto com histórico
        context = self._context_manager.create_context(
            client_id=client_id,
            query=query,
            contract_id=contract_id,
            system_prompt=enriched_system_prompt,
        )

        # Adicionar histórico ao contexto
        if conversation_history:
            # Usar todas as mensagens do histórico fornecido
            # (o limite já foi aplicado pelo ConversationService)
            for msg in conversation_history:
                context.add_message(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                )

        # Adicionar query atual (se não for a última mensagem do histórico)
        if not conversation_history or conversation_history[-1].get("content") != query:
            context.add_message(role="user", content=query)

        return await self.execute_with_context(context)

    def _format_key_entities(self, key_entities: Dict[str, Any]) -> str:
        """
        Formata entidades-chave para inclusão no prompt.

        Args:
            key_entities: Dicionário com entidades extraídas

        Returns:
            Texto formatado com entidades
        """
        parts = []

        if key_entities.get("contracts_mentioned"):
            contracts = key_entities["contracts_mentioned"]
            if contracts:
                parts.append(f"- Contratos mencionados: {', '.join(contracts[:5])}")

        if key_entities.get("procedures"):
            procedures = key_entities["procedures"]
            if procedures:
                parts.append(f"- Procedimentos discutidos: {', '.join(procedures[:5])}")

        if key_entities.get("values"):
            values = key_entities["values"]
            if values:
                parts.append(f"- Valores mencionados: {', '.join(str(v) for v in values[:5])}")

        if key_entities.get("key_topics"):
            topics = key_entities["key_topics"]
            if topics:
                parts.append(f"- Tópicos principais: {', '.join(topics[:5])}")

        if key_entities.get("pending_questions"):
            pending = key_entities["pending_questions"]
            if pending:
                parts.append(f"- Perguntas pendentes: {', '.join(pending[:3])}")

        return "\n".join(parts)


# Factory function
def create_orchestrator_agent(
    tool_registry: Optional[ToolRegistry] = None,
) -> OrchestratorAgent:
    """
    Cria uma instância do OrchestratorAgent.

    Args:
        tool_registry: Registry de ferramentas (opcional)

    Returns:
        Instância configurada do OrchestratorAgent
    """
    return OrchestratorAgent(tool_registry=tool_registry)
