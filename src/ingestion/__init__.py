"""
Módulo de ingestão de documentos.

Responsável por:
- Extração de texto de PDFs
- Chunking inteligente de documentos
- Processamento de contratos
- Processamento de dados de custos
"""

from src.ingestion.pdf_extractor import (
    PDFExtractor,
    PDFExtractionResult,
    PageContent,
)
from src.ingestion.chunker import TextChunker
from src.ingestion.contract_processor import (
    ContractProcessor,
    get_contract_processor,
)
from src.ingestion.cost_processor import (
    CostDataProcessor,
    get_cost_processor,
)

__all__ = [
    # PDF
    "PDFExtractor",
    "PDFExtractionResult",
    "PageContent",
    # Chunking
    "TextChunker",
    # Contratos
    "ContractProcessor",
    "get_contract_processor",
    # Custos
    "CostDataProcessor",
    "get_cost_processor",
]
