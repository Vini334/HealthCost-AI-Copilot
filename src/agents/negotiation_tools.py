"""
Ferramentas de análise de renegociação para agentes.

Este módulo implementa ferramentas para identificar oportunidades
de renegociação de contratos de planos de saúde, baseando-se em:
- Análise de custos e tendências
- Comparação com benchmarks de mercado
- Identificação de cláusulas impactantes
- Cálculo de potencial de economia
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.agents.tools import AgentTool
from src.config.logging import get_logger
from src.models.agents import ToolParameter
from src.storage.cosmos_db import CosmosDBClient, get_cosmos_client

logger = get_logger(__name__)


# Benchmarks de mercado (valores de referência)
MARKET_BENCHMARKS = {
    "reajuste_anual": {
        "inflacao_medica": 15.0,  # VCMH típico
        "min_mercado": 8.0,
        "max_mercado": 25.0,
        "otimo": 10.0,
    },
    "coparticipacao": {
        "consulta": {"min": 20.0, "max": 50.0, "comum": 30.0},
        "exame_simples": {"min": 20.0, "max": 40.0, "comum": 25.0},
        "exame_complexo": {"min": 30.0, "max": 50.0, "comum": 40.0},
        "internacao": {"min": 0.0, "max": 30.0, "comum": 0.0},
    },
    "glosa_aceitavel": 5.0,  # % de glosa aceitável
    "sinistralidade_alvo": 75.0,  # % sinistralidade ideal
}


class IdentifyRenegotiationOpportunitiesTool(AgentTool):
    """
    Ferramenta para identificar oportunidades de renegociação.

    Analisa dados de custos e contrato para identificar
    pontos com potencial de renegociação.
    """

    name = "identify_renegotiation_opportunities"
    description = (
        "Identifica oportunidades de renegociação analisando dados de custos, "
        "tendências e cláusulas contratuais. Retorna lista priorizada de "
        "oportunidades com estimativa de impacto."
    )

    def __init__(self, cosmos_client: Optional[CosmosDBClient] = None):
        """Inicializa a ferramenta."""
        super().__init__()
        self._cosmos_client = cosmos_client

    @property
    def cosmos_client(self) -> CosmosDBClient:
        """Retorna o cliente Cosmos DB (lazy loading)."""
        if self._cosmos_client is None:
            self._cosmos_client = get_cosmos_client()
        return self._cosmos_client

    def get_parameters(self) -> List[ToolParameter]:
        """Define os parâmetros da ferramenta."""
        return [
            ToolParameter(
                name="client_id",
                type="string",
                description="ID do cliente.",
                required=True,
            ),
            ToolParameter(
                name="contract_id",
                type="string",
                description="ID do contrato para análise (opcional).",
                required=False,
            ),
            ToolParameter(
                name="cost_data",
                type="object",
                description="Dados de custos já coletados (opcional).",
                required=False,
            ),
            ToolParameter(
                name="contract_context",
                type="object",
                description="Informações do contrato atual (opcional).",
                required=False,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        cost_data: Optional[Dict[str, Any]] = None,
        contract_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Identifica oportunidades de renegociação.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            cost_data: Dados de custos pré-carregados (opcional)
            contract_context: Contexto do contrato (opcional)

        Returns:
            Dicionário com oportunidades identificadas
        """
        self._logger.info(
            "Identificando oportunidades de renegociação",
            client_id=client_id,
            contract_id=contract_id,
        )

        opportunities = []

        # Se não temos dados de custos, buscar
        if not cost_data:
            cost_data = await self._collect_cost_data(client_id, contract_id)

        # 1. Analisar concentração de prestadores
        provider_opportunities = self._analyze_provider_concentration(cost_data)
        opportunities.extend(provider_opportunities)

        # 2. Analisar tendência de custos
        trend_opportunities = self._analyze_cost_trends(cost_data)
        opportunities.extend(trend_opportunities)

        # 3. Analisar categorias de alto custo
        category_opportunities = self._analyze_high_cost_categories(cost_data)
        opportunities.extend(category_opportunities)

        # 4. Analisar procedimentos recorrentes
        procedure_opportunities = self._analyze_recurrent_procedures(cost_data)
        opportunities.extend(procedure_opportunities)

        # 5. Analisar glosas (diferença cobrado vs pago)
        glosa_opportunities = self._analyze_glosas(cost_data)
        opportunities.extend(glosa_opportunities)

        # Ordenar por impacto estimado
        opportunities.sort(
            key=lambda x: x.get("estimated_savings", 0),
            reverse=True,
        )

        # Calcular totais
        total_potential_savings = sum(
            op.get("estimated_savings", 0) for op in opportunities
        )

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "opportunities": opportunities,
            "total_opportunities": len(opportunities),
            "total_potential_savings": total_potential_savings,
            "analysis_date": datetime.utcnow().isoformat(),
        }

    async def _collect_cost_data(
        self,
        client_id: str,
        contract_id: Optional[str],
    ) -> Dict[str, Any]:
        """Coleta dados de custos necessários para análise."""
        summary = await self.cosmos_client.get_cost_summary(
            client_id=client_id,
            contract_id=contract_id,
        )

        categories = await self.cosmos_client.get_cost_by_category(
            client_id=client_id,
            contract_id=contract_id,
        )

        return {
            "summary": summary,
            "by_category": categories,
            "total_paid": float(summary.get("total_paid", 0) or 0),
            "total_charged": float(summary.get("total_charged", 0) or 0),
        }

    def _analyze_provider_concentration(
        self,
        cost_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analisa concentração em prestadores."""
        opportunities = []

        # top_providers pode ser uma lista direta ou um dict com chave "providers"
        top_providers_data = cost_data.get("top_providers", [])
        if isinstance(top_providers_data, list):
            top_providers = top_providers_data
        else:
            top_providers = top_providers_data.get("providers", [])

        if not top_providers:
            return opportunities

        # Verificar concentração em poucos prestadores
        top3_percentage = sum(p.get("percentage", 0) for p in top_providers[:3])

        if top3_percentage > 50:
            total_paid = cost_data.get("total_paid", 0)
            top3_value = total_paid * (top3_percentage / 100)

            # Estimar economia de 5-10% através de negociação
            estimated_savings = top3_value * 0.07  # 7% de média

            opportunities.append({
                "type": "provider_concentration",
                "title": "Alta concentração em prestadores",
                "description": (
                    f"Os 3 maiores prestadores concentram {top3_percentage:.1f}% "
                    f"dos custos (R$ {top3_value:,.2f}). "
                    "Negociar descontos por volume ou pacotes pode gerar economia."
                ),
                "priority": "alta" if top3_percentage > 60 else "média",
                "estimated_savings": estimated_savings,
                "estimated_savings_percent": 7.0,
                "action_items": [
                    "Solicitar proposta comercial dos prestadores principais",
                    "Avaliar alternativas de rede para serviços similares",
                    "Negociar descontos por volume ou fidelização",
                ],
                "providers_affected": [
                    p.get("provider_name") for p in top_providers[:3]
                ],
            })

        return opportunities

    def _analyze_cost_trends(
        self,
        cost_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analisa tendências de custos."""
        opportunities = []

        # by_period pode ser uma lista direta ou um dict com chave "periods"
        by_period_data = cost_data.get("by_period", [])
        if isinstance(by_period_data, list):
            periods = by_period_data
        else:
            periods = by_period_data.get("periods", [])

        if len(periods) < 3:
            return opportunities

        # Calcular tendência dos últimos 6 meses
        recent_periods = periods[-6:] if len(periods) >= 6 else periods

        variations = [
            p.get("variation_percent")
            for p in recent_periods
            if p.get("variation_percent") is not None
        ]

        if not variations:
            return opportunities

        avg_variation = sum(variations) / len(variations)

        # Se tendência de alta acima da inflação médica (15%)
        if avg_variation > MARKET_BENCHMARKS["reajuste_anual"]["inflacao_medica"]:
            total_paid = cost_data.get("total_paid", 0)
            excess_growth = avg_variation - MARKET_BENCHMARKS["reajuste_anual"]["otimo"]

            # Economia potencial = reduzir para inflação médica
            estimated_savings = total_paid * (excess_growth / 100) * 0.5

            opportunities.append({
                "type": "cost_trend",
                "title": "Tendência de alta acima do mercado",
                "description": (
                    f"Os custos estão crescendo {avg_variation:.1f}% ao mês em média, "
                    f"acima da inflação médica de {MARKET_BENCHMARKS['reajuste_anual']['inflacao_medica']}%. "
                    "Revisar utilização e negociar cap de reajuste."
                ),
                "priority": "alta",
                "estimated_savings": estimated_savings,
                "current_trend_percent": avg_variation,
                "market_benchmark_percent": MARKET_BENCHMARKS["reajuste_anual"]["inflacao_medica"],
                "action_items": [
                    "Analisar causas do crescimento (sinistros específicos)",
                    "Implementar programa de gestão de saúde",
                    "Negociar teto de reajuste no contrato",
                    "Avaliar mudança de modalidade (coparticipação)",
                ],
            })

        return opportunities

    def _analyze_high_cost_categories(
        self,
        cost_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analisa categorias de alto custo."""
        opportunities = []

        # by_category pode ser uma lista direta ou um dict com chave "categories"
        by_category = cost_data.get("by_category", [])
        if isinstance(by_category, list):
            categories = by_category
        else:
            categories = by_category.get("categories", [])

        if not categories:
            return opportunities

        total_paid = cost_data.get("total_paid", 0)

        for cat in categories[:3]:  # Top 3 categorias
            percentage = cat.get("percentage", 0)
            cat_value = cat.get("total_paid", 0)
            cat_name = cat.get("category", "outros")

            # Se uma categoria representa mais de 35% dos custos
            if percentage > 35:
                # Estimar 5-8% de economia com gestão focada
                estimated_savings = cat_value * 0.06

                opportunities.append({
                    "type": "high_cost_category",
                    "title": f"Alta concentração em {cat_name}",
                    "description": (
                        f"A categoria '{cat_name}' representa {percentage:.1f}% "
                        f"dos custos totais (R$ {cat_value:,.2f}). "
                        "Foco em gestão desta categoria pode reduzir custos."
                    ),
                    "priority": "média",
                    "estimated_savings": estimated_savings,
                    "category": cat_name,
                    "category_percentage": percentage,
                    "category_value": cat_value,
                    "action_items": self._get_category_action_items(cat_name),
                })

        return opportunities

    def _get_category_action_items(self, category: str) -> List[str]:
        """Retorna ações específicas por categoria."""
        actions = {
            "internacao": [
                "Revisar autorizações de internação",
                "Implementar programa de alta precoce",
                "Negociar pacotes de procedimentos",
                "Avaliar segunda opinião médica",
            ],
            "exame": [
                "Revisar protocolos de exames",
                "Direcionar para rede própria/referenciada",
                "Negociar tabela de exames com laboratórios",
                "Combater exames desnecessários",
            ],
            "consulta": [
                "Promover telemedicina",
                "Implementar médico de família/coordenação",
                "Negociar pacotes de consultas",
                "Avaliar coparticipação",
            ],
            "procedimento": [
                "Revisar rol de procedimentos cobertos",
                "Negociar valores de tabela",
                "Implementar auditoria de contas",
                "Avaliar pacotes cirúrgicos",
            ],
        }

        cat_lower = category.lower()
        for key, items in actions.items():
            if key in cat_lower:
                return items

        return [
            "Analisar detalhamento dos custos",
            "Identificar principais drivers",
            "Avaliar alternativas de rede",
            "Negociar condições específicas",
        ]

    def _analyze_recurrent_procedures(
        self,
        cost_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analisa procedimentos recorrentes de alto valor."""
        opportunities = []

        # top_procedures pode ser uma lista direta ou um dict com chave "procedures"
        top_procedures_data = cost_data.get("top_procedures", [])
        if isinstance(top_procedures_data, list):
            procedures = top_procedures_data
        else:
            procedures = top_procedures_data.get("procedures", [])

        if not procedures:
            return opportunities

        total_paid = cost_data.get("total_paid", 0)

        # Verificar procedimentos com alta frequência e valor
        for proc in procedures[:5]:
            occurrences = proc.get("occurrences", 0)
            proc_total = proc.get("total_paid", 0)
            avg_value = proc.get("avg_paid", 0)
            proc_name = proc.get("procedure_description", "")[:50]

            # Se um procedimento tem muitas ocorrências
            if occurrences > 50 and proc_total > total_paid * 0.05:
                # Estimar 10% de economia com pacote
                estimated_savings = proc_total * 0.10

                opportunities.append({
                    "type": "recurrent_procedure",
                    "title": f"Procedimento recorrente: {proc_name}",
                    "description": (
                        f"'{proc_name}' teve {occurrences} ocorrências, "
                        f"totalizando R$ {proc_total:,.2f} (média R$ {avg_value:,.2f}). "
                        "Negociar pacote ou valor fixo pode gerar economia."
                    ),
                    "priority": "média",
                    "estimated_savings": estimated_savings,
                    "procedure_name": proc_name,
                    "occurrences": occurrences,
                    "total_value": proc_total,
                    "avg_value": avg_value,
                    "action_items": [
                        f"Solicitar proposta de pacote para {proc_name}",
                        "Comparar valores com tabela de referência",
                        "Avaliar rede alternativa para este procedimento",
                        "Negociar desconto por volume",
                    ],
                })

        return opportunities

    def _analyze_glosas(
        self,
        cost_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analisa diferença entre valor cobrado e pago (glosas)."""
        opportunities = []

        total_charged = cost_data.get("total_charged", 0)
        total_paid = cost_data.get("total_paid", 0)

        if total_charged <= 0:
            return opportunities

        glosa_percent = ((total_charged - total_paid) / total_charged) * 100
        glosa_value = total_charged - total_paid

        # Se glosa está muito alta (acima de 10%)
        if glosa_percent > 10:
            opportunities.append({
                "type": "high_glosa",
                "title": "Taxa de glosa elevada",
                "description": (
                    f"A taxa de glosa está em {glosa_percent:.1f}% "
                    f"(R$ {glosa_value:,.2f} glosados). "
                    "Isso pode indicar problemas no faturamento ou na rede."
                ),
                "priority": "média",
                "estimated_savings": 0,  # Não é economia, é risco
                "glosa_percent": glosa_percent,
                "glosa_value": glosa_value,
                "benchmark_percent": MARKET_BENCHMARKS["glosa_aceitavel"],
                "action_items": [
                    "Auditar principais motivos de glosa",
                    "Alinhar faturamento com prestadores",
                    "Revisar autorizações prévias",
                    "Treinar RH sobre regras de utilização",
                ],
            })
        # Se glosa está muito baixa (pode estar pagando demais)
        elif glosa_percent < 2:
            potential_savings = total_paid * 0.03  # 3% potencial

            opportunities.append({
                "type": "low_glosa",
                "title": "Auditoria de contas pode ser melhorada",
                "description": (
                    f"A taxa de glosa está em apenas {glosa_percent:.1f}%. "
                    "Uma auditoria mais rigorosa pode identificar cobranças indevidas."
                ),
                "priority": "baixa",
                "estimated_savings": potential_savings,
                "glosa_percent": glosa_percent,
                "action_items": [
                    "Implementar auditoria de contas médicas",
                    "Revisar conformidade com tabelas contratadas",
                    "Validar procedimentos faturados",
                ],
            })

        return opportunities


class EstimateSavingsTool(AgentTool):
    """
    Ferramenta para estimar economia potencial.

    Calcula economia estimada baseada em cenários
    e oportunidades identificadas.
    """

    name = "estimate_savings"
    description = (
        "Calcula estimativa de economia potencial para diferentes cenários "
        "de renegociação, considerando dados históricos e benchmarks de mercado."
    )

    def __init__(self, cosmos_client: Optional[CosmosDBClient] = None):
        """Inicializa a ferramenta."""
        super().__init__()
        self._cosmos_client = cosmos_client

    @property
    def cosmos_client(self) -> CosmosDBClient:
        """Retorna o cliente Cosmos DB (lazy loading)."""
        if self._cosmos_client is None:
            self._cosmos_client = get_cosmos_client()
        return self._cosmos_client

    def get_parameters(self) -> List[ToolParameter]:
        """Define os parâmetros da ferramenta."""
        return [
            ToolParameter(
                name="client_id",
                type="string",
                description="ID do cliente.",
                required=True,
            ),
            ToolParameter(
                name="annual_cost",
                type="number",
                description="Custo anual atual ou estimado.",
                required=True,
            ),
            ToolParameter(
                name="scenarios",
                type="list",
                description=(
                    "Lista de cenários para calcular. "
                    "Opções: 'reajuste', 'coparticipacao', 'rede', 'gestao_saude', 'all'."
                ),
                required=False,
                default=["all"],
            ),
            ToolParameter(
                name="contract_id",
                type="string",
                description="ID do contrato (opcional).",
                required=False,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        annual_cost: float,
        scenarios: Optional[List[str]] = None,
        contract_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Calcula estimativas de economia.

        Args:
            client_id: ID do cliente
            annual_cost: Custo anual atual
            scenarios: Cenários a calcular
            contract_id: ID do contrato (opcional)

        Returns:
            Estimativas de economia por cenário
        """
        self._logger.info(
            "Estimando economia potencial",
            client_id=client_id,
            annual_cost=annual_cost,
            scenarios=scenarios,
        )

        if not scenarios or "all" in scenarios:
            scenarios = ["reajuste", "coparticipacao", "rede", "gestao_saude"]

        estimates = []

        for scenario in scenarios:
            estimate = self._calculate_scenario(scenario, annual_cost)
            if estimate:
                estimates.append(estimate)

        # Calcular totais (não somamos diretamente pois cenários podem ser excludentes)
        conservative_total = sum(e.get("conservative", 0) for e in estimates)
        optimistic_total = sum(e.get("optimistic", 0) for e in estimates)
        realistic_total = sum(e.get("realistic", 0) for e in estimates)

        # Ajustar para evitar sobreposição (máximo 25% de economia total)
        max_savings = annual_cost * 0.25
        if realistic_total > max_savings:
            adjustment_factor = max_savings / realistic_total
            for estimate in estimates:
                estimate["conservative"] *= adjustment_factor
                estimate["optimistic"] *= adjustment_factor
                estimate["realistic"] *= adjustment_factor
            realistic_total = max_savings
            conservative_total *= adjustment_factor
            optimistic_total *= adjustment_factor

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "annual_cost": annual_cost,
            "scenarios": estimates,
            "total_estimates": {
                "conservative": conservative_total,
                "conservative_percent": (conservative_total / annual_cost * 100) if annual_cost > 0 else 0,
                "optimistic": optimistic_total,
                "optimistic_percent": (optimistic_total / annual_cost * 100) if annual_cost > 0 else 0,
                "realistic": realistic_total,
                "realistic_percent": (realistic_total / annual_cost * 100) if annual_cost > 0 else 0,
            },
            "disclaimer": (
                "Estimativas baseadas em benchmarks de mercado e dados históricos. "
                "Resultados reais podem variar conforme negociação e condições específicas."
            ),
        }

    def _calculate_scenario(
        self,
        scenario: str,
        annual_cost: float,
    ) -> Optional[Dict[str, Any]]:
        """Calcula economia para um cenário específico."""
        scenarios_config = {
            "reajuste": {
                "name": "Negociação de reajuste",
                "description": "Negociar cap de reajuste anual abaixo da inflação médica",
                "conservative_percent": 2.0,
                "realistic_percent": 5.0,
                "optimistic_percent": 8.0,
                "implementation": "curto_prazo",
                "complexity": "média",
                "requirements": [
                    "Sinistralidade sob controle",
                    "Histórico de bom relacionamento",
                    "Volume de vidas significativo",
                ],
            },
            "coparticipacao": {
                "name": "Implementação de coparticipação",
                "description": "Introduzir ou ajustar coparticipação para reduzir utilização desnecessária",
                "conservative_percent": 5.0,
                "realistic_percent": 10.0,
                "optimistic_percent": 15.0,
                "implementation": "médio_prazo",
                "complexity": "média",
                "requirements": [
                    "Acordo coletivo permite",
                    "Comunicação adequada aos colaboradores",
                    "Plano sem coparticipação atual",
                ],
            },
            "rede": {
                "name": "Otimização de rede",
                "description": "Direcionar utilização para rede mais eficiente",
                "conservative_percent": 3.0,
                "realistic_percent": 7.0,
                "optimistic_percent": 12.0,
                "implementation": "médio_prazo",
                "complexity": "alta",
                "requirements": [
                    "Rede alternativa de qualidade disponível",
                    "Colaboradores dispostos a mudar hábitos",
                    "Gestão ativa de utilização",
                ],
            },
            "gestao_saude": {
                "name": "Programa de gestão de saúde",
                "description": "Implementar programa de saúde preventiva e gestão de crônicos",
                "conservative_percent": 3.0,
                "realistic_percent": 8.0,
                "optimistic_percent": 15.0,
                "implementation": "longo_prazo",
                "complexity": "alta",
                "requirements": [
                    "Investimento inicial em programa",
                    "Engajamento da liderança",
                    "Dados de saúde populacional",
                ],
            },
        }

        config = scenarios_config.get(scenario)
        if not config:
            return None

        return {
            "scenario": scenario,
            "name": config["name"],
            "description": config["description"],
            "conservative": annual_cost * (config["conservative_percent"] / 100),
            "conservative_percent": config["conservative_percent"],
            "realistic": annual_cost * (config["realistic_percent"] / 100),
            "realistic_percent": config["realistic_percent"],
            "optimistic": annual_cost * (config["optimistic_percent"] / 100),
            "optimistic_percent": config["optimistic_percent"],
            "implementation_timeline": config["implementation"],
            "complexity": config["complexity"],
            "requirements": config["requirements"],
        }


class PrioritizeNegotiationPointsTool(AgentTool):
    """
    Ferramenta para priorizar pontos de negociação.

    Ordena oportunidades por impacto, facilidade e urgência.
    """

    name = "prioritize_negotiation_points"
    description = (
        "Prioriza pontos de renegociação considerando impacto financeiro, "
        "facilidade de implementação e urgência. Retorna ranking ordenado."
    )

    def get_parameters(self) -> List[ToolParameter]:
        """Define os parâmetros da ferramenta."""
        return [
            ToolParameter(
                name="opportunities",
                type="list",
                description="Lista de oportunidades identificadas.",
                required=True,
            ),
            ToolParameter(
                name="criteria_weights",
                type="object",
                description=(
                    "Pesos para critérios (opcional). "
                    "Ex: {'impacto': 0.5, 'facilidade': 0.3, 'urgencia': 0.2}"
                ),
                required=False,
            ),
        ]

    async def execute(
        self,
        opportunities: List[Dict[str, Any]],
        criteria_weights: Optional[Dict[str, float]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Prioriza pontos de negociação.

        Args:
            opportunities: Lista de oportunidades
            criteria_weights: Pesos dos critérios

        Returns:
            Lista priorizada de oportunidades
        """
        self._logger.info(
            "Priorizando pontos de negociação",
            opportunity_count=len(opportunities),
        )

        # Pesos padrão
        weights = criteria_weights or {
            "impacto": 0.5,
            "facilidade": 0.3,
            "urgencia": 0.2,
        }

        # Normalizar pesos
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}

        # Calcular score para cada oportunidade
        scored_opportunities = []

        for opp in opportunities:
            scores = self._calculate_scores(opp)
            weighted_score = (
                scores["impacto"] * weights.get("impacto", 0.5) +
                scores["facilidade"] * weights.get("facilidade", 0.3) +
                scores["urgencia"] * weights.get("urgencia", 0.2)
            )

            scored_opp = {
                **opp,
                "scores": scores,
                "weighted_score": weighted_score,
                "rank": 0,  # Será preenchido após ordenação
            }
            scored_opportunities.append(scored_opp)

        # Ordenar por score
        scored_opportunities.sort(
            key=lambda x: x["weighted_score"],
            reverse=True,
        )

        # Atribuir ranks
        for i, opp in enumerate(scored_opportunities, 1):
            opp["rank"] = i

        # Categorizar por prioridade
        high_priority = [o for o in scored_opportunities if o["weighted_score"] >= 0.7]
        medium_priority = [o for o in scored_opportunities if 0.4 <= o["weighted_score"] < 0.7]
        low_priority = [o for o in scored_opportunities if o["weighted_score"] < 0.4]

        return {
            "prioritized_opportunities": scored_opportunities,
            "summary": {
                "total": len(scored_opportunities),
                "high_priority_count": len(high_priority),
                "medium_priority_count": len(medium_priority),
                "low_priority_count": len(low_priority),
            },
            "by_priority": {
                "alta": high_priority,
                "média": medium_priority,
                "baixa": low_priority,
            },
            "criteria_weights": weights,
        }

    def _calculate_scores(self, opportunity: Dict[str, Any]) -> Dict[str, float]:
        """Calcula scores individuais para uma oportunidade."""
        # Score de impacto (baseado em economia estimada)
        savings = opportunity.get("estimated_savings", 0)
        if savings >= 100000:
            impacto = 1.0
        elif savings >= 50000:
            impacto = 0.8
        elif savings >= 20000:
            impacto = 0.6
        elif savings >= 10000:
            impacto = 0.4
        else:
            impacto = 0.2

        # Score de facilidade (baseado no tipo)
        type_facility = {
            "high_glosa": 0.8,  # Fácil - apenas revisar processos
            "provider_concentration": 0.6,  # Médio - negociação
            "cost_trend": 0.4,  # Difícil - múltiplas ações
            "high_cost_category": 0.5,
            "recurrent_procedure": 0.7,
            "low_glosa": 0.6,
        }
        facilidade = type_facility.get(opportunity.get("type", ""), 0.5)

        # Score de urgência (baseado na prioridade original)
        priority_urgency = {
            "alta": 1.0,
            "média": 0.6,
            "baixa": 0.3,
        }
        urgencia = priority_urgency.get(
            opportunity.get("priority", "média"),
            0.5,
        )

        return {
            "impacto": impacto,
            "facilidade": facilidade,
            "urgencia": urgencia,
        }


class GenerateNegotiationReportTool(AgentTool):
    """
    Ferramenta para gerar relatório de renegociação.

    Compila análises em um relatório estruturado.
    """

    name = "generate_negotiation_report"
    description = (
        "Gera relatório consolidado de renegociação com análises, "
        "oportunidades priorizadas e recomendações acionáveis."
    )

    def get_parameters(self) -> List[ToolParameter]:
        """Define os parâmetros da ferramenta."""
        return [
            ToolParameter(
                name="client_id",
                type="string",
                description="ID do cliente.",
                required=True,
            ),
            ToolParameter(
                name="opportunities",
                type="list",
                description="Oportunidades identificadas e priorizadas.",
                required=True,
            ),
            ToolParameter(
                name="savings_estimates",
                type="object",
                description="Estimativas de economia.",
                required=True,
            ),
            ToolParameter(
                name="contract_context",
                type="object",
                description="Contexto do contrato (opcional).",
                required=False,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        opportunities: List[Dict[str, Any]],
        savings_estimates: Dict[str, Any],
        contract_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Gera relatório de renegociação.

        Args:
            client_id: ID do cliente
            opportunities: Oportunidades priorizadas
            savings_estimates: Estimativas de economia
            contract_context: Contexto do contrato

        Returns:
            Relatório estruturado
        """
        self._logger.info(
            "Gerando relatório de renegociação",
            client_id=client_id,
            opportunity_count=len(opportunities),
        )

        # Sumário executivo
        total_savings = savings_estimates.get("total_estimates", {})
        realistic_savings = total_savings.get("realistic", 0)
        realistic_percent = total_savings.get("realistic_percent", 0)

        executive_summary = (
            f"Identificamos {len(opportunities)} oportunidades de otimização "
            f"com potencial de economia de R$ {realistic_savings:,.2f} "
            f"({realistic_percent:.1f}% do custo anual) em cenário realista."
        )

        # Top 3 recomendações
        top_recommendations = []
        for opp in opportunities[:3]:
            top_recommendations.append({
                "title": opp.get("title", ""),
                "savings": opp.get("estimated_savings", 0),
                "priority": opp.get("priority", "média"),
                "quick_win": opp.get("scores", {}).get("facilidade", 0) >= 0.7,
            })

        # Plano de ação sugerido
        action_plan = self._build_action_plan(opportunities)

        # Próximos passos
        next_steps = [
            {
                "step": 1,
                "action": "Validar dados e premissas com cliente",
                "timeline": "Semana 1",
            },
            {
                "step": 2,
                "action": "Priorizar oportunidades conforme estratégia do cliente",
                "timeline": "Semana 1-2",
            },
            {
                "step": 3,
                "action": "Solicitar propostas comerciais de operadoras/prestadores",
                "timeline": "Semana 2-4",
            },
            {
                "step": 4,
                "action": "Analisar propostas e negociar condições",
                "timeline": "Semana 4-8",
            },
            {
                "step": 5,
                "action": "Implementar mudanças e monitorar resultados",
                "timeline": "Mês 3+",
            },
        ]

        return {
            "client_id": client_id,
            "report_date": datetime.utcnow().isoformat(),
            "executive_summary": executive_summary,
            "savings_potential": {
                "conservative": total_savings.get("conservative", 0),
                "realistic": realistic_savings,
                "optimistic": total_savings.get("optimistic", 0),
            },
            "top_recommendations": top_recommendations,
            "all_opportunities": opportunities,
            "scenarios": savings_estimates.get("scenarios", []),
            "action_plan": action_plan,
            "next_steps": next_steps,
            "contract_context": contract_context,
            "disclaimer": (
                "Este relatório é uma análise preliminar baseada nos dados disponíveis. "
                "Recomenda-se validação com especialistas antes de tomar decisões."
            ),
        }

    def _build_action_plan(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Constrói plano de ação por prazo."""
        short_term = []  # Próximos 30 dias
        medium_term = []  # 1-3 meses
        long_term = []  # 3+ meses

        for opp in opportunities:
            action = {
                "opportunity": opp.get("title", ""),
                "actions": opp.get("action_items", [])[:2],
                "expected_savings": opp.get("estimated_savings", 0),
            }

            facility_score = opp.get("scores", {}).get("facilidade", 0.5)

            if facility_score >= 0.7:
                short_term.append(action)
            elif facility_score >= 0.4:
                medium_term.append(action)
            else:
                long_term.append(action)

        return {
            "curto_prazo": short_term[:3],
            "medio_prazo": medium_term[:3],
            "longo_prazo": long_term[:3],
        }


def register_negotiation_tools(registry: "ToolRegistry") -> None:
    """
    Registra todas as ferramentas de negociação no registry.

    Args:
        registry: ToolRegistry onde registrar as ferramentas
    """
    tools = [
        IdentifyRenegotiationOpportunitiesTool(),
        EstimateSavingsTool(),
        PrioritizeNegotiationPointsTool(),
        GenerateNegotiationReportTool(),
    ]

    for tool in tools:
        registry.register(tool)

    logger.info(
        "Ferramentas de negociação registradas",
        tool_count=len(tools),
        tools=[t.name for t in tools],
    )
