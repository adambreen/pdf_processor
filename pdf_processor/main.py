"""
PDF Processor Main Module

This module provides the core functionality for processing PDFs,
including text extraction, Markdown conversion, and image extraction.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import fitz
from .errors import (
    Result,
    PDFProcessorError,
    ValidationError,
    ExternalToolError,
    FileError
)
from .text import (
    TextBlock,
    extract_text_with_metadata,
    extract_hyperlinks_with_pymupdf,
    extract_layout_with_pymupdf,
    save_text_to_file,
    save_markdown_to_file,
    validate_pdf
)
from .table import detect_tables, TableMetrics

__all__ = ['process_pdf', 'parse_args']

def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if debug else logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger('fitz').setLevel(logging.WARNING)


def layout_to_markdown(layout: List[TextBlock], links: List[Tuple[str, str]] = None) -> str:
    """Convert layout-aware text blocks to Markdown.
    
    Args:
        layout: A list of text blocks with positional metadata.
        links: A list of hyperlinks as (text, url).
        
    Returns:
        str: Markdown-formatted text.
    """
    if links is None:
        links = []
        
    # Create a map of link text to URLs for quick lookup
    link_map = {text: url for text, url in links}
    
    # Sort blocks by vertical position first, then horizontal
    sorted_blocks = sorted(layout, key=lambda b: (b.y0, b.x0))
    
    # Group blocks into lines
    lines = []
    current_line = []
    last_y = None
    line_spacing_threshold = 5  # Adjust based on your needs
    
    for block in sorted_blocks:
        # Start a new line if vertical position changes significantly
        if last_y is not None and abs(block.y0 - last_y) > line_spacing_threshold:
            if current_line:
                lines.append(current_line)
            current_line = []
        
        current_line.append(block)
        last_y = block.y0
    
    # Add the last line
    if current_line:
        lines.append(current_line)
    
    # Convert lines to Markdown
    markdown_lines = []
    table_data = []
    in_table = False
    
    for line_blocks in lines:
        # Check if this is a heading
        if len(line_blocks) == 1 and line_blocks[0].font_size >= 14:
            # If we were in a table, convert it now
            if table_data:
                table_md = convert_table_to_markdown(table_data)
                if table_md:
                    markdown_lines.append(table_md)
                table_data = []
                in_table = False
            
            text = line_blocks[0].text.strip()
            if text in link_map:
                markdown_lines.append(f"[{text}]({link_map[text]})")
            else:
                markdown_lines.append(f"# {text}")
            continue
        
        # Check if this could be a table row
        words = []
        for block in line_blocks:
            # Split block text into potential cells
            block_words = block.text.strip().split()
            if len(block_words) > 1:
                # This block might contain multiple cells
                words.extend(block_words)
            else:
                words.append(block.text.strip())
        
        # Potential table header detection
        if not in_table and len(words) >= 2 and all(len(word.split()) == 1 for word in words):
            in_table = True
            table_data = [words]  # Start new table with header
        # Table data row detection
        elif in_table and len(words) >= len(table_data[0]):
            table_data.append(words)
        else:
            # If we were in a table, convert it now
            if table_data:
                table_md = convert_table_to_markdown(table_data)
                if table_md:
                    markdown_lines.append(table_md)
                table_data = []
                in_table = False
            
            # Process as regular text
            text = " ".join(words)
            if text:
                markdown_lines.append(text)
    
    # Handle any remaining table
    if table_data:
        table_md = convert_table_to_markdown(table_data)
        if table_md:
            markdown_lines.append(table_md)
    
    return "\n\n".join(markdown_lines)


def convert_table_to_markdown(table_data: List[List[str]]) -> str:
    """Convert table data to Markdown format."""
    if not table_data or len(table_data) < 2:  # Need at least header and one data row
        return ""
    
    # Calculate number of columns
    num_cols = max(len(row) for row in table_data)
    
    # Pad rows to have equal columns
    for row in table_data:
        while len(row) < num_cols:
            row.append("")
    
    # Build markdown table
    md_lines = []
    
    # Header
    md_lines.append("| " + " | ".join(table_data[0]) + " |")
    
    # Separator
    md_lines.append("| " + " | ".join(":---" for _ in range(num_cols)) + " |")
    
    # Data rows
    for row in table_data[1:]:
        md_lines.append("| " + " | ".join(row) + " |")
    
    return "\n".join(md_lines)


def process_line_blocks(blocks: List[TextBlock], link_map: dict) -> str:
    """Process a line of text blocks into Markdown."""
    line_parts = []
    for block in blocks:
        text = block.text.strip()
        if text:
            # Check if this is a link
            if text in link_map:
                line_parts.append(f"[{text}]({link_map[text]})")
            else:
                line_parts.append(text)
    
    return " ".join(line_parts)


def extract_images(pdf_path: str, output_dir: str) -> Result[List[Path], PDFProcessorError]:
    """Extract images (PNG) from the PDF.
    
    Args:
        pdf_path: The path to the PDF file to process.
        output_dir: The directory where extracted images will be saved.
        
    Returns:
        Result: Ok(List[Path]) with paths to extracted images if successful, Err otherwise
    """
    # Validate PDF file
    pdf_path_result = validate_pdf(pdf_path)
    if not pdf_path_result.is_ok:
        return Result.Err(pdf_path_result.error)

    try:
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Extract images using PyMuPDF
        doc = fitz.open(pdf_path)
        image_paths = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                # Get image data
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Save image
                image_path = output_path / f"page_{page_num + 1}_image_{img_index + 1}.png"
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)
                image_paths.append(image_path)
        
        doc.close()
        return Result.Ok(image_paths)
    except Exception as e:
        return Result.Err(PDFProcessorError(f"Failed to extract images: {str(e)}"))


def save_text(output_dir: str, file_name: str, content: str) -> Result[Path, FileError]:
    """Save content to a text file.
    
    Args:
        output_dir: The directory where the file will be saved.
        file_name: The name of the output file.
        content: The content to save.
        
    Returns:
        Result: Ok(Path) with path to saved file if successful, Err otherwise
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_path = output_path / file_name
        file_path.write_text(content, encoding="utf-8")
        
        return Result.Ok(file_path)
    except Exception as e:
        return Result.Err(FileError(f"Failed to save file: {str(e)}"))


def process_pdf(
    pdf_path: str,
    output_dir: str,
    extract_images_flag: bool = False,
    extract_text_flag: bool = False,
    extract_markdown_flag: bool = False,
    debug: bool = False
) -> Result[List[Path], PDFProcessorError]:
    """Process a PDF file and extract content based on flags.
    
    Args:
        pdf_path: Path to the PDF file to process
        output_dir: Directory to save extracted content
        extract_images_flag: Whether to extract images
        extract_text_flag: Whether to extract text
        extract_markdown_flag: Whether to convert to markdown
        debug: Whether to enable debug logging
    
    Returns:
        Result: Ok(List[Path]) with paths to output files if successful, Err otherwise
    """
    # Setup logging
    setup_logging(debug)
    
    # Validate input file
    pdf_result = validate_pdf(pdf_path)
    if not pdf_result.is_ok:
        return Result.Err(pdf_result.error)
    
    # Validate output directory
    try:
        output_path = Path(output_dir)
        if not output_path.exists():
            return Result.Err(FileError(output_dir, "Directory does not exist"))
        if not output_path.is_dir():
            return Result.Err(FileError(output_dir, "Not a directory"))
    except Exception as e:
        return Result.Err(FileError(output_dir, str(e)))
    
    output_files = []
    
    # Extract text
    if extract_text_flag:
        text_result = extract_text_with_metadata(pdf_path)
        if not text_result.is_ok:
            return Result.Err(text_result.error)
        
        text_path = output_path / "output.txt"
        save_result = save_text_to_file(text_result.value, text_path)
        if not save_result.is_ok:
            return Result.Err(save_result.error)
        output_files.append(text_path)
    
    # Extract images
    if extract_images_flag:
        images_result = extract_images(pdf_path, str(output_path))
        if not images_result.is_ok:
            return Result.Err(images_result.error)
        output_files.extend(images_result.value)
    
    # Convert to markdown
    if extract_markdown_flag:
        # Extract layout
        layout_result = extract_layout_with_pymupdf(pdf_path)
        if not layout_result.is_ok:
            return Result.Err(layout_result.error)
        
        # Extract hyperlinks
        links_result = extract_hyperlinks_with_pymupdf(pdf_path)
        if not links_result.is_ok:
            return Result.Err(links_result.error)
        
        # Convert to markdown
        markdown = layout_to_markdown(layout_result.value, links_result.value)
        
        # Save markdown
        markdown_path = output_path / "output.md"
        save_result = save_markdown_to_file(markdown, markdown_path)
        if not save_result.is_ok:
            return Result.Err(save_result.error)
        output_files.append(markdown_path)
    
    return Result.Ok(output_files)


def parse_args(args=None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Process PDF files to extract text, images, and convert to Markdown."
    )
    
    parser.add_argument(
        "pdf_path",
        help="Path to the PDF file to process"
    )
    
    parser.add_argument(
        "-i", "--images",
        action="store_true",
        help="Extract images from the PDF"
    )
    
    parser.add_argument(
        "-t", "--text",
        action="store_true",
        help="Extract text from the PDF"
    )
    
    parser.add_argument(
        "-m", "--markdown",
        action="store_true",
        help="Convert PDF to Markdown"
    )
    
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    return parser.parse_args(args)


def main() -> int:
    """Main CLI entry point for processing PDFs."""
    args = parse_args()
    
    # Process the PDF
    result = process_pdf(
        args.pdf_path,
        "output",
        args.images,
        args.text,
        args.markdown,
        args.debug
    )
    
    if result.is_ok:
        print("Successfully processed PDF:")
        for file_path in result.value:
            print(f"  - {file_path}")
        return 0
    else:
        print(f"Error: {result.error}")
        return 1


if __name__ == "__main__":
    exit(main())
