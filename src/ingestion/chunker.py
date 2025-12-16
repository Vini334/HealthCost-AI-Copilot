"""
Sistema de chunking inteligente para documentos.

Divide documentos em chunks otimizados para:
- Busca semântica (embeddings)
- Contexto de LLMs
- Citação de fontes
"""

import re
from typing import Optional
from uuid import UUID, uuid4

from src.config.logging import get_logger
from src.ingestion.pdf_extractor import PageContent
from src.models.chunks import (
    ChunkingConfig,
    ChunkingStrategy,
    DEFAULT_CHUNKING_CONFIG,
    DocumentChunk,
)

logger = get_logger(__name__)


# ============================================================
# Padrões regex para detectar seções em contratos
# ============================================================

# Padrão para cláusulas: "CLÁUSULA 1", "Cláusula 1.", "CLÁUSULA PRIMEIRA"
CLAUSE_PATTERN = re.compile(
    r'^(?:CLÁUSULA|CLAUSULA|Cláusula|Clausula)\s*'
    r'(?:\d+|PRIMEIR[AO]|SEGUND[AO]|TERCEIR[AO]|QUART[AO]|QUINT[AO]|'
    r'SEXT[AO]|SÉTIM[AO]|OITAV[AO]|NON[AO]|DÉCIM[AO])'
    r'[.:°ª\s\-–—]*'
    r'(.*)$',
    re.IGNORECASE | re.MULTILINE
)

# Padrão para seções numeradas: "1.", "1.1", "1.1.1", "I.", "II."
SECTION_PATTERN = re.compile(
    r'^(\d+(?:\.\d+)*\.?|[IVXLC]+\.)\s+(.+)$',
    re.MULTILINE
)

# Padrão para artigos: "Art. 1", "Artigo 1º"
ARTICLE_PATTERN = re.compile(
    r'^(?:Art\.?|Artigo)\s*(\d+)[°º]?\s*[.:–—-]?\s*(.*)$',
    re.IGNORECASE | re.MULTILINE
)

# Padrão para parágrafos: "§ 1º", "Parágrafo único"
PARAGRAPH_PATTERN = re.compile(
    r'^(?:§\s*\d+[°º]?|Parágrafo\s+(?:único|\d+[°º]?))\s*[.:–—-]?\s*(.*)$',
    re.IGNORECASE | re.MULTILINE
)

# Padrão para anexos: "ANEXO I", "Anexo A"
ANNEX_PATTERN = re.compile(
    r'^(?:ANEXO|Anexo)\s+([IVXLC]+|[A-Z]|\d+)\s*[.:–—-]?\s*(.*)$',
    re.IGNORECASE | re.MULTILINE
)


class TextChunker:
    """
    Divide textos em chunks inteligentes.

    Estratégias disponíveis:
    - PAGE: Um chunk por página
    - SECTION: Baseado em seções/cláusulas detectadas
    - FIXED_SIZE: Tamanho fixo com overlap
    - HYBRID: Tenta seção, fallback para página/tamanho

    Exemplo:
        chunker = TextChunker()
        chunks = chunker.chunk_pages(
            pages=pdf_pages,
            document_id=doc_id,
            client_id="cliente-123"
        )
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        """
        Inicializa o chunker com configuração.

        Args:
            config: Configuração de chunking (usa padrão se não especificado)
        """
        self.config = config or DEFAULT_CHUNKING_CONFIG
        logger.info(
            "TextChunker inicializado",
            strategy=self.config.strategy.value,
            chunk_size=self.config.chunk_size,
            overlap=self.config.chunk_overlap,
        )

    def _detect_section_start(self, line: str) -> Optional[tuple[str, str, str]]:
        """
        Detecta se uma linha é início de seção.

        Args:
            line: Linha de texto

        Returns:
            Tupla (tipo, número, título) se for início de seção, None caso contrário
        """
        line = line.strip()

        # Tenta cada padrão
        if match := CLAUSE_PATTERN.match(line):
            title = match.group(1).strip() if match.group(1) else ""
            # Extrai número da cláusula do match
            number_match = re.search(r'\d+', line)
            number = number_match.group() if number_match else ""
            return ("clausula", number, title or line)

        if match := ARTICLE_PATTERN.match(line):
            return ("artigo", match.group(1), match.group(2).strip())

        if match := ANNEX_PATTERN.match(line):
            return ("anexo", match.group(1), match.group(2).strip())

        if match := SECTION_PATTERN.match(line):
            number = match.group(1).rstrip('.')
            title = match.group(2).strip()
            # Só considera se o título parece um título (começa com maiúscula, >3 chars)
            if title and title[0].isupper() and len(title) > 3:
                return ("secao", number, title)

        return None

    def _split_into_sections(
        self,
        pages: list[PageContent],
    ) -> list[dict]:
        """
        Divide o texto em seções baseado em padrões detectados.

        Args:
            pages: Lista de páginas do documento

        Returns:
            Lista de dicts com informações de cada seção
        """
        sections = []
        current_section = {
            "type": None,
            "number": None,
            "title": None,
            "content": [],
            "page_start": 1,
            "page_end": 1,
        }

        for page in pages:
            lines = page.text.split('\n')

            for line in lines:
                section_info = self._detect_section_start(line)

                if section_info:
                    # Salva seção anterior se tiver conteúdo
                    if current_section["content"]:
                        current_section["text"] = '\n'.join(current_section["content"])
                        sections.append(current_section.copy())

                    # Inicia nova seção
                    section_type, number, title = section_info
                    current_section = {
                        "type": section_type,
                        "number": number,
                        "title": title,
                        "content": [line],
                        "page_start": page.page_number,
                        "page_end": page.page_number,
                    }
                else:
                    # Adiciona linha à seção atual
                    current_section["content"].append(line)
                    current_section["page_end"] = page.page_number

        # Não esquece a última seção
        if current_section["content"]:
            current_section["text"] = '\n'.join(current_section["content"])
            sections.append(current_section)

        return sections

    def _split_by_size(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
    ) -> list[str]:
        """
        Divide texto em chunks de tamanho fixo com overlap.

        O overlap faz com que chunks adjacentes compartilhem texto,
        evitando que ideias sejam cortadas no meio.

        Args:
            text: Texto a dividir
            chunk_size: Tamanho alvo de cada chunk
            overlap: Quantidade de caracteres de sobreposição

        Returns:
            Lista de strings (chunks)

        Exemplo:
            text = "ABCDEFGHIJ" (10 chars)
            chunk_size = 5
            overlap = 2
            Resultado: ["ABCDE", "DEFGH", "GHIJ"]
                       (DE e GH são compartilhados)
        """
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Tenta não cortar no meio de uma palavra
            if end < len(text):
                # Procura o último espaço antes do limite
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Próximo início = fim atual - overlap
            start = end - overlap
            if start <= 0:
                start = end  # Evita loop infinito

        return chunks

    def _chunk_by_page(
        self,
        pages: list[PageContent],
        document_id: UUID,
        client_id: str,
    ) -> list[DocumentChunk]:
        """
        Cria um chunk por página.

        Estratégia mais simples, útil quando o documento
        não tem estrutura clara de seções.
        """
        chunks = []

        for i, page in enumerate(pages):
            if not page.text.strip():
                continue

            # Se página muito grande, divide por tamanho
            if len(page.text) > self.config.max_section_length:
                sub_chunks = self._split_by_size(
                    page.text,
                    self.config.chunk_size,
                    self.config.chunk_overlap,
                )
                for j, sub_text in enumerate(sub_chunks):
                    chunk = DocumentChunk(
                        document_id=document_id,
                        client_id=client_id,
                        content=sub_text,
                        page_number=page.page_number,
                        chunk_index=len(chunks),
                        strategy=ChunkingStrategy.PAGE,
                    )
                    chunks.append(chunk)
            else:
                chunk = DocumentChunk(
                    document_id=document_id,
                    client_id=client_id,
                    content=page.text,
                    page_number=page.page_number,
                    chunk_index=len(chunks),
                    strategy=ChunkingStrategy.PAGE,
                )
                chunks.append(chunk)

        return chunks

    def _chunk_by_section(
        self,
        pages: list[PageContent],
        document_id: UUID,
        client_id: str,
    ) -> list[DocumentChunk]:
        """
        Cria chunks baseados em seções detectadas.

        Melhor para documentos estruturados como contratos.
        """
        sections = self._split_into_sections(pages)
        chunks = []

        for section in sections:
            text = section.get("text", "")
            if not text.strip():
                continue

            # Se seção muito grande, divide por tamanho
            if len(text) > self.config.max_section_length:
                sub_chunks = self._split_by_size(
                    text,
                    self.config.chunk_size,
                    self.config.chunk_overlap,
                )
                for sub_text in sub_chunks:
                    chunk = DocumentChunk(
                        document_id=document_id,
                        client_id=client_id,
                        content=sub_text,
                        page_start=section["page_start"],
                        page_end=section["page_end"],
                        section_title=section.get("title"),
                        section_number=section.get("number"),
                        section_type=section.get("type"),
                        chunk_index=len(chunks),
                        strategy=ChunkingStrategy.SECTION,
                    )
                    chunks.append(chunk)
            # Se seção muito pequena, pode juntar com a próxima (futuro)
            elif len(text) < self.config.min_section_length:
                # Por ora, mantém como chunk separado
                chunk = DocumentChunk(
                    document_id=document_id,
                    client_id=client_id,
                    content=text,
                    page_start=section["page_start"],
                    page_end=section["page_end"],
                    section_title=section.get("title"),
                    section_number=section.get("number"),
                    section_type=section.get("type"),
                    chunk_index=len(chunks),
                    strategy=ChunkingStrategy.SECTION,
                )
                chunks.append(chunk)
            else:
                chunk = DocumentChunk(
                    document_id=document_id,
                    client_id=client_id,
                    content=text,
                    page_start=section["page_start"],
                    page_end=section["page_end"],
                    section_title=section.get("title"),
                    section_number=section.get("number"),
                    section_type=section.get("type"),
                    chunk_index=len(chunks),
                    strategy=ChunkingStrategy.SECTION,
                )
                chunks.append(chunk)

        return chunks

    def _chunk_by_fixed_size(
        self,
        pages: list[PageContent],
        document_id: UUID,
        client_id: str,
    ) -> list[DocumentChunk]:
        """
        Cria chunks de tamanho fixo com overlap.

        Fallback quando outras estratégias não funcionam bem.
        """
        # Concatena todo o texto com marcadores de página
        full_text = ""
        page_markers = []  # Lista de (posição, página)

        for page in pages:
            if page.text.strip():
                page_markers.append((len(full_text), page.page_number))
                full_text += page.text + "\n\n"

        # Divide por tamanho
        text_chunks = self._split_by_size(
            full_text,
            self.config.chunk_size,
            self.config.chunk_overlap,
        )

        chunks = []
        for i, text in enumerate(text_chunks):
            # Encontra em qual página está o início do chunk
            chunk_start = full_text.find(text[:50]) if len(text) >= 50 else 0
            page_number = 1
            for pos, page in page_markers:
                if pos <= chunk_start:
                    page_number = page
                else:
                    break

            chunk = DocumentChunk(
                document_id=document_id,
                client_id=client_id,
                content=text,
                page_number=page_number,
                chunk_index=i,
                strategy=ChunkingStrategy.FIXED_SIZE,
            )
            chunks.append(chunk)

        return chunks

    def _link_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """
        Adiciona referências entre chunks adjacentes.

        Permite navegação para contexto anterior/posterior.
        """
        for i, chunk in enumerate(chunks):
            if i > 0:
                chunk.previous_chunk_id = chunks[i - 1].id
            if i < len(chunks) - 1:
                chunk.next_chunk_id = chunks[i + 1].id
            chunk.total_chunks = len(chunks)

        return chunks

    def chunk_pages(
        self,
        pages: list[PageContent],
        document_id: UUID,
        client_id: str,
    ) -> list[DocumentChunk]:
        """
        Divide páginas de um documento em chunks.

        Este é o método principal para chunking.

        Args:
            pages: Lista de PageContent do PDF extrator
            document_id: ID do documento
            client_id: ID do cliente

        Returns:
            Lista de DocumentChunk prontos para indexação
        """
        if not pages:
            logger.warning("Nenhuma página para processar")
            return []

        total_chars = sum(p.char_count for p in pages)
        logger.info(
            "Iniciando chunking",
            strategy=self.config.strategy.value,
            pages=len(pages),
            total_chars=total_chars,
        )

        # Seleciona estratégia
        if self.config.strategy == ChunkingStrategy.PAGE:
            chunks = self._chunk_by_page(pages, document_id, client_id)

        elif self.config.strategy == ChunkingStrategy.SECTION:
            chunks = self._chunk_by_section(pages, document_id, client_id)

        elif self.config.strategy == ChunkingStrategy.FIXED_SIZE:
            chunks = self._chunk_by_fixed_size(pages, document_id, client_id)

        elif self.config.strategy == ChunkingStrategy.HYBRID:
            # Tenta seção primeiro
            chunks = self._chunk_by_section(pages, document_id, client_id)

            # Se não encontrou seções úteis, fallback para página
            sections_found = sum(1 for c in chunks if c.section_title)
            if sections_found < len(chunks) * 0.3:  # Menos de 30% com seção
                logger.info(
                    "Poucas seções detectadas, usando fallback para página",
                    sections_found=sections_found,
                    total_chunks=len(chunks),
                )
                chunks = self._chunk_by_page(pages, document_id, client_id)

        else:
            # Fallback
            chunks = self._chunk_by_page(pages, document_id, client_id)

        # Link chunks adjacentes
        chunks = self._link_chunks(chunks)

        logger.info(
            "Chunking concluído",
            total_chunks=len(chunks),
            avg_size=sum(c.content_length for c in chunks) // len(chunks) if chunks else 0,
        )

        return chunks

    def chunk_text(
        self,
        text: str,
        document_id: UUID,
        client_id: str,
    ) -> list[DocumentChunk]:
        """
        Divide um texto simples em chunks.

        Versão simplificada para textos sem estrutura de página.

        Args:
            text: Texto a dividir
            document_id: ID do documento
            client_id: ID do cliente

        Returns:
            Lista de DocumentChunk
        """
        # Cria uma página virtual
        page = PageContent(page_number=1, text=text)
        return self.chunk_pages([page], document_id, client_id)
