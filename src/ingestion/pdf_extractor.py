"""
Extrator de texto de documentos PDF.

Utiliza pdfplumber para extrair texto mantendo a estrutura
e informações de página. Também detecta e extrai tabelas.
"""

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import pdfplumber

from src.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PageContent:
    """
    Conteúdo extraído de uma página do PDF.

    Attributes:
        page_number: Número da página (1-indexed)
        text: Texto extraído da página
        has_tables: Se a página contém tabelas
        table_count: Quantidade de tabelas na página
        char_count: Quantidade de caracteres no texto
    """
    page_number: int
    text: str
    has_tables: bool = False
    table_count: int = 0
    char_count: int = 0

    def __post_init__(self):
        """Calcula char_count após inicialização."""
        self.char_count = len(self.text) if self.text else 0


@dataclass
class PDFExtractionResult:
    """
    Resultado completo da extração de um PDF.

    Attributes:
        success: Se a extração foi bem-sucedida
        total_pages: Total de páginas do documento
        pages: Lista de PageContent com o conteúdo de cada página
        full_text: Texto completo concatenado
        total_characters: Total de caracteres extraídos
        error_message: Mensagem de erro se success=False
    """
    success: bool
    total_pages: int
    pages: list[PageContent]
    full_text: str
    total_characters: int
    error_message: Optional[str] = None


class PDFExtractor:
    """
    Extrai texto de documentos PDF.

    Funcionalidades:
    - Extração de texto por página
    - Detecção de tabelas
    - Limpeza e normalização de texto
    - Remoção de cabeçalhos/rodapés repetidos

    Exemplo de uso:
        extractor = PDFExtractor()
        result = extractor.extract_from_bytes(pdf_bytes)
        if result.success:
            for page in result.pages:
                print(f"Página {page.page_number}: {page.char_count} caracteres")
    """

    def __init__(
        self,
        remove_headers_footers: bool = True,
        normalize_whitespace: bool = True,
        min_line_length: int = 3,
    ):
        """
        Inicializa o extrator.

        Args:
            remove_headers_footers: Tentar remover cabeçalhos/rodapés repetidos
            normalize_whitespace: Normalizar espaços em branco
            min_line_length: Tamanho mínimo de linha para considerar válida
        """
        self._remove_headers_footers = remove_headers_footers
        self._normalize_whitespace = normalize_whitespace
        self._min_line_length = min_line_length

    def _clean_text(self, text: str) -> str:
        """
        Limpa e normaliza o texto extraído.

        Args:
            text: Texto bruto extraído do PDF

        Returns:
            Texto limpo e normalizado
        """
        if not text:
            return ""

        # Remove caracteres de controle (exceto newlines e tabs)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        if self._normalize_whitespace:
            # Substitui múltiplos espaços por um só
            text = re.sub(r'[^\S\n]+', ' ', text)
            # Remove espaços no início/fim de linhas
            text = re.sub(r'^ +| +$', '', text, flags=re.MULTILINE)
            # Substitui 3+ quebras de linha por 2
            text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove linhas muito curtas (provavelmente lixo)
        lines = text.split('\n')
        cleaned_lines = [
            line for line in lines
            if len(line.strip()) >= self._min_line_length or line.strip() == ''
        ]
        text = '\n'.join(cleaned_lines)

        return text.strip()

    def _detect_header_footer(self, pages: list[PageContent]) -> tuple[str, str]:
        """
        Detecta cabeçalhos e rodapés repetidos.

        Analisa as primeiras e últimas linhas de cada página
        para encontrar padrões repetidos (ex: número de página, nome do documento).

        Args:
            pages: Lista de páginas extraídas

        Returns:
            Tupla (header_pattern, footer_pattern) com padrões detectados
        """
        if len(pages) < 3:
            return "", ""

        # Coleta primeiras e últimas linhas de cada página
        first_lines = []
        last_lines = []

        for page in pages:
            lines = page.text.strip().split('\n')
            if lines:
                first_lines.append(lines[0].strip())
                last_lines.append(lines[-1].strip())

        # Procura padrões repetidos (aparecem em >50% das páginas)
        def find_common_pattern(lines: list[str], threshold: float = 0.5) -> str:
            """Encontra padrão comum nas linhas."""
            if not lines:
                return ""

            # Conta ocorrências (ignorando números que podem ser páginas)
            normalized = [re.sub(r'\d+', '#', line) for line in lines]
            counts = {}
            for line in normalized:
                counts[line] = counts.get(line, 0) + 1

            # Retorna o mais comum se passar do threshold
            for pattern, count in counts.items():
                if count / len(lines) >= threshold and len(pattern) > 5:
                    return pattern

            return ""

        header = find_common_pattern(first_lines)
        footer = find_common_pattern(last_lines)

        return header, footer

    def _remove_header_footer_from_text(
        self,
        text: str,
        header_pattern: str,
        footer_pattern: str,
    ) -> str:
        """
        Remove cabeçalhos e rodapés do texto.

        Args:
            text: Texto da página
            header_pattern: Padrão do cabeçalho (com # no lugar de números)
            footer_pattern: Padrão do rodapé

        Returns:
            Texto sem cabeçalho/rodapé
        """
        if not text:
            return text

        lines = text.split('\n')

        # Remove primeira linha se bater com header
        if header_pattern and lines:
            first_normalized = re.sub(r'\d+', '#', lines[0].strip())
            if first_normalized == header_pattern:
                lines = lines[1:]

        # Remove última linha se bater com footer
        if footer_pattern and lines:
            last_normalized = re.sub(r'\d+', '#', lines[-1].strip())
            if last_normalized == footer_pattern:
                lines = lines[:-1]

        return '\n'.join(lines)

    def extract_from_bytes(self, pdf_bytes: bytes) -> PDFExtractionResult:
        """
        Extrai texto de um PDF a partir de bytes.

        Este é o método principal para extração.

        Args:
            pdf_bytes: Conteúdo do PDF em bytes

        Returns:
            PDFExtractionResult com o texto extraído

        Exemplo:
            with open("contrato.pdf", "rb") as f:
                result = extractor.extract_from_bytes(f.read())
        """
        logger.info("Iniciando extração de PDF", size_bytes=len(pdf_bytes))

        try:
            # BytesIO permite usar bytes como se fosse um arquivo
            pdf_file = BytesIO(pdf_bytes)

            # Abre o PDF com pdfplumber
            with pdfplumber.open(pdf_file) as pdf:
                total_pages = len(pdf.pages)
                logger.info("PDF aberto", total_pages=total_pages)

                pages: list[PageContent] = []

                # Extrai texto de cada página
                for i, page in enumerate(pdf.pages):
                    page_number = i + 1  # 1-indexed

                    # Extrai texto da página
                    text = page.extract_text() or ""
                    text = self._clean_text(text)

                    # Detecta tabelas na página
                    tables = page.extract_tables() or []
                    has_tables = len(tables) > 0

                    page_content = PageContent(
                        page_number=page_number,
                        text=text,
                        has_tables=has_tables,
                        table_count=len(tables),
                    )
                    pages.append(page_content)

                    logger.debug(
                        "Página processada",
                        page=page_number,
                        chars=page_content.char_count,
                        tables=len(tables),
                    )

            # Remove headers/footers se configurado
            if self._remove_headers_footers and len(pages) > 2:
                header, footer = self._detect_header_footer(pages)

                if header or footer:
                    logger.debug(
                        "Padrões detectados",
                        header=header[:30] if header else None,
                        footer=footer[:30] if footer else None,
                    )

                    for page in pages:
                        page.text = self._remove_header_footer_from_text(
                            page.text, header, footer
                        )
                        page.char_count = len(page.text)

            # Concatena texto completo
            full_text = "\n\n".join(
                f"[Página {p.page_number}]\n{p.text}"
                for p in pages
                if p.text.strip()
            )
            total_chars = sum(p.char_count for p in pages)

            logger.info(
                "Extração concluída",
                total_pages=total_pages,
                total_chars=total_chars,
            )

            return PDFExtractionResult(
                success=True,
                total_pages=total_pages,
                pages=pages,
                full_text=full_text,
                total_characters=total_chars,
            )

        except Exception as e:
            logger.error("Erro na extração de PDF", error=str(e))
            return PDFExtractionResult(
                success=False,
                total_pages=0,
                pages=[],
                full_text="",
                total_characters=0,
                error_message=str(e),
            )

    def extract_from_file(self, file_path: str) -> PDFExtractionResult:
        """
        Extrai texto de um arquivo PDF.

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            PDFExtractionResult com o texto extraído
        """
        logger.info("Lendo PDF de arquivo", path=file_path)

        try:
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
            return self.extract_from_bytes(pdf_bytes)
        except FileNotFoundError:
            logger.error("Arquivo não encontrado", path=file_path)
            return PDFExtractionResult(
                success=False,
                total_pages=0,
                pages=[],
                full_text="",
                total_characters=0,
                error_message=f"Arquivo não encontrado: {file_path}",
            )
        except Exception as e:
            logger.error("Erro ao ler arquivo", path=file_path, error=str(e))
            return PDFExtractionResult(
                success=False,
                total_pages=0,
                pages=[],
                full_text="",
                total_characters=0,
                error_message=str(e),
            )
