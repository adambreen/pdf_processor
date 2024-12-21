"""
PDF processor module.

Provides reusable functions for text extraction, Markdown conversion,
and image extraction from PDF files.
"""

__version__ = "0.3.0"

from .text import (
    extract_text_with_metadata,
    extract_hyperlinks_with_pymupdf,
    extract_layout_with_pymupdf,
)

from .main import (
    layout_to_markdown,
)

from .table import (
    Table,
    TableCell,
    TableMetrics,
    TextBlock,
    detect_tables,
    detect_tables_from_borders,
    detect_tables_from_alignment,
    table_to_markdown,
    is_potential_table_row,
)

__all__ = [
    'TextBlock',
    'extract_text_with_metadata',
    'extract_hyperlinks_with_pymupdf',
    'extract_layout_with_pymupdf',
    'layout_to_markdown',
    'Table',
    'TableCell',
    'TableMetrics',
    'detect_tables',
    'detect_tables_from_borders',
    'detect_tables_from_alignment',
    'table_to_markdown',
    'is_potential_table_row',
]
