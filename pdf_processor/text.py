"""Text processing module for PDF processor."""

import subprocess
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import fitz
from dataclasses import dataclass
from .errors import (
    Result,
    PDFProcessorError,
    ValidationError,
    ExternalToolError,
)


logger = logging.getLogger(__name__)

@dataclass
class TextBlock:
    """A block of text with positional metadata."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float
    font: str


def check_dependencies() -> Result[None, ExternalToolError]:
    """Check if mutool is installed and accessible."""
    try:
        result = subprocess.run(
            ["mutool", "--version"],
            capture_output=True,
            text=True
        )
        # mutool --version returns 1 but still outputs version info
        if "mutool version" in result.stderr:
            return Result.Ok(None)
        return Result.Err(
            ExternalToolError("mutool", "Unexpected output from version check")
        )
    except FileNotFoundError:
        return Result.Err(
            ExternalToolError("mutool", "Not found in PATH")
        )


def validate_pdf(pdf_path: str) -> Result[Path, ValidationError]:
    """Validate that a file is a valid, readable PDF.
    
    Performs the following checks:
    1. Path exists and is a file
    2. File has .pdf extension
    3. File is a valid PDF (can be opened by PyMuPDF)
    4. File is not empty or corrupted
    
    Args:
        pdf_path: Path to the PDF file to validate
        
    Returns:
        Result: On success, Ok(Path) with resolved path
               On failure, Err(ValidationError) with error details
    """
    try:
        # Basic path validation
        path = Path(pdf_path)
        if not path.exists():
            return Result.Err(ValidationError(f"PDF file not found: {pdf_path}"))
        if not path.is_file():
            return Result.Err(ValidationError(f"Not a file: {pdf_path}"))
        if path.suffix.lower() != ".pdf":
            return Result.Err(ValidationError(f"Not a PDF file: {pdf_path}"))
            
        # Check if file is empty
        if path.stat().st_size == 0:
            return Result.Err(ValidationError(f"Empty PDF file: {pdf_path}"))
            
        # Try to open with PyMuPDF to verify it's a valid PDF
        try:
            doc = fitz.open(pdf_path)
            if doc.page_count == 0:
                doc.close()
                return Result.Err(ValidationError(f"PDF has no pages: {pdf_path}"))
            doc.close()
        except Exception as e:
            return Result.Err(ValidationError(f"Invalid PDF file: {pdf_path} ({str(e)})"))
            
        return Result.Ok(path)
    except Exception as e:
        return Result.Err(ValidationError(f"Invalid path: {pdf_path} ({str(e)})"))


def extract_text_with_metadata(pdf_path: str) -> Result[str, PDFProcessorError]:
    """Extract raw text from a PDF file using mutool."""
    # Validate PDF file
    pdf_path_result = validate_pdf(pdf_path)
    if not pdf_path_result.is_ok:
        return Result.Err(pdf_path_result.error)

    # Check dependencies
    deps_result = check_dependencies()
    if not deps_result.is_ok:
        return Result.Err(deps_result.error)

    try:
        logger.info("Extracting text from PDF: %s", pdf_path)
        process = subprocess.run(
            ["mutool", "draw", "-F", "text", pdf_path],
            capture_output=True,
            text=True,
            check=True
        )
        return Result.Ok(process.stdout)
    except subprocess.CalledProcessError as e:
        return Result.Err(
            ExternalToolError("mutool", "Failed to extract text", e.returncode)
        )
    except Exception as e:
        logger.exception("Failed to extract text from PDF: %s", e)
        return Result.Err(PDFProcessorError(f"Failed to extract text: {str(e)}"))


def extract_hyperlinks_with_pymupdf(pdf_path: str) -> Result[List[Tuple[str, str]], PDFProcessorError]:
    """Extract hyperlinks from a PDF file using PyMuPDF."""
    # Validate PDF file
    pdf_path_result = validate_pdf(pdf_path)
    if not pdf_path_result.is_ok:
        return Result.Err(pdf_path_result.error)

    try:
        logger.info("Extracting hyperlinks from PDF: %s", pdf_path)
        doc = fitz.open(pdf_path)
        hyperlinks = []
        for page in doc:
            hyperlinks.extend(parse_hyperlinks(page))
        doc.close()
        return Result.Ok(hyperlinks)
    except Exception as e:
        logger.exception("Failed to extract hyperlinks from PDF: %s", e)
        return Result.Err(PDFProcessorError(f"Failed to extract hyperlinks: {str(e)}"))


def parse_hyperlinks(page: fitz.Page) -> List[Tuple[str, str]]:
    """Extract hyperlinks from a single PDF page."""
    hyperlinks = []
    for link in page.get_links():
        if "uri" in link:
            # Get the text under the link rectangle
            rect = fitz.Rect(link["from"])
            text = page.get_textbox(rect)
            if text.strip():
                hyperlinks.append((text.strip(), link["uri"]))
    return hyperlinks


def extract_layout_with_pymupdf(pdf_path: str) -> Result[List[TextBlock], PDFProcessorError]:
    """Extract text with layout information from a PDF using PyMuPDF."""
    # Validate PDF file
    pdf_path_result = validate_pdf(pdf_path)
    if not pdf_path_result.is_ok:
        return Result.Err(pdf_path_result.error)

    try:
        logger.info("Extracting layout from PDF: %s", pdf_path)
        doc = fitz.open(pdf_path)
        text_blocks = []
        for page in doc:
            text_blocks.extend(parse_page_layout(page))
        doc.close()
        return Result.Ok(text_blocks)
    except Exception as e:
        logger.exception("Failed to extract layout from PDF: %s", e)
        return Result.Err(PDFProcessorError(f"Failed to extract layout: {str(e)}"))


def parse_page_layout(page: fitz.Page) -> List[TextBlock]:
    """Extract text blocks from a single PDF page."""
    blocks = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        blocks.append(TextBlock(
                            text=text,
                            x0=span["bbox"][0],
                            y0=span["bbox"][1],
                            x1=span["bbox"][2],
                            y1=span["bbox"][3],
                            font_size=span.get("size", 0),
                            font=span.get("font", "")
                        ))
    return blocks


def save_text_to_file(text: str, output_path: Path) -> Result[Path, PDFProcessorError]:
    """Save extracted text to a file."""
    try:
        output_path.write_text(text)
        return Result.Ok(output_path)
    except Exception as e:
        logger.exception("Failed to save text to file: %s", e)
        return Result.Err(PDFProcessorError(f"Failed to save text: {str(e)}"))


def save_markdown_to_file(markdown: str, output_path: Path) -> Result[Path, PDFProcessorError]:
    """Save markdown content to a file."""
    try:
        output_path.write_text(markdown)
        return Result.Ok(output_path)
    except Exception as e:
        logger.exception("Failed to save markdown to file: %s", e)
        return Result.Err(PDFProcessorError(f"Failed to save markdown: {str(e)}"))
