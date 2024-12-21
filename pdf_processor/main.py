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
    FileError,
)
from .text import (
    TextBlock,
    extract_text_with_metadata,
    extract_hyperlinks_with_pymupdf,
    extract_layout_with_pymupdf,
    save_text_to_file,
    save_markdown_to_file,
    validate_pdf,
    check_dependencies,
)
from .table import detect_tables, TableMetrics

__all__ = ["process_pdf", "parse_args"]


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if debug else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)

    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("fitz").setLevel(logging.WARNING)


def layout_to_markdown(
    layout: List[TextBlock], links: List[Tuple[str, str]] = None
) -> str:
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
        if (
            not in_table
            and len(words) >= 2
            and all(len(word.split()) == 1 for word in words)
        ):
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


def extract_images(
    pdf_path: str, output_dir: str
) -> Result[List[Path], PDFProcessorError]:
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

        # Save each page as PNG image
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap()
            image_path = output_path / f"{Path(pdf_path).stem}_page_{page_num + 1}.png"
            pix.save(str(image_path))
            image_paths.append(image_path)

        doc.close()
        return Result.Ok(image_paths)
    except Exception as e:
        return Result.Err(PDFProcessorError(f"Failed to extract images: {str(e)})"))


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
    input_dir: str,
    input_pattern: str,
    output_dir: Optional[str] = None,
    extract_images_flag: bool = False,
    extract_text_flag: bool = False,
    extract_markdown_flag: bool = False,
    debug: bool = False,
) -> Result[List[Path], PDFProcessorError]:
    """Process multiple PDF files with comprehensive error handling.

    This function processes PDF files found in the input directory that match
    the specified pattern. For each PDF, it creates a dedicated output directory
    and generates the requested output formats.

    Directory Structure:
        input_dir/
            file1.pdf
            file2.pdf
        output_dir/
            file1/
                file1.txt       (if extract_text)
                file1.md        (if extract_markdown)
                file1_page_1.png (if extract_images)
                file1_page_2.png
            file2/
                file2.txt
                file2.md
                file2_page_1.png
                ...

    Error Handling:
        - Individual file failures don't stop the entire process
        - Errors are collected and reported at the end
        - Process succeeds if at least one file is processed
        - All errors are logged for debugging

    Args:
        input_dir: Directory containing PDF files to process
        input_pattern: Glob pattern to match PDF files (e.g., "*.pdf", "report*.pdf")
        output_dir: Directory for output files (default: same as input_dir)
        extract_images_flag: Extract each page as a PNG image
        extract_text_flag: Extract raw text content
        extract_markdown_flag: Convert to Markdown with tables and links
        debug: Enable detailed debug logging

    Returns:
        Result: On success, Ok(List[Path]) containing all output file paths
               On failure, Err(PDFProcessorError) with error details
    """
    setup_logging(debug)
    logger = logging.getLogger(__name__)

    # Validate and resolve input directory
    try:
        input_path = Path(input_dir).resolve()
        if not input_path.is_dir():
            return Result.Err(FileError(str(input_path), "Not a directory"))
        logger.debug(f"Input directory resolved to: {input_path}")
    except Exception as e:
        return Result.Err(FileError(input_dir, f"Invalid input directory: {str(e)}"))

    # Resolve output directory (default to input directory if not specified)
    output_path = Path(output_dir).resolve() if output_dir else input_path
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Output directory resolved to: {output_path}")
    except Exception as e:
        return Result.Err(FileError(str(output_path), f"Failed to create output directory: {str(e)}"))

    # Find matching PDF files
    try:
        pdf_files = list(input_path.glob(input_pattern))
        if not pdf_files:
            return Result.Err(FileError(str(input_path), f"No files matching pattern: {input_pattern}"))
        logger.debug(f"Found {len(pdf_files)} PDF files matching pattern: {input_pattern}")
    except Exception as e:
        return Result.Err(FileError(str(input_path), f"Error finding PDF files: {str(e)}"))

    all_output_files = []
    errors = []

    # Process each PDF file
    for pdf_file in pdf_files:
        logger.info(f"Processing {pdf_file.name}...")

        # Validate PDF
        pdf_result = validate_pdf(str(pdf_file))
        if not pdf_result.is_ok:
            error_msg = f"Skipping {pdf_file.name}: {pdf_result.error}"
            logger.warning(error_msg)
            errors.append(error_msg)
            continue

        # Create file-specific output directory
        file_output_dir = output_path / pdf_file.stem
        try:
            file_output_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created output directory for {pdf_file.name}: {file_output_dir}")
        except Exception as e:
            error_msg = f"Skipping {pdf_file.name}: Failed to create output directory: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            continue

        # Extract text
        if extract_text_flag:
            logger.debug(f"Extracting text from {pdf_file.name}")
            text_result = extract_text_with_metadata(str(pdf_file))
            if not text_result.is_ok:
                error_msg = f"Failed to extract text from {pdf_file.name}: {text_result.error}"
                logger.error(error_msg)
                errors.append(error_msg)
            else:
                text_path = file_output_dir / f"{pdf_file.stem}.txt"
                save_result = save_text_to_file(text_result.value, text_path)
                if not save_result.is_ok:
                    error_msg = f"Failed to save text from {pdf_file.name}: {save_result.error}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                else:
                    logger.info(f"Saved text to {text_path}")
                    all_output_files.append(text_path)

        # Extract images
        if extract_images_flag:
            logger.debug(f"Extracting images from {pdf_file.name}")
            images_result = extract_images(str(pdf_file), str(file_output_dir))
            if not images_result.is_ok:
                error_msg = f"Failed to extract images from {pdf_file.name}: {images_result.error}"
                logger.error(error_msg)
                errors.append(error_msg)
            else:
                logger.info(f"Extracted {len(images_result.value)} images from {pdf_file.name}")
                all_output_files.extend(images_result.value)

        # Convert to markdown
        if extract_markdown_flag:
            logger.debug(f"Converting {pdf_file.name} to Markdown")
            
            # Extract layout
            layout_result = extract_layout_with_pymupdf(str(pdf_file))
            if not layout_result.is_ok:
                error_msg = f"Failed to extract layout from {pdf_file.name}: {layout_result.error}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            # Extract hyperlinks
            links_result = extract_hyperlinks_with_pymupdf(str(pdf_file))
            if not links_result.is_ok:
                error_msg = f"Failed to extract hyperlinks from {pdf_file.name}: {links_result.error}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            # Convert to markdown
            markdown = layout_to_markdown(layout_result.value, links_result.value)

            # Save markdown
            markdown_path = file_output_dir / f"{pdf_file.stem}.md"
            save_result = save_markdown_to_file(markdown, markdown_path)
            if not save_result.is_ok:
                error_msg = f"Failed to save markdown from {pdf_file.name}: {save_result.error}"
                logger.error(error_msg)
                errors.append(error_msg)
            else:
                logger.info(f"Saved Markdown to {markdown_path}")
                all_output_files.append(markdown_path)

    # Summarize results
    if all_output_files:
        logger.info(f"Successfully processed {len(pdf_files)} PDF files")
        if errors:
            logger.warning("Completed with errors:\n%s", "\n".join(errors))
        return Result.Ok(all_output_files)
    else:
        error_msg = "No files were successfully processed:\n" + "\n".join(errors)
        logger.error(error_msg)
        return Result.Err(PDFProcessorError(error_msg))


def post_install_message():
    """Display a helpful message after package installation.
    
    This function is called automatically by pipx/poetry after installation.
    It is registered as an entry point in pyproject.toml.
    """
    print("""
Thank you for installing pdf_processor!

To ensure everything works correctly, please verify these requirements:

1. Python Version
   - Required: Python 3.11.x (needed by PyMuPDF)
   - Check with: python --version
   - If needed, reinstall with: pipx install pdf_processor --python python3.11

2. System Dependencies
   - Required: mutool (part of MuPDF tools)
   - Check with: pdf-process --check-dependencies
   - Install with:
     * macOS:     brew install mupdf
     * Ubuntu:    apt-get install mupdf-tools
     * Arch:      pacman -S mupdf-tools

3. Verify Installation
   Run this command to check if everything is set up correctly:
       pdf-process --check-dependencies

For usage instructions and examples, run:
    pdf-process --help
""")


def check_dependencies() -> bool:
    """Check if required system dependencies are installed.
    
    Returns:
        bool: True if all dependencies are installed, False otherwise
    """
    # Check mutool
    import logging
    logger = logging.getLogger(__name__)
    
    from . import text
    deps_result = text.check_dependencies()
    if not deps_result.is_ok:
        logger.error("Dependency check failed: %s", deps_result.error)
        return False
        
    logger.info("All dependencies are installed and working correctly.")
    return True


def parse_args(args=None) -> argparse.Namespace:
    """Parse and validate command-line arguments for PDF processing.

    This function sets up a comprehensive command-line interface that supports:
    1. Directory-based processing with glob patterns
    2. Multiple output formats (text, markdown, images)
    3. Custom input/output directory specification
    4. Debug logging

    The interface is designed to be both powerful and user-friendly, with:
    - Detailed help text and examples
    - Sensible defaults for all options
    - Clear error messages
    - Support for batch processing

    Command-line Format:
        pdf-process [-h] [-dir DIR] [-input PATTERN] [-output DIR]
                   [--extract-images] [--extract-text] [--extract-markdown]
                   [--check-dependencies] [-d]

    Examples:
        Process all PDFs in current directory:
            pdf-process --extract-text

        Process specific PDFs with pattern matching:
            pdf-process -dir /docs -input "report*.pdf" --extract-markdown

        Extract everything from PDFs in a directory:
            pdf-process -dir /pdfs -output /processed --extract-images --extract-text --extract-markdown

        Check dependencies:
            pdf-process --check-dependencies

    Args:
        args: List of command-line arguments (default: sys.argv[1:])

    Returns:
        argparse.Namespace with the following attributes:
        - dir (str): Directory containing PDF files
        - input (str): File pattern to match PDFs
        - output (str, optional): Output directory path
        - extract_images (bool): Extract page images flag
        - extract_text (bool): Extract raw text flag
        - extract_markdown (bool): Convert to Markdown flag
        - check_dependencies (bool): Check if required dependencies are installed
        - debug (bool): Enable debug logging flag
    """
    parser = argparse.ArgumentParser(
        description=(
            "PDF Processor: Extract and convert PDF content with multiple output formats\n\n"
            "A Python package to process PDFs using both mutool and PyMuPDF:\n"
            "- Extract raw text using mutool\n"
            "- Convert pages to PNG images\n"
            "- Generate Markdown with table detection using PyMuPDF\n"
            "- Preserve text layout and hyperlinks\n\n"
            "Key Features:\n"
            "- Image Extraction: Converts each page to PNG images using mutool\n"
            "- Plain Text Extraction: Extracts raw text using mutool\n"
            "- Markdown Generation: Converts PDFs to GitHub-Flavored Markdown with:\n"
            "  * Table detection and formatting\n"
            "  * Hyperlink preservation\n"
            "  * Layout analysis using PyMuPDF"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Process multiple PDFs:\n"
            "    %(prog)s -dir /path/to/pdfs -input '*.pdf' -output /path/to/output --extract-images --extract-markdown\n\n"
            "  Extract everything from a single PDF:\n"
            "    %(prog)s -dir . -input sample.pdf --extract-images --extract-text --extract-markdown\n\n"
            "  Convert to Markdown with tables:\n"
            "    %(prog)s -dir . -input report.pdf --extract-markdown\n\n"
            "  Extract just the text:\n"
            "    %(prog)s -dir . -input document.pdf --extract-text\n\n"
            "  Check dependencies:\n"
            "    %(prog)s --check-dependencies\n\n"
            "Output Structure:\n"
            "  For each processed PDF, a directory is created with the PDF's name containing:\n"
            "  - Text: <pdfname>.txt\n"
            "  - Markdown: <pdfname>.md\n"
            "  - Images: <pdfname>_page_N.png\n\n"
            "Note: Requires mutool to be installed (brew install mupdf on macOS)"
        )
    )
    
    parser.add_argument(
        "-dir",
        default=".",
        help="Directory containing PDF files (default: current directory)"
    )
    
    parser.add_argument(
        "-input",
        default="*.pdf",
        help="File pattern to match PDFs (e.g., '*.pdf', 'report*.pdf')"
    )
    
    parser.add_argument(
        "-output",
        help="Directory where output files will be saved (default: same as input directory)"
    )
    
    parser.add_argument(
        "--extract-images",
        action="store_true",
        help="Extract each page of the PDF as PNG images"
    )
    
    parser.add_argument(
        "--extract-text",
        action="store_true",
        help="Extract the raw plain text from the PDF"
    )
    
    parser.add_argument(
        "--extract-markdown",
        action="store_true",
        help="Extract structured Markdown, including tables and hyperlinks"
    )
    
    parser.add_argument(
        "--check-dependencies",
        action="store_true",
        help="Check if required dependencies are installed"
    )
    
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable detailed debug logging"
    )
    
    return parser.parse_args(args)


def main() -> int:
    """Main CLI entry point for processing PDFs."""
    args = parse_args()
    
    # Configure logging
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)
    
    # Check dependencies if requested
    if args.check_dependencies:
        if check_dependencies():
            logger.info("All dependencies are installed correctly.")
            return 0
        return 1
    
    # Check if any extraction flags are set
    if not (args.extract_images or args.extract_text or args.extract_markdown):
        logger.error("No extraction flags specified. Use --extract-images, --extract-text, or --extract-markdown")
        return 1
    
    # Check dependencies before processing
    if not check_dependencies():
        return 1

    # Process the PDF
    result = process_pdf(
        args.dir, args.input, args.output,
        args.extract_images, args.extract_text, args.extract_markdown,
        args.debug
    )

    if not result.is_ok:
        logger.error(str(result.error))
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
