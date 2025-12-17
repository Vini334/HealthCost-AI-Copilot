"""
Response Formatter - Módulo de formatação de respostas.

Este módulo fornece funções para formatar respostas do copilot
com Markdown rico, incluindo:
- Citações de fontes (página, seção)
- Tabelas para dados numéricos
- Destaque de recomendações
- Formatação de valores monetários e percentuais
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class RecommendationPriority(str, Enum):
    """Prioridade de recomendação."""
    HIGH = "alta"
    MEDIUM = "média"
    LOW = "baixa"


class CalloutType(str, Enum):
    """Tipo de callout/destaque."""
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"
    TIP = "tip"
    IMPORTANT = "important"


@dataclass
class Citation:
    """Representa uma citação de fonte."""
    document_name: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    section_number: Optional[str] = None
    content_snippet: Optional[str] = None
    relevance_score: Optional[float] = None


@dataclass
class Recommendation:
    """Representa uma recomendação."""
    title: str
    description: str
    priority: RecommendationPriority = RecommendationPriority.MEDIUM
    estimated_savings: Optional[float] = None
    action_items: Optional[List[str]] = None
    responsible: Optional[str] = None
    deadline: Optional[str] = None


def format_currency(
    value: Union[int, float],
    currency: str = "R$",
    decimal_places: int = 2,
    include_sign: bool = False,
) -> str:
    """
    Formata um valor monetário.

    Args:
        value: Valor numérico
        currency: Símbolo da moeda (padrão: R$)
        decimal_places: Casas decimais
        include_sign: Se True, inclui sinal (+/-) para valores

    Returns:
        String formatada (ex: "R$ 1.234,56")

    Examples:
        >>> format_currency(1234.56)
        'R$ 1.234,56'
        >>> format_currency(-500.00, include_sign=True)
        'R$ -500,00'
    """
    if value is None:
        return f"{currency} 0,00"

    # Formatar número com separadores brasileiros
    abs_value = abs(value)
    formatted = f"{abs_value:,.{decimal_places}f}"

    # Converter separadores para formato brasileiro
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    # Adicionar sinal se necessário
    if include_sign and value > 0:
        return f"{currency} +{formatted}"
    elif value < 0:
        return f"{currency} -{formatted}"
    else:
        return f"{currency} {formatted}"


def format_percentage(
    value: Union[int, float],
    decimal_places: int = 1,
    include_sign: bool = False,
) -> str:
    """
    Formata um valor percentual.

    Args:
        value: Valor percentual (ex: 15.5 para 15,5%)
        decimal_places: Casas decimais
        include_sign: Se True, inclui sinal (+/-) para variações

    Returns:
        String formatada (ex: "15,5%")

    Examples:
        >>> format_percentage(15.5)
        '15,5%'
        >>> format_percentage(-3.2, include_sign=True)
        '-3,2%'
    """
    if value is None:
        return "0%"

    formatted = f"{abs(value):.{decimal_places}f}".replace(".", ",")

    if include_sign and value > 0:
        return f"+{formatted}%"
    elif value < 0:
        return f"-{formatted}%"
    else:
        return f"{formatted}%"


def format_citation(
    citation: Union[Citation, Dict[str, Any]],
    style: str = "inline",
) -> str:
    """
    Formata uma citação de fonte.

    Args:
        citation: Objeto Citation ou dicionário com dados da citação
        style: Estilo de formatação ("inline", "footnote", "reference")

    Returns:
        String formatada da citação

    Examples:
        >>> format_citation({"document_name": "Contrato.pdf", "page_number": 12, "section_title": "Das Carências"})
        '(Contrato.pdf, Página 12, "Das Carências")'
    """
    if isinstance(citation, dict):
        citation = Citation(**{k: v for k, v in citation.items() if k in Citation.__dataclass_fields__})

    parts = []

    # Nome do documento
    doc_name = citation.document_name or citation.document_id
    if doc_name:
        parts.append(doc_name)

    # Página
    if citation.page_number:
        parts.append(f"Página {citation.page_number}")

    # Seção
    section_info = []
    if citation.section_number:
        section_info.append(f"Seção {citation.section_number}")
    if citation.section_title:
        section_info.append(f'"{citation.section_title}"')

    if section_info:
        parts.append(", ".join(section_info))

    if not parts:
        return ""

    if style == "inline":
        return f"({', '.join(parts)})"
    elif style == "footnote":
        return f"[^{citation.document_id or 'ref'}]: {', '.join(parts)}"
    elif style == "reference":
        return f"- {', '.join(parts)}"
    else:
        return f"({', '.join(parts)})"


def format_citations_list(
    citations: List[Union[Citation, Dict[str, Any]]],
    deduplicate: bool = True,
) -> List[str]:
    """
    Formata uma lista de citações, removendo duplicatas.

    Args:
        citations: Lista de citações
        deduplicate: Se True, remove citações duplicadas

    Returns:
        Lista de strings formatadas
    """
    formatted = []
    seen = set()

    for citation in citations:
        formatted_citation = format_citation(citation, style="reference")
        if not formatted_citation:
            continue

        if deduplicate:
            citation_key = formatted_citation.lower()
            if citation_key in seen:
                continue
            seen.add(citation_key)

        formatted.append(formatted_citation)

    return formatted


def format_sources_section(
    sources: List[Union[Citation, Dict[str, Any]]],
    title: str = "Fontes",
    include_snippets: bool = False,
) -> str:
    """
    Formata uma seção de fontes/referências.

    Args:
        sources: Lista de fontes
        title: Título da seção
        include_snippets: Se True, inclui trechos do conteúdo

    Returns:
        Seção formatada em Markdown

    Examples:
        >>> sources = [{"document_name": "Contrato.pdf", "page_number": 12}]
        >>> format_sources_section(sources)
        '\\n---\\n\\n**Fontes:**\\n- Contrato.pdf, Página 12\\n'
    """
    if not sources:
        return ""

    lines = [
        "",
        "---",
        "",
        f"**{title}:**",
    ]

    for source in sources:
        if isinstance(source, dict):
            citation = Citation(**{k: v for k, v in source.items() if k in Citation.__dataclass_fields__})
        else:
            citation = source

        parts = []

        # Documento e página
        doc_name = citation.document_name or citation.document_id or "Documento"
        parts.append(doc_name)

        if citation.page_number:
            parts.append(f"Página {citation.page_number}")

        # Seção
        if citation.section_number:
            parts.append(f"Seção {citation.section_number}")
        if citation.section_title:
            parts.append(f'"{citation.section_title}"')

        line = f"- {', '.join(parts)}"

        # Snippet opcional
        if include_snippets and citation.content_snippet:
            snippet = citation.content_snippet[:100]
            if len(citation.content_snippet) > 100:
                snippet += "..."
            line += f'\n  > "{snippet}"'

        lines.append(line)

    lines.append("")

    return "\n".join(lines)


def format_table(
    data: List[Dict[str, Any]],
    columns: Optional[List[Dict[str, str]]] = None,
    title: Optional[str] = None,
    max_rows: int = 10,
    include_total: bool = False,
    total_columns: Optional[List[str]] = None,
) -> str:
    """
    Formata dados em uma tabela Markdown.

    Args:
        data: Lista de dicionários com dados
        columns: Lista de colunas com chave e título
            Ex: [{"key": "category", "title": "Categoria"}, ...]
        title: Título da tabela (opcional)
        max_rows: Máximo de linhas a exibir
        include_total: Se True, inclui linha de total
        total_columns: Colunas para calcular total

    Returns:
        Tabela formatada em Markdown

    Examples:
        >>> data = [{"categoria": "Consultas", "valor": 1000}, {"categoria": "Exames", "valor": 500}]
        >>> columns = [{"key": "categoria", "title": "Categoria"}, {"key": "valor", "title": "Valor"}]
        >>> print(format_table(data, columns))
        | Categoria | Valor |
        |-----------|-------|
        | Consultas | 1000 |
        | Exames | 500 |
    """
    if not data:
        return "_Nenhum dado disponível_"

    # Auto-detectar colunas se não especificadas
    if not columns:
        first_row = data[0]
        columns = [{"key": k, "title": k.replace("_", " ").title()} for k in first_row.keys()]

    lines = []

    # Título opcional
    if title:
        lines.append(f"**{title}**")
        lines.append("")

    # Cabeçalho
    header_titles = [col["title"] for col in columns]
    lines.append("| " + " | ".join(header_titles) + " |")

    # Separador
    separators = ["-" * max(3, len(col["title"])) for col in columns]
    lines.append("| " + " | ".join(separators) + " |")

    # Limitar linhas
    display_data = data[:max_rows]

    # Dados
    totals = {col["key"]: 0 for col in columns} if include_total else {}

    for row in display_data:
        cells = []
        for col in columns:
            value = row.get(col["key"], "")

            # Formatar valor baseado no tipo
            if isinstance(value, float):
                # Verificar se é percentual pelo nome da coluna
                if "percent" in col["key"].lower() or "%" in col.get("title", ""):
                    formatted = format_percentage(value)
                else:
                    formatted = format_currency(value)
            elif isinstance(value, int) and col["key"] in (total_columns or []):
                formatted = f"{value:,}".replace(",", ".")
            else:
                formatted = str(value) if value is not None else "-"

            cells.append(formatted)

            # Acumular totais
            if include_total and col["key"] in (total_columns or []):
                try:
                    totals[col["key"]] += float(value) if value else 0
                except (ValueError, TypeError):
                    pass

        lines.append("| " + " | ".join(cells) + " |")

    # Indicar se há mais linhas
    if len(data) > max_rows:
        lines.append(f"| _... e mais {len(data) - max_rows} registros_ | | |")

    # Linha de total
    if include_total and total_columns:
        total_cells = []
        for col in columns:
            if col["key"] == columns[0]["key"]:
                total_cells.append("**Total**")
            elif col["key"] in total_columns:
                total_value = totals.get(col["key"], 0)
                if "percent" in col["key"].lower():
                    total_cells.append(format_percentage(total_value))
                else:
                    total_cells.append(f"**{format_currency(total_value)}**")
            else:
                total_cells.append("")

        lines.append("| " + " | ".join(total_cells) + " |")

    lines.append("")

    return "\n".join(lines)


def format_cost_table(
    data: List[Dict[str, Any]],
    title: str = "Custos por Categoria",
    show_percentage: bool = True,
    show_count: bool = True,
) -> str:
    """
    Formata uma tabela específica para dados de custos.

    Args:
        data: Lista de dicionários com dados de custos
        title: Título da tabela
        show_percentage: Mostrar coluna de percentual
        show_count: Mostrar coluna de quantidade

    Returns:
        Tabela formatada
    """
    if not data:
        return "_Nenhum dado de custos disponível_"

    columns = [{"key": "category", "title": "Categoria"}]

    if show_count:
        columns.append({"key": "count", "title": "Qtd"})

    columns.append({"key": "total_paid", "title": "Valor Pago"})

    if show_percentage:
        columns.append({"key": "percentage", "title": "% do Total"})

    # Normalizar chaves dos dados
    normalized_data = []
    for item in data:
        normalized = {
            "category": item.get("category") or item.get("categoria") or item.get("name") or "-",
            "count": item.get("count") or item.get("occurrences") or item.get("quantidade") or 0,
            "total_paid": item.get("total_paid") or item.get("valor_pago") or item.get("value") or 0,
            "percentage": item.get("percentage") or item.get("percentual") or 0,
        }
        normalized_data.append(normalized)

    return format_table(
        data=normalized_data,
        columns=columns,
        title=title,
        max_rows=10,
        include_total=True,
        total_columns=["total_paid"],
    )


def format_period_table(
    data: List[Dict[str, Any]],
    title: str = "Evolução por Período",
    show_variation: bool = True,
) -> str:
    """
    Formata uma tabela de evolução temporal.

    Args:
        data: Lista de dicionários com dados por período
        title: Título da tabela
        show_variation: Mostrar coluna de variação

    Returns:
        Tabela formatada
    """
    if not data:
        return "_Nenhum dado de período disponível_"

    columns = [
        {"key": "period", "title": "Período"},
        {"key": "total_paid", "title": "Valor Pago"},
    ]

    if show_variation:
        columns.append({"key": "variation", "title": "Variação"})

    # Normalizar dados
    normalized_data = []
    for item in data:
        variation = item.get("variation_percent") or item.get("variacao") or 0
        variation_str = format_percentage(variation, include_sign=True) if variation else "-"

        normalized = {
            "period": item.get("month") or item.get("period") or item.get("periodo") or "-",
            "total_paid": item.get("total_paid") or item.get("valor_pago") or 0,
            "variation": variation_str,
        }
        normalized_data.append(normalized)

    return format_table(
        data=normalized_data,
        columns=columns,
        title=title,
        max_rows=12,
    )


def format_recommendation(
    recommendation: Union[Recommendation, Dict[str, Any]],
    include_details: bool = True,
) -> str:
    """
    Formata uma recomendação com destaque.

    Args:
        recommendation: Objeto Recommendation ou dicionário
        include_details: Se True, inclui detalhes completos

    Returns:
        Recomendação formatada em Markdown

    Examples:
        >>> rec = {"title": "Renegociar reajuste", "description": "...", "priority": "alta"}
        >>> print(format_recommendation(rec))
        > **[ALTA] Renegociar reajuste**
        > ...
    """
    if isinstance(recommendation, dict):
        rec = Recommendation(
            title=recommendation.get("title", "Recomendação"),
            description=recommendation.get("description", ""),
            priority=RecommendationPriority(recommendation.get("priority", "média").lower()),
            estimated_savings=recommendation.get("estimated_savings"),
            action_items=recommendation.get("action_items"),
            responsible=recommendation.get("responsible"),
            deadline=recommendation.get("deadline"),
        )
    else:
        rec = recommendation

    # Emoji baseado na prioridade
    priority_emoji = {
        RecommendationPriority.HIGH: "!",
        RecommendationPriority.MEDIUM: "*",
        RecommendationPriority.LOW: "-",
    }

    lines = []

    # Cabeçalho com prioridade
    emoji = priority_emoji.get(rec.priority, "*")
    priority_label = rec.priority.value.upper()
    lines.append(f"> **[{priority_label}] {rec.title}**")
    lines.append(f"> ")
    lines.append(f"> {rec.description}")

    if include_details:
        # Economia estimada
        if rec.estimated_savings:
            lines.append(f"> ")
            lines.append(f"> **Economia estimada:** {format_currency(rec.estimated_savings)}")

        # Itens de ação
        if rec.action_items:
            lines.append(f"> ")
            lines.append(f"> **Ações:**")
            for action in rec.action_items:
                lines.append(f"> - {action}")

        # Responsável e prazo
        if rec.responsible or rec.deadline:
            lines.append(f"> ")
            details = []
            if rec.responsible:
                details.append(f"**Responsável:** {rec.responsible}")
            if rec.deadline:
                details.append(f"**Prazo:** {rec.deadline}")
            lines.append(f"> {' | '.join(details)}")

    lines.append("")

    return "\n".join(lines)


def format_recommendations_section(
    recommendations: List[Union[Recommendation, Dict[str, Any]]],
    title: str = "Recomendações",
    group_by_priority: bool = True,
) -> str:
    """
    Formata uma seção de recomendações.

    Args:
        recommendations: Lista de recomendações
        title: Título da seção
        group_by_priority: Se True, agrupa por prioridade

    Returns:
        Seção formatada em Markdown
    """
    if not recommendations:
        return ""

    lines = [
        "",
        f"## {title}",
        "",
    ]

    if group_by_priority:
        # Agrupar por prioridade
        by_priority = {
            RecommendationPriority.HIGH: [],
            RecommendationPriority.MEDIUM: [],
            RecommendationPriority.LOW: [],
        }

        for rec in recommendations:
            if isinstance(rec, dict):
                priority = RecommendationPriority(rec.get("priority", "média").lower())
            else:
                priority = rec.priority
            by_priority[priority].append(rec)

        # Exibir por prioridade
        priority_titles = {
            RecommendationPriority.HIGH: "Prioridade Alta",
            RecommendationPriority.MEDIUM: "Prioridade Média",
            RecommendationPriority.LOW: "Prioridade Baixa",
        }

        for priority in [RecommendationPriority.HIGH, RecommendationPriority.MEDIUM, RecommendationPriority.LOW]:
            recs = by_priority[priority]
            if recs:
                lines.append(f"### {priority_titles[priority]}")
                lines.append("")
                for rec in recs:
                    lines.append(format_recommendation(rec))
    else:
        for rec in recommendations:
            lines.append(format_recommendation(rec))

    return "\n".join(lines)


def format_callout(
    content: str,
    callout_type: CalloutType = CalloutType.INFO,
    title: Optional[str] = None,
) -> str:
    """
    Formata um callout/destaque.

    Args:
        content: Conteúdo do callout
        callout_type: Tipo de callout
        title: Título opcional

    Returns:
        Callout formatado em Markdown

    Examples:
        >>> print(format_callout("Atenção ao prazo!", CalloutType.WARNING))
        > **Atenção!**
        > Atenção ao prazo!
    """
    # Títulos padrão por tipo
    default_titles = {
        CalloutType.INFO: "Informação",
        CalloutType.WARNING: "Atenção",
        CalloutType.SUCCESS: "Sucesso",
        CalloutType.TIP: "Dica",
        CalloutType.IMPORTANT: "Importante",
    }

    callout_title = title or default_titles.get(callout_type, "Nota")

    lines = [
        f"> **{callout_title}**",
        f"> {content}",
        "",
    ]

    return "\n".join(lines)


def format_summary_box(
    items: Dict[str, Any],
    title: str = "Resumo",
) -> str:
    """
    Formata uma caixa de resumo com métricas.

    Args:
        items: Dicionário com métricas (chave: valor)
        title: Título do resumo

    Returns:
        Box formatado em Markdown

    Examples:
        >>> items = {"Total Gasto": 100000, "Economia Potencial": 15000}
        >>> print(format_summary_box(items))
        **Resumo**
        - **Total Gasto:** R$ 100.000,00
        - **Economia Potencial:** R$ 15.000,00
    """
    lines = [
        f"**{title}**",
        "",
    ]

    for key, value in items.items():
        # Formatar valor baseado no tipo
        if isinstance(value, float) or isinstance(value, int):
            # Detectar se é percentual pela chave
            if "percent" in key.lower() or "%" in key:
                formatted_value = format_percentage(value)
            elif "count" in key.lower() or "qtd" in key.lower() or "quantidade" in key.lower():
                formatted_value = f"{value:,}".replace(",", ".")
            else:
                formatted_value = format_currency(value)
        else:
            formatted_value = str(value) if value is not None else "-"

        lines.append(f"- **{key}:** {formatted_value}")

    lines.append("")

    return "\n".join(lines)


class ResponseFormatter:
    """
    Classe para formatação completa de respostas do copilot.

    Fornece métodos para construir respostas ricas em Markdown
    com citações, tabelas, recomendações e mais.

    Example:
        formatter = ResponseFormatter()

        # Adicionar conteúdo
        formatter.add_heading("Análise de Custos")
        formatter.add_summary({"Total": 100000, "Período": "2024"})
        formatter.add_table(cost_data, title="Por Categoria")
        formatter.add_recommendations(recommendations)
        formatter.add_sources(sources)

        # Gerar resposta final
        response = formatter.build()
    """

    def __init__(self):
        """Inicializa o formatador."""
        self._sections: List[str] = []
        self._sources: List[Dict[str, Any]] = []

    def add_text(self, text: str) -> "ResponseFormatter":
        """Adiciona texto livre."""
        self._sections.append(text)
        return self

    def add_heading(self, text: str, level: int = 2) -> "ResponseFormatter":
        """Adiciona um título."""
        prefix = "#" * level
        self._sections.append(f"\n{prefix} {text}\n")
        return self

    def add_paragraph(self, text: str) -> "ResponseFormatter":
        """Adiciona um parágrafo."""
        self._sections.append(f"\n{text}\n")
        return self

    def add_summary(
        self,
        items: Dict[str, Any],
        title: str = "Resumo",
    ) -> "ResponseFormatter":
        """Adiciona uma caixa de resumo."""
        self._sections.append(format_summary_box(items, title))
        return self

    def add_table(
        self,
        data: List[Dict[str, Any]],
        columns: Optional[List[Dict[str, str]]] = None,
        title: Optional[str] = None,
        **kwargs,
    ) -> "ResponseFormatter":
        """Adiciona uma tabela."""
        self._sections.append(format_table(data, columns, title, **kwargs))
        return self

    def add_cost_table(
        self,
        data: List[Dict[str, Any]],
        title: str = "Custos por Categoria",
        **kwargs,
    ) -> "ResponseFormatter":
        """Adiciona uma tabela de custos."""
        self._sections.append(format_cost_table(data, title, **kwargs))
        return self

    def add_period_table(
        self,
        data: List[Dict[str, Any]],
        title: str = "Evolução por Período",
        **kwargs,
    ) -> "ResponseFormatter":
        """Adiciona uma tabela de evolução temporal."""
        self._sections.append(format_period_table(data, title, **kwargs))
        return self

    def add_recommendation(
        self,
        recommendation: Union[Recommendation, Dict[str, Any]],
    ) -> "ResponseFormatter":
        """Adiciona uma recomendação."""
        self._sections.append(format_recommendation(recommendation))
        return self

    def add_recommendations(
        self,
        recommendations: List[Union[Recommendation, Dict[str, Any]]],
        title: str = "Recomendações",
        group_by_priority: bool = True,
    ) -> "ResponseFormatter":
        """Adiciona seção de recomendações."""
        self._sections.append(format_recommendations_section(
            recommendations, title, group_by_priority
        ))
        return self

    def add_callout(
        self,
        content: str,
        callout_type: CalloutType = CalloutType.INFO,
        title: Optional[str] = None,
    ) -> "ResponseFormatter":
        """Adiciona um callout/destaque."""
        self._sections.append(format_callout(content, callout_type, title))
        return self

    def add_source(
        self,
        source: Union[Citation, Dict[str, Any]],
    ) -> "ResponseFormatter":
        """Adiciona uma fonte para a seção de referências."""
        if isinstance(source, Citation):
            self._sources.append({
                "document_name": source.document_name,
                "document_id": source.document_id,
                "page_number": source.page_number,
                "section_title": source.section_title,
                "section_number": source.section_number,
                "content_snippet": source.content_snippet,
            })
        else:
            self._sources.append(source)
        return self

    def add_sources(
        self,
        sources: List[Union[Citation, Dict[str, Any]]],
    ) -> "ResponseFormatter":
        """Adiciona múltiplas fontes."""
        for source in sources:
            self.add_source(source)
        return self

    def add_inline_citation(
        self,
        text: str,
        source: Union[Citation, Dict[str, Any]],
    ) -> "ResponseFormatter":
        """Adiciona texto com citação inline."""
        citation = format_citation(source, style="inline")
        self._sections.append(f"{text} {citation}")
        self.add_source(source)
        return self

    def add_list(
        self,
        items: List[str],
        ordered: bool = False,
    ) -> "ResponseFormatter":
        """Adiciona uma lista."""
        lines = []
        for i, item in enumerate(items, 1):
            if ordered:
                lines.append(f"{i}. {item}")
            else:
                lines.append(f"- {item}")
        self._sections.append("\n".join(lines) + "\n")
        return self

    def add_divider(self) -> "ResponseFormatter":
        """Adiciona um divisor horizontal."""
        self._sections.append("\n---\n")
        return self

    def build(
        self,
        include_sources: bool = True,
        sources_title: str = "Fontes",
    ) -> str:
        """
        Constrói a resposta final.

        Args:
            include_sources: Se True, inclui seção de fontes no final
            sources_title: Título da seção de fontes

        Returns:
            Resposta completa formatada em Markdown
        """
        response_parts = self._sections.copy()

        # Adicionar seção de fontes se houver
        if include_sources and self._sources:
            sources_section = format_sources_section(
                self._sources,
                title=sources_title,
            )
            response_parts.append(sources_section)

        # Juntar partes
        response = "\n".join(response_parts)

        # Limpar múltiplas linhas em branco
        while "\n\n\n" in response:
            response = response.replace("\n\n\n", "\n\n")

        return response.strip()

    def clear(self) -> "ResponseFormatter":
        """Limpa o formatador para reutilização."""
        self._sections = []
        self._sources = []
        return self


def format_agent_response(
    content: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    include_sources_section: bool = True,
) -> str:
    """
    Formata uma resposta de agente adicionando seção de fontes.

    Função utilitária para adicionar formatação padrão
    às respostas dos agentes.

    Args:
        content: Conteúdo da resposta
        sources: Lista de fontes
        include_sources_section: Se True, adiciona seção de fontes

    Returns:
        Resposta formatada
    """
    if not sources or not include_sources_section:
        return content

    sources_section = format_sources_section(sources)
    return f"{content}{sources_section}"


def format_consolidated_response(
    sections: List[Dict[str, Any]],
    title: Optional[str] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Formata uma resposta consolidada de múltiplos agentes.

    Args:
        sections: Lista de seções com título e conteúdo
        title: Título geral (opcional)
        sources: Fontes combinadas (opcional)

    Returns:
        Resposta consolidada formatada
    """
    formatter = ResponseFormatter()

    if title:
        formatter.add_heading(title, level=1)

    for section in sections:
        section_title = section.get("title")
        section_content = section.get("content", "")

        if section_title:
            formatter.add_heading(section_title, level=2)

        formatter.add_text(section_content)

    if sources:
        formatter.add_sources(sources)

    return formatter.build()
