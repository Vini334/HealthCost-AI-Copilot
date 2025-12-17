"""
Testes para o módulo de formatação de respostas.

Testa as funções de formatação de:
- Valores monetários
- Percentuais
- Citações de fontes
- Tabelas Markdown
- Recomendações
- ResponseFormatter
"""

import pytest

from src.utils.response_formatter import (
    CalloutType,
    Citation,
    Recommendation,
    RecommendationPriority,
    ResponseFormatter,
    format_callout,
    format_citation,
    format_citations_list,
    format_consolidated_response,
    format_cost_table,
    format_currency,
    format_percentage,
    format_period_table,
    format_recommendation,
    format_recommendations_section,
    format_sources_section,
    format_summary_box,
    format_table,
)


class TestFormatCurrency:
    """Testes para formatação de valores monetários."""

    def test_format_positive_value(self):
        """Testa formatação de valor positivo."""
        result = format_currency(1234.56)
        assert result == "R$ 1.234,56"

    def test_format_large_value(self):
        """Testa formatação de valor grande."""
        result = format_currency(1234567.89)
        assert result == "R$ 1.234.567,89"

    def test_format_zero(self):
        """Testa formatação de zero."""
        result = format_currency(0)
        assert result == "R$ 0,00"

    def test_format_none(self):
        """Testa formatação de None."""
        result = format_currency(None)
        assert result == "R$ 0,00"

    def test_format_negative_value(self):
        """Testa formatação de valor negativo."""
        result = format_currency(-500.00)
        assert result == "R$ -500,00"

    def test_format_with_sign_positive(self):
        """Testa formatação com sinal positivo."""
        result = format_currency(1000.00, include_sign=True)
        assert result == "R$ +1.000,00"

    def test_format_custom_currency(self):
        """Testa formatação com moeda customizada."""
        result = format_currency(100.00, currency="US$")
        assert result == "US$ 100,00"

    def test_format_custom_decimal_places(self):
        """Testa formatação com casas decimais customizadas."""
        result = format_currency(100.5, decimal_places=0)
        assert result == "R$ 100"


class TestFormatPercentage:
    """Testes para formatação de percentuais."""

    def test_format_positive_percentage(self):
        """Testa formatação de percentual positivo."""
        result = format_percentage(15.5)
        assert result == "15,5%"

    def test_format_negative_percentage(self):
        """Testa formatação de percentual negativo."""
        result = format_percentage(-3.2)
        assert result == "-3,2%"

    def test_format_with_sign(self):
        """Testa formatação com sinal."""
        result = format_percentage(10.0, include_sign=True)
        assert result == "+10,0%"

    def test_format_none(self):
        """Testa formatação de None."""
        result = format_percentage(None)
        assert result == "0%"

    def test_format_zero(self):
        """Testa formatação de zero."""
        result = format_percentage(0)
        assert result == "0,0%"

    def test_format_custom_decimal_places(self):
        """Testa formatação com casas decimais customizadas."""
        result = format_percentage(15.567, decimal_places=2)
        assert result == "15,57%"


class TestFormatCitation:
    """Testes para formatação de citações."""

    def test_format_citation_dict(self):
        """Testa formatação de citação a partir de dicionário."""
        citation = {
            "document_name": "Contrato.pdf",
            "page_number": 12,
            "section_title": "Das Carências",
        }
        result = format_citation(citation)
        assert "Contrato.pdf" in result
        assert "Página 12" in result
        assert "Das Carências" in result

    def test_format_citation_object(self):
        """Testa formatação de citação a partir de objeto."""
        citation = Citation(
            document_name="Contrato.pdf",
            page_number=5,
            section_number="3.1",
        )
        result = format_citation(citation)
        assert "Contrato.pdf" in result
        assert "Página 5" in result
        assert "Seção 3.1" in result

    def test_format_citation_inline_style(self):
        """Testa formatação inline."""
        citation = {"document_name": "Doc.pdf", "page_number": 1}
        result = format_citation(citation, style="inline")
        assert result.startswith("(")
        assert result.endswith(")")

    def test_format_citation_reference_style(self):
        """Testa formatação de referência."""
        citation = {"document_name": "Doc.pdf", "page_number": 1}
        result = format_citation(citation, style="reference")
        assert result.startswith("-")

    def test_format_empty_citation(self):
        """Testa citação vazia."""
        result = format_citation({})
        assert result == ""


class TestFormatCitationsList:
    """Testes para formatação de lista de citações."""

    def test_format_multiple_citations(self):
        """Testa formatação de múltiplas citações."""
        citations = [
            {"document_name": "Doc1.pdf", "page_number": 1},
            {"document_name": "Doc2.pdf", "page_number": 2},
        ]
        result = format_citations_list(citations)
        assert len(result) == 2

    def test_format_deduplicate(self):
        """Testa deduplicação de citações."""
        citations = [
            {"document_name": "Doc.pdf", "page_number": 1},
            {"document_name": "Doc.pdf", "page_number": 1},
        ]
        result = format_citations_list(citations, deduplicate=True)
        assert len(result) == 1


class TestFormatSourcesSection:
    """Testes para formatação de seção de fontes."""

    def test_format_sources_section(self):
        """Testa formatação de seção de fontes."""
        sources = [
            {"document_name": "Contrato.pdf", "page_number": 12},
            {"document_name": "Anexo.pdf", "page_number": 3},
        ]
        result = format_sources_section(sources)
        assert "**Fontes:**" in result
        assert "Contrato.pdf" in result
        assert "Anexo.pdf" in result

    def test_format_empty_sources(self):
        """Testa seção de fontes vazia."""
        result = format_sources_section([])
        assert result == ""

    def test_format_sources_with_snippets(self):
        """Testa fontes com snippets."""
        sources = [
            {
                "document_name": "Doc.pdf",
                "page_number": 1,
                "content_snippet": "Este é um trecho do documento",
            }
        ]
        result = format_sources_section(sources, include_snippets=True)
        assert "Este é um trecho" in result


class TestFormatTable:
    """Testes para formatação de tabelas."""

    def test_format_basic_table(self):
        """Testa tabela básica."""
        data = [
            {"categoria": "A", "valor": 100},
            {"categoria": "B", "valor": 200},
        ]
        result = format_table(data)
        assert "|" in result
        assert "Categoria" in result
        assert "Valor" in result

    def test_format_table_with_columns(self):
        """Testa tabela com colunas especificadas."""
        data = [{"cat": "A", "val": 100}]
        columns = [
            {"key": "cat", "title": "Categoria"},
            {"key": "val", "title": "Valor Total"},
        ]
        result = format_table(data, columns=columns)
        assert "Categoria" in result
        assert "Valor Total" in result

    def test_format_table_with_title(self):
        """Testa tabela com título."""
        data = [{"a": 1}]
        result = format_table(data, title="Minha Tabela")
        assert "**Minha Tabela**" in result

    def test_format_empty_table(self):
        """Testa tabela vazia."""
        result = format_table([])
        assert "Nenhum dado disponível" in result

    def test_format_table_max_rows(self):
        """Testa limite de linhas."""
        data = [{"a": i} for i in range(20)]
        result = format_table(data, max_rows=5)
        assert "mais" in result.lower() or "..." in result


class TestFormatCostTable:
    """Testes para formatação de tabela de custos."""

    def test_format_cost_table(self):
        """Testa tabela de custos."""
        data = [
            {"category": "Consultas", "total_paid": 1000, "percentage": 50},
            {"category": "Exames", "total_paid": 1000, "percentage": 50},
        ]
        result = format_cost_table(data)
        assert "Consultas" in result
        assert "Exames" in result
        assert "R$" in result


class TestFormatPeriodTable:
    """Testes para formatação de tabela de período."""

    def test_format_period_table(self):
        """Testa tabela de período."""
        data = [
            {"month": "Jan/24", "total_paid": 1000, "variation_percent": None},
            {"month": "Fev/24", "total_paid": 1100, "variation_percent": 10},
        ]
        result = format_period_table(data)
        assert "Jan/24" in result
        assert "Fev/24" in result
        assert "+" in result or "10" in result


class TestFormatRecommendation:
    """Testes para formatação de recomendações."""

    def test_format_recommendation_dict(self):
        """Testa formatação de recomendação de dicionário."""
        rec = {
            "title": "Renegociar contrato",
            "description": "Buscar melhores condições",
            "priority": "alta",
        }
        result = format_recommendation(rec)
        assert "[ALTA]" in result
        assert "Renegociar contrato" in result

    def test_format_recommendation_object(self):
        """Testa formatação de recomendação de objeto."""
        rec = Recommendation(
            title="Reduzir custos",
            description="Implementar coparticipação",
            priority=RecommendationPriority.MEDIUM,
        )
        result = format_recommendation(rec)
        assert "[MÉDIA]" in result
        assert "Reduzir custos" in result

    def test_format_recommendation_with_savings(self):
        """Testa recomendação com economia estimada."""
        rec = {
            "title": "Ação",
            "description": "Descrição",
            "priority": "alta",
            "estimated_savings": 50000,
        }
        result = format_recommendation(rec, include_details=True)
        assert "Economia estimada" in result
        assert "R$" in result

    def test_format_recommendation_with_actions(self):
        """Testa recomendação com itens de ação."""
        rec = {
            "title": "Ação",
            "description": "Descrição",
            "priority": "média",
            "action_items": ["Passo 1", "Passo 2"],
        }
        result = format_recommendation(rec, include_details=True)
        assert "Passo 1" in result
        assert "Passo 2" in result


class TestFormatRecommendationsSection:
    """Testes para seção de recomendações."""

    def test_format_recommendations_section(self):
        """Testa seção de recomendações."""
        recs = [
            {"title": "Alta 1", "description": "Desc", "priority": "alta"},
            {"title": "Média 1", "description": "Desc", "priority": "média"},
        ]
        result = format_recommendations_section(recs)
        assert "## Recomendações" in result
        assert "Alta 1" in result
        assert "Média 1" in result

    def test_format_empty_recommendations(self):
        """Testa seção vazia."""
        result = format_recommendations_section([])
        assert result == ""

    def test_format_recommendations_grouped(self):
        """Testa agrupamento por prioridade."""
        recs = [
            {"title": "R1", "description": "D", "priority": "baixa"},
            {"title": "R2", "description": "D", "priority": "alta"},
        ]
        result = format_recommendations_section(recs, group_by_priority=True)
        assert "Prioridade Alta" in result
        assert "Prioridade Baixa" in result


class TestFormatCallout:
    """Testes para formatação de callouts."""

    def test_format_info_callout(self):
        """Testa callout de informação."""
        result = format_callout("Texto informativo", CalloutType.INFO)
        assert "Informação" in result
        assert "Texto informativo" in result

    def test_format_warning_callout(self):
        """Testa callout de aviso."""
        result = format_callout("Atenção!", CalloutType.WARNING)
        assert "Atenção" in result

    def test_format_callout_custom_title(self):
        """Testa callout com título customizado."""
        result = format_callout("Conteúdo", CalloutType.INFO, title="Nota")
        assert "Nota" in result


class TestFormatSummaryBox:
    """Testes para caixa de resumo."""

    def test_format_summary_box(self):
        """Testa caixa de resumo."""
        items = {
            "Total Gasto": 100000,
            "Economia": 15000,
        }
        result = format_summary_box(items)
        assert "**Resumo**" in result
        assert "Total Gasto" in result
        assert "R$" in result


class TestResponseFormatter:
    """Testes para a classe ResponseFormatter."""

    def test_basic_usage(self):
        """Testa uso básico do formatter."""
        formatter = ResponseFormatter()
        formatter.add_heading("Título")
        formatter.add_paragraph("Parágrafo de texto")
        result = formatter.build()
        assert "## Título" in result
        assert "Parágrafo de texto" in result

    def test_add_table(self):
        """Testa adição de tabela."""
        formatter = ResponseFormatter()
        data = [{"col1": "a", "col2": "b"}]
        formatter.add_table(data)
        result = formatter.build()
        assert "|" in result

    def test_add_sources(self):
        """Testa adição de fontes."""
        formatter = ResponseFormatter()
        formatter.add_text("Texto")
        formatter.add_source({
            "document_name": "Doc.pdf",
            "page_number": 1,
        })
        result = formatter.build(include_sources=True)
        assert "Fontes" in result
        assert "Doc.pdf" in result

    def test_add_recommendation(self):
        """Testa adição de recomendação."""
        formatter = ResponseFormatter()
        rec = {
            "title": "Recomendação",
            "description": "Descrição",
            "priority": "alta",
        }
        formatter.add_recommendation(rec)
        result = formatter.build()
        assert "[ALTA]" in result

    def test_add_callout(self):
        """Testa adição de callout."""
        formatter = ResponseFormatter()
        formatter.add_callout("Atenção!", CalloutType.WARNING)
        result = formatter.build()
        assert ">" in result

    def test_add_list(self):
        """Testa adição de lista."""
        formatter = ResponseFormatter()
        formatter.add_list(["Item 1", "Item 2"])
        result = formatter.build()
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_add_ordered_list(self):
        """Testa adição de lista ordenada."""
        formatter = ResponseFormatter()
        formatter.add_list(["Item 1", "Item 2"], ordered=True)
        result = formatter.build()
        assert "1. Item 1" in result
        assert "2. Item 2" in result

    def test_add_divider(self):
        """Testa adição de divisor."""
        formatter = ResponseFormatter()
        formatter.add_text("Antes")
        formatter.add_divider()
        formatter.add_text("Depois")
        result = formatter.build()
        assert "---" in result

    def test_clear(self):
        """Testa limpeza do formatter."""
        formatter = ResponseFormatter()
        formatter.add_text("Texto")
        formatter.clear()
        result = formatter.build()
        assert result == ""

    def test_chaining(self):
        """Testa encadeamento de métodos."""
        result = (
            ResponseFormatter()
            .add_heading("Título")
            .add_paragraph("Texto")
            .add_divider()
            .build()
        )
        assert "## Título" in result
        assert "Texto" in result
        assert "---" in result

    def test_inline_citation(self):
        """Testa citação inline."""
        formatter = ResponseFormatter()
        source = {"document_name": "Doc.pdf", "page_number": 5}
        formatter.add_inline_citation("Este é um fato", source)
        result = formatter.build()
        assert "Este é um fato" in result
        assert "Doc.pdf" in result


class TestFormatConsolidatedResponse:
    """Testes para consolidação de respostas."""

    def test_format_consolidated_response(self):
        """Testa consolidação de respostas."""
        sections = [
            {"title": "Análise de Contrato", "content": "O contrato prevê..."},
            {"title": "Análise de Custos", "content": "Os custos totalizaram..."},
        ]
        result = format_consolidated_response(sections)
        assert "Análise de Contrato" in result
        assert "Análise de Custos" in result

    def test_format_consolidated_with_sources(self):
        """Testa consolidação com fontes."""
        sections = [{"content": "Texto"}]
        sources = [{"document_name": "Doc.pdf", "page_number": 1}]
        result = format_consolidated_response(sections, sources=sources)
        assert "Doc.pdf" in result


class TestEdgeCases:
    """Testes de casos extremos."""

    def test_very_long_content(self):
        """Testa conteúdo muito longo."""
        long_text = "A" * 10000
        result = format_callout(long_text, CalloutType.INFO)
        assert long_text in result

    def test_special_characters(self):
        """Testa caracteres especiais."""
        result = format_currency(1234.56)
        assert "R$" in result  # Verifica que não quebrou com caracteres especiais

    def test_unicode_in_table(self):
        """Testa unicode em tabela."""
        data = [{"categoria": "Análise & Testes", "valor": 100}]
        result = format_table(data)
        assert "Análise & Testes" in result

    def test_empty_dict_values(self):
        """Testa valores vazios em dicionário."""
        data = [{"a": None, "b": "", "c": 0}]
        result = format_table(data)
        assert "|" in result

    def test_negative_currency(self):
        """Testa moeda negativa."""
        result = format_currency(-1234.56, include_sign=True)
        assert "-" in result
        assert "1.234,56" in result
