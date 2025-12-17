"""
Ferramentas de análise de custos para agentes.

Este módulo implementa as ferramentas de análise de dados de custos
que podem ser utilizadas pelos agentes, especialmente pelo CostInsightsAgent.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.agents.tools import AgentTool
from src.config.logging import get_logger
from src.models.agents import ToolParameter
from src.models.costs import CostCategory
from src.storage.cosmos_db import CosmosDBClient, get_cosmos_client

logger = get_logger(__name__)


class CostSummaryTool(AgentTool):
    """
    Ferramenta para obter resumo geral de custos.

    Retorna totais agregados de custos de um cliente.
    """

    name = "get_cost_summary"
    description = (
        "Obtém resumo geral de custos de um cliente, incluindo totais "
        "de valores cobrados, pagos, quantidade de registros e período. "
        "Use esta ferramenta para ter uma visão geral dos gastos."
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
                description="ID do contrato para filtrar (opcional).",
                required=False,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Obtém resumo de custos.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)

        Returns:
            Dicionário com resumo de custos
        """
        self._logger.info(
            "Obtendo resumo de custos",
            client_id=client_id,
            contract_id=contract_id,
        )

        summary = await self.cosmos_client.get_cost_summary(
            client_id=client_id,
            contract_id=contract_id,
        )

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "total_records": summary.get("total_records", 0),
            "total_charged": float(summary.get("total_charged", 0) or 0),
            "total_paid": float(summary.get("total_paid", 0) or 0),
            "date_range": {
                "start": summary.get("date_start"),
                "end": summary.get("date_end"),
            },
        }


class CostByCategoryTool(AgentTool):
    """
    Ferramenta para análise de custos por categoria.

    Agrega custos por tipo de serviço (consulta, exame, internação, etc.).
    """

    name = "get_cost_by_category"
    description = (
        "Analisa custos agrupados por categoria (consulta, exame, "
        "internação, procedimento, etc.). Use para entender a "
        "distribuição dos gastos por tipo de serviço."
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
                description="ID do contrato para filtrar (opcional).",
                required=False,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Obtém custos por categoria.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)

        Returns:
            Dicionário com custos por categoria
        """
        self._logger.info(
            "Obtendo custos por categoria",
            client_id=client_id,
        )

        categories = await self.cosmos_client.get_cost_by_category(
            client_id=client_id,
            contract_id=contract_id,
        )

        # Calcular totais e percentuais
        total_paid = sum(c.get("total_paid", 0) or 0 for c in categories)

        results = []
        for cat in categories:
            paid = cat.get("total_paid", 0) or 0
            results.append({
                "category": cat.get("category", "outros"),
                "total_records": cat.get("total_records", 0),
                "total_charged": float(cat.get("total_charged", 0) or 0),
                "total_paid": float(paid),
                "percentage": round(paid / total_paid * 100, 2) if total_paid > 0 else 0,
            })

        # Ordenar por valor pago (maior primeiro)
        results.sort(key=lambda x: x["total_paid"], reverse=True)

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "categories": results,
            "total_paid": float(total_paid),
        }


class CostByPeriodTool(AgentTool):
    """
    Ferramenta para análise de evolução temporal de custos.

    Agrupa custos por mês para análise de tendências.
    """

    name = "get_cost_by_period"
    description = (
        "Analisa evolução dos custos ao longo do tempo, agrupando "
        "por mês. Use para identificar tendências, sazonalidade e "
        "variações nos gastos."
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
                description="ID do contrato para filtrar (opcional).",
                required=False,
            ),
            ToolParameter(
                name="start_date",
                type="string",
                description="Data inicial no formato YYYY-MM-DD (opcional).",
                required=False,
            ),
            ToolParameter(
                name="end_date",
                type="string",
                description="Data final no formato YYYY-MM-DD (opcional).",
                required=False,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Obtém custos por período.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            start_date: Data inicial (opcional)
            end_date: Data final (opcional)

        Returns:
            Dicionário com custos por período mensal
        """
        self._logger.info(
            "Obtendo custos por período",
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Query customizada para agrupar por mês
        container = self.cosmos_client._get_costs_container()

        query = """
            SELECT
                SUBSTRING(c.service_date, 0, 7) as month,
                COUNT(1) as total_records,
                SUM(c.charged_amount) as total_charged,
                SUM(c.paid_amount) as total_paid
            FROM c
            WHERE c.client_id = @client_id
        """
        parameters = [{"name": "@client_id", "value": client_id}]

        if contract_id:
            query += " AND c.contract_id = @contract_id"
            parameters.append({"name": "@contract_id", "value": contract_id})

        if start_date:
            query += " AND c.service_date >= @start_date"
            parameters.append({"name": "@start_date", "value": start_date})

        if end_date:
            query += " AND c.service_date <= @end_date"
            parameters.append({"name": "@end_date", "value": end_date})

        query += " GROUP BY SUBSTRING(c.service_date, 0, 7)"

        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
        )

        periods = []
        for item in items:
            periods.append({
                "month": item.get("month"),
                "total_records": item.get("total_records", 0),
                "total_charged": float(item.get("total_charged", 0) or 0),
                "total_paid": float(item.get("total_paid", 0) or 0),
            })

        # Ordenar por mês
        periods.sort(key=lambda x: x["month"])

        # Calcular variações mensais
        for i in range(1, len(periods)):
            prev_paid = periods[i - 1]["total_paid"]
            curr_paid = periods[i]["total_paid"]
            if prev_paid > 0:
                variation = ((curr_paid - prev_paid) / prev_paid) * 100
                periods[i]["variation_percent"] = round(variation, 2)
            else:
                periods[i]["variation_percent"] = None

        if periods:
            periods[0]["variation_percent"] = None

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "periods": periods,
            "period_count": len(periods),
        }


class TopProceduresTool(AgentTool):
    """
    Ferramenta para identificar procedimentos mais custosos.

    Retorna os procedimentos com maiores valores pagos.
    """

    name = "get_top_procedures"
    description = (
        "Identifica os procedimentos com maiores custos. "
        "Use para encontrar os principais drivers de custo "
        "e oportunidades de economia."
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
                description="ID do contrato para filtrar (opcional).",
                required=False,
            ),
            ToolParameter(
                name="top",
                type="integer",
                description="Número de procedimentos a retornar (padrão: 10).",
                required=False,
                default=10,
            ),
            ToolParameter(
                name="category",
                type="string",
                description="Filtrar por categoria específica (opcional).",
                required=False,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        top: int = 10,
        category: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Obtém top procedimentos por custo.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            top: Número de resultados
            category: Categoria para filtrar (opcional)

        Returns:
            Dicionário com top procedimentos
        """
        self._logger.info(
            "Obtendo top procedimentos",
            client_id=client_id,
            top=top,
            category=category,
        )

        container = self.cosmos_client._get_costs_container()

        query = """
            SELECT
                c.procedure_description,
                c.procedure_code,
                COUNT(1) as occurrences,
                SUM(c.charged_amount) as total_charged,
                SUM(c.paid_amount) as total_paid,
                AVG(c.paid_amount) as avg_paid
            FROM c
            WHERE c.client_id = @client_id
        """
        parameters = [{"name": "@client_id", "value": client_id}]

        if contract_id:
            query += " AND c.contract_id = @contract_id"
            parameters.append({"name": "@contract_id", "value": contract_id})

        if category:
            query += " AND c.category = @category"
            parameters.append({"name": "@category", "value": category})

        query += " GROUP BY c.procedure_description, c.procedure_code"

        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
        )

        procedures = []
        for item in items:
            procedures.append({
                "procedure_description": item.get("procedure_description"),
                "procedure_code": item.get("procedure_code"),
                "occurrences": item.get("occurrences", 0),
                "total_charged": float(item.get("total_charged", 0) or 0),
                "total_paid": float(item.get("total_paid", 0) or 0),
                "avg_paid": float(item.get("avg_paid", 0) or 0),
            })

        # Ordenar por valor total pago (maior primeiro)
        procedures.sort(key=lambda x: x["total_paid"], reverse=True)

        # Limitar ao top N
        top_procedures = procedures[:top]

        # Calcular percentual do total
        total_paid = sum(p["total_paid"] for p in procedures)
        for proc in top_procedures:
            proc["percentage"] = round(
                proc["total_paid"] / total_paid * 100, 2
            ) if total_paid > 0 else 0

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "category_filter": category,
            "procedures": top_procedures,
            "total_procedures": len(procedures),
            "total_paid_all": float(total_paid),
        }


class TopProvidersTool(AgentTool):
    """
    Ferramenta para identificar prestadores com maiores custos.

    Retorna os prestadores com maiores valores.
    """

    name = "get_top_providers"
    description = (
        "Identifica os prestadores (hospitais, clínicas, laboratórios) "
        "com maiores custos. Use para análise de rede e negociação."
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
                description="ID do contrato para filtrar (opcional).",
                required=False,
            ),
            ToolParameter(
                name="top",
                type="integer",
                description="Número de prestadores a retornar (padrão: 10).",
                required=False,
                default=10,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        top: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Obtém top prestadores por custo.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            top: Número de resultados

        Returns:
            Dicionário com top prestadores
        """
        self._logger.info(
            "Obtendo top prestadores",
            client_id=client_id,
            top=top,
        )

        container = self.cosmos_client._get_costs_container()

        query = """
            SELECT
                c.provider_name,
                c.provider_code,
                COUNT(1) as total_records,
                SUM(c.charged_amount) as total_charged,
                SUM(c.paid_amount) as total_paid
            FROM c
            WHERE c.client_id = @client_id
            AND c.provider_name != null
        """
        parameters = [{"name": "@client_id", "value": client_id}]

        if contract_id:
            query += " AND c.contract_id = @contract_id"
            parameters.append({"name": "@contract_id", "value": contract_id})

        query += " GROUP BY c.provider_name, c.provider_code"

        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
        )

        providers = []
        for item in items:
            providers.append({
                "provider_name": item.get("provider_name"),
                "provider_code": item.get("provider_code"),
                "total_records": item.get("total_records", 0),
                "total_charged": float(item.get("total_charged", 0) or 0),
                "total_paid": float(item.get("total_paid", 0) or 0),
            })

        # Ordenar por valor total pago
        providers.sort(key=lambda x: x["total_paid"], reverse=True)
        top_providers = providers[:top]

        # Calcular percentuais
        total_paid = sum(p["total_paid"] for p in providers)
        for prov in top_providers:
            prov["percentage"] = round(
                prov["total_paid"] / total_paid * 100, 2
            ) if total_paid > 0 else 0

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "providers": top_providers,
            "total_providers": len(providers),
            "total_paid_all": float(total_paid),
        }


class ComparePeriodsTool(AgentTool):
    """
    Ferramenta para comparar custos entre dois períodos.

    Útil para análise de variação e impacto de mudanças.
    """

    name = "compare_periods"
    description = (
        "Compara custos entre dois períodos diferentes. "
        "Use para analisar variações após mudanças de contrato, "
        "campanhas de saúde ou sazonalidade."
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
                name="period1_start",
                type="string",
                description="Data inicial do primeiro período (YYYY-MM-DD).",
                required=True,
            ),
            ToolParameter(
                name="period1_end",
                type="string",
                description="Data final do primeiro período (YYYY-MM-DD).",
                required=True,
            ),
            ToolParameter(
                name="period2_start",
                type="string",
                description="Data inicial do segundo período (YYYY-MM-DD).",
                required=True,
            ),
            ToolParameter(
                name="period2_end",
                type="string",
                description="Data final do segundo período (YYYY-MM-DD).",
                required=True,
            ),
            ToolParameter(
                name="contract_id",
                type="string",
                description="ID do contrato para filtrar (opcional).",
                required=False,
            ),
        ]

    async def execute(
        self,
        client_id: str,
        period1_start: str,
        period1_end: str,
        period2_start: str,
        period2_end: str,
        contract_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Compara custos entre dois períodos.

        Args:
            client_id: ID do cliente
            period1_start: Início do período 1
            period1_end: Fim do período 1
            period2_start: Início do período 2
            period2_end: Fim do período 2
            contract_id: ID do contrato (opcional)

        Returns:
            Comparação detalhada entre os períodos
        """
        self._logger.info(
            "Comparando períodos",
            client_id=client_id,
            period1=f"{period1_start} a {period1_end}",
            period2=f"{period2_start} a {period2_end}",
        )

        async def get_period_data(start: str, end: str) -> Dict[str, Any]:
            """Obtém dados agregados de um período."""
            container = self.cosmos_client._get_costs_container()

            query = """
                SELECT
                    COUNT(1) as total_records,
                    SUM(c.charged_amount) as total_charged,
                    SUM(c.paid_amount) as total_paid
                FROM c
                WHERE c.client_id = @client_id
                AND c.service_date >= @start_date
                AND c.service_date <= @end_date
            """
            parameters = [
                {"name": "@client_id", "value": client_id},
                {"name": "@start_date", "value": start},
                {"name": "@end_date", "value": end},
            ]

            if contract_id:
                query += " AND c.contract_id = @contract_id"
                parameters.append({"name": "@contract_id", "value": contract_id})

            items = container.query_items(
                query=query,
                parameters=parameters,
                partition_key=client_id,
            )

            result = list(items)
            if result:
                return {
                    "total_records": result[0].get("total_records", 0),
                    "total_charged": float(result[0].get("total_charged", 0) or 0),
                    "total_paid": float(result[0].get("total_paid", 0) or 0),
                }

            return {"total_records": 0, "total_charged": 0, "total_paid": 0}

        # Obter dados dos dois períodos
        period1_data = await get_period_data(period1_start, period1_end)
        period2_data = await get_period_data(period2_start, period2_end)

        # Calcular variações
        def calc_variation(val1: float, val2: float) -> Optional[float]:
            if val1 == 0:
                return None
            return round(((val2 - val1) / val1) * 100, 2)

        return {
            "client_id": client_id,
            "contract_id": contract_id,
            "period1": {
                "start": period1_start,
                "end": period1_end,
                **period1_data,
            },
            "period2": {
                "start": period2_start,
                "end": period2_end,
                **period2_data,
            },
            "variation": {
                "records_percent": calc_variation(
                    period1_data["total_records"],
                    period2_data["total_records"],
                ),
                "charged_percent": calc_variation(
                    period1_data["total_charged"],
                    period2_data["total_charged"],
                ),
                "paid_percent": calc_variation(
                    period1_data["total_paid"],
                    period2_data["total_paid"],
                ),
                "absolute_difference": period2_data["total_paid"] - period1_data["total_paid"],
            },
        }


def register_cost_tools(registry: "ToolRegistry") -> None:
    """
    Registra todas as ferramentas de custos no registry.

    Args:
        registry: ToolRegistry onde registrar as ferramentas
    """
    tools = [
        CostSummaryTool(),
        CostByCategoryTool(),
        CostByPeriodTool(),
        TopProceduresTool(),
        TopProvidersTool(),
        ComparePeriodsTool(),
    ]

    for tool in tools:
        registry.register(tool)

    logger.info(
        "Ferramentas de custos registradas",
        tool_count=len(tools),
        tools=[t.name for t in tools],
    )
