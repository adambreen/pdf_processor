"""Table processing module for PDF processor.

This module handles the detection, processing, and conversion of tables from PDFs to Markdown.

Design Decisions and Current Implementation:
------------------------------------------
1. Table Detection Strategy:
   - Primary: Border-based detection using geometric analysis of lines
   - Secondary: Alignment-based detection for borderless tables
   - Focus on simple grid-based tables with clear borders

2. Current Limitations:
   - Only detects tables with clear horizontal and vertical lines
   - No support for diagonal lines or complex borders
   - No handling of line opacity or color
   - Assumes consistent line width (close to 1 point)
   - May struggle with nested tables or complex layouts

3. Future Improvements:
   - Support for partially bordered tables
   - Line opacity and color consideration
   - Improved handling of nested structures
   - Support for diagonal lines and complex borders
   - Machine learning-based table detection

4. Testing Approach:
   - Test cases defined by sample PDF generation
   - Each new feature requires corresponding test PDF examples
   - Iterative improvement through test-driven development
"""

import logging
from typing import List, Tuple, Union, Optional
import fitz
from dataclasses import dataclass, field
from .text import TextBlock

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

@dataclass
class TableMetrics:
    """Metrics for table detection.
    
    These parameters define the geometric constraints for table detection.
    Values are calibrated based on common PDF layouts and current test cases.
    
    Current Focus:
    - Simple grid-based tables
    - Clear borders with consistent width
    - Standard cell sizes and spacing
    
    Future Considerations:
    - May need adjustment for complex layouts
    - Could be made configurable per document type
    - Might need per-page calibration
    """
    min_rows: int = 2
    min_cols: int = 2
    line_spacing_threshold: float = 15.0
    min_cell_width: float = 20.0
    min_cell_height: float = 10.0
    max_cell_width: float = 500.0
    max_cell_height: float = 100.0
    min_row_alignment: float = 0.8
    min_col_alignment: float = 0.8
    max_col_spacing: float = 50.0
    max_row_spacing: float = 20.0
    min_border_length: float = 10.0
    min_table_width: float = 50.0
    min_table_height: float = 20.0
    min_width: float = 50.0
    min_height: float = 20.0
    min_aspect_ratio: float = 0.5


@dataclass
class TableCell:
    """A cell in a table."""
    content: str
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    row_span: int = 1
    col_span: int = 1
    alignment: str = "left"
    is_header: bool = False
    formatting: List[str] = field(default_factory=list)


@dataclass
class Table:
    """A table with cells and metadata."""
    cells: List[List[TableCell]] = field(default_factory=list)
    has_header: bool = False
    x0: float = 0.0  # Left position
    y0: float = 0.0  # Top position
    x1: float = 0.0  # Right position
    y1: float = 0.0  # Bottom position

    def __post_init__(self):
        if not self.cells:
            self.cells = []


def detect_tables(pdf_path: Union[str, fitz.Document], metrics: TableMetrics) -> List[Table]:
    """Detect tables in a PDF document."""
    doc = None
    try:
        if isinstance(pdf_path, str):
            doc = fitz.open(pdf_path)
        else:
            doc = pdf_path
            
        tables = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # Try border detection first
            page_tables = detect_tables_from_borders(page, metrics)
            if not page_tables:
                # Fall back to alignment detection
                page_tables = detect_tables_from_alignment(page, metrics)
            tables.extend(page_tables)
        
        return merge_overlapping_tables(tables)
        
    finally:
        if isinstance(pdf_path, str) and doc:
            doc.close()


def detect_tables_from_borders(page: fitz.Page, metrics: TableMetrics) -> List[Table]:
    """Detect tables in a PDF using border lines."""
    try:
        horizontal_lines = []
        vertical_lines = []
        
        # Get all paths from the page
        paths = page.get_drawings()
        
        for path in paths:
            # Get the path's bounding rectangle
            x0, y0, x1, y1 = path["rect"]
            
            # Simple line detection based on geometry
            # Horizontal line: height is very small compared to width
            if abs(y1 - y0) <= 2 and abs(x1 - x0) >= metrics.min_border_length:
                horizontal_lines.append((min(x0, x1), y0, max(x0, x1), y1))
                
            # Vertical line: width is very small compared to height
            elif abs(x1 - x0) <= 2 and abs(y1 - y0) >= metrics.min_border_length:
                vertical_lines.append((x0, min(y0, y1), x1, max(y0, y1)))
        
        if not horizontal_lines or not vertical_lines:
            logger.debug("No valid grid lines found")
            return []
        
        # Find table bounds
        table = detect_table_from_lines(horizontal_lines, vertical_lines)
        if not table:
            logger.debug("Could not detect table bounds from lines")
            return []
        
        # Extract text within table bounds
        blocks = extract_text_blocks(page, table)
        if blocks:
            table.cells = convert_blocks_to_cells(blocks)
            if validate_table_cells(table, metrics):
                return [table]
            else:
                logger.debug("Table validation failed")
        else:
            logger.debug("No text blocks found within table bounds")
        
        return []
    except Exception as e:
        logger.exception("Error detecting tables from borders: %s", e)
        return []


def detect_tables_from_alignment(page: fitz.Page, metrics: TableMetrics) -> List[Table]:
    """Detect tables in a PDF using text alignment."""
    try:
        blocks = extract_text_blocks(page, None)  # Get all text blocks
        if not blocks:
            logger.debug("No text blocks found in page")
            return []
        
        # Sort blocks by vertical position
        blocks.sort(key=lambda b: (b.y0, b.x0))
        
        tables = []
        current_table = None
        
        for text_block in blocks:
            logger.debug("Processing block: %.30s...", text_block.text)
            if is_potential_table_row(text_block, metrics):
                logger.debug("  - Potential table row found")
                if current_table is None:
                    current_table = Table()
                    current_table.cells = []
                
                # Update table bounds
                if current_table.x0 == 0 or text_block.x0 < current_table.x0:
                    current_table.x0 = text_block.x0
                if current_table.y0 == 0 or text_block.y0 < current_table.y0:
                    current_table.y0 = text_block.y0
                current_table.x1 = max(current_table.x1, text_block.x1)
                current_table.y1 = max(current_table.y1, text_block.y1)
                
                # Add block to table
                add_block_to_table(current_table, text_block, metrics)
                logger.debug("  - Added block to table, now has %d rows", len(current_table.cells))
            elif current_table is not None:
                if validate_table(current_table, metrics):
                    logger.debug("  - Adding table with %d rows", len(current_table.cells))
                    tables.append(current_table)
                current_table = None
        
        # Add last table if valid
        if current_table is not None and validate_table(current_table, metrics):
            logger.debug("Adding final table with %d rows", len(current_table.cells))
            tables.append(current_table)
        
        return tables
    except Exception:
        logger.exception("Error in detect_tables_from_alignment")
        return []


def is_potential_table_row(block: TextBlock, metrics: TableMetrics) -> bool:
    """Check if a text block is likely part of a table row."""
    # Check if the text contains multiple whitespace-separated items
    text = block.text.strip()
    if not text:
        return False
        
    # Check for explicit table markers
    if "|" in text:
        return True
        
    # Check for consistent spacing that might indicate columns
    words = text.split()
    if len(words) < 2:
        return False
        
    # Check for numeric content which often appears in tables
    num_count = sum(1 for word in words if any(c.isdigit() for c in word))
    if num_count > 0 and num_count < len(words):
        return True
        
    # Check for consistent spacing between words
    spaces = [len(s) for s in text.split(words[0])[1:] if s.strip()]
    if spaces and all(abs(s - spaces[0]) <= 1 for s in spaces):
        return True
        
    return False


def add_block_to_table(table: Table, block: TextBlock, metrics: TableMetrics) -> None:
    """Add a text block to a table, processing it into cells."""
    text = block.text.strip()
    cells = []
    
    # Update table bounds
    table.x0 = min(table.x0, block.x0) if table.x0 else block.x0
    table.x1 = max(table.x1, block.x1) if table.x1 else block.x1
    table.y0 = min(table.y0, block.y0) if table.y0 else block.y0
    table.y1 = max(table.y1, block.y1) if table.y1 else block.y1
    
    # Split into cells if delimiter present
    if "|" in text:
        raw_cells = text.split("|")
        for cell_text in raw_cells:
            if cell_text.strip():
                cells.append(TableCell(
                    content=cell_text.strip(),
                    x0=block.x0,
                    x1=block.x1,
                    y0=block.y0,
                    y1=block.y1
                ))
    else:
        # Try to split based on spacing
        words = text.split()
        if len(words) >= metrics.min_cols:
            # Calculate word positions for alignment
            positions = []
            current_pos = 0
            for word in words:
                positions.append(current_pos)
                current_pos += len(word) + 1
            
            # Create cells
            for word, pos in zip(words, positions):
                cells.append(TableCell(
                    content=word,
                    x0=block.x0 + (pos / current_pos) * (block.x1 - block.x0),
                    x1=block.x0 + ((pos + len(word)) / current_pos) * (block.x1 - block.x0),
                    y0=block.y0,
                    y1=block.y1
                ))
    
    if cells:
        table.cells.append(cells)


def merge_overlapping_tables(tables: List[Table]) -> List[Table]:
    """Merge tables that overlap significantly."""
    if not tables:
        return []

    # Sort tables by y position
    tables = sorted(tables, key=lambda t: (t.y0, t.x0))
    
    # Merge overlapping tables
    merged = []
    current = tables[0]
    
    for next_table in tables[1:]:
        # Check if tables overlap
        if (current.y1 >= next_table.y0 and
            current.x1 >= next_table.x0 and
            current.x0 <= next_table.x1):
            # Merge tables
            current.x0 = min(current.x0, next_table.x0)
            current.y0 = min(current.y0, next_table.y0)
            current.x1 = max(current.x1, next_table.x1)
            current.y1 = max(current.y1, next_table.y1)
            if current.cells and next_table.cells:
                current.cells.extend(next_table.cells)
        else:
            merged.append(current)
            current = next_table
    
    merged.append(current)
    return merged


def validate_table(table: Table, metrics: TableMetrics) -> bool:
    """Validate that a table meets the minimum size requirements."""
    width = table.x1 - table.x0
    height = table.y1 - table.y0
    
    logger.debug("Validating table: width=%.2f, height=%.2f", width, height)
    
    # Check minimum size requirements
    if width < metrics.min_width or height < metrics.min_height:
        logger.debug("Table failed minimum size check: min_width=%.1f, min_height=%.1f",
                    metrics.min_width, metrics.min_height)
        return False
    
    if not validate_table_cells(table, metrics):
        logger.debug("Table failed cell validation")
        return False
    
    return True


def validate_table_cells(table: Table, metrics: TableMetrics) -> bool:
    """Validate that a table has the required number of cells."""
    if not table.cells:
        logger.debug("No cells found in table")
        return False
    
    # Check minimum number of rows and columns
    if len(table.cells) < 2:  # At least header and one data row
        logger.debug("Not enough rows: %d < 2", len(table.cells))
        return False
    
    if any(len(row) < 2 for row in table.cells):  # At least 2 columns
        logger.debug("Some rows have less than 2 columns")
        return False
    
    # Check for consistent number of columns
    num_cols = len(table.cells[0])
    if any(len(row) != num_cols for row in table.cells[1:]):
        logger.debug("Inconsistent number of columns. Expected %d", num_cols)
        return False
    
    return True


def detect_table_from_lines(horizontal_lines: List[Tuple[float, float, float, float]], 
                          vertical_lines: List[Tuple[float, float, float, float]]) -> Optional[Table]:
    """Detect a table from a set of horizontal and vertical lines."""
    if not horizontal_lines or not vertical_lines:
        return None

    # Find table bounds
    x0 = min(min(l[0], l[2]) for l in vertical_lines)
    y0 = min(min(l[1], l[3]) for l in horizontal_lines)
    x1 = max(max(l[0], l[2]) for l in vertical_lines)
    y1 = max(max(l[1], l[3]) for l in horizontal_lines)

    # Create table
    table = Table()
    table.x0 = x0
    table.y0 = y0
    table.x1 = x1
    table.y1 = y1

    return table


def extract_text_blocks(page: fitz.Page, table: Optional[Table] = None) -> List[TextBlock]:
    """Extract text blocks within table bounds."""
    try:
        blocks = []
        # Use PyMuPDF's text extraction with dict mode
        page_blocks = page.get_text("dict")["blocks"]
        logger.debug("Found %d raw blocks in page", len(page_blocks))
        
        for block in page_blocks:
            if block.get("type") != 0:  # Not a text block
                continue
            
            # Extract block coordinates
            x0 = block["bbox"][0]
            y0 = block["bbox"][1]
            x1 = block["bbox"][2]
            y1 = block["bbox"][3]
            
            # Check if block is within table bounds
            if table:
                if not (x0 >= table.x0 - 2 and x1 <= table.x1 + 2 and
                       y0 >= table.y0 - 2 and y1 <= table.y1 + 2):
                    logger.debug("Block outside table bounds: (%.2f, %.2f, %.2f, %.2f) vs table (%.2f, %.2f, %.2f, %.2f)",
                               x0, y0, x1, y1, table.x0, table.y0, table.x1, table.y1)
                    continue
                else:
                    logger.debug("Block inside table bounds: (%.2f, %.2f, %.2f, %.2f)", x0, y0, x1, y1)
            
            # Process lines within block
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    
                    text_block = TextBlock(
                        text=text,
                        x0=span["bbox"][0],
                        y0=span["bbox"][1],
                        x1=span["bbox"][2],
                        y1=span["bbox"][3],
                        font=span.get("font", ""),
                        font_size=span.get("size", 0)
                    )
                    blocks.append(text_block)
                    logger.debug("Added text block: '%s' at (%.2f, %.2f, %.2f, %.2f)", text, text_block.x0, text_block.y0, text_block.x1, text_block.y1)
        
        logger.debug("Found %d text blocks", len(blocks))
        return blocks
    except Exception as e:
        logger.exception("Error extracting text blocks: %s", e)
        return []


def convert_blocks_to_cells(blocks: List[TextBlock]) -> List[List[TableCell]]:
    """Convert text blocks to table cells."""
    if not blocks:
        return []
    
    # Sort blocks by y-coordinate first
    blocks = sorted(blocks, key=lambda b: b.y0)
    
    # Group blocks into rows based on y-coordinate
    rows = []
    current_row = []
    current_y = blocks[0].y0
    
    for block in blocks:
        # If block is on a new line (with some tolerance)
        if abs(block.y0 - current_y) > 5:
            if current_row:
                # Sort blocks in row by x-coordinate
                current_row.sort(key=lambda b: b.x0)
                rows.append(current_row)
            current_row = []
            current_y = block.y0
        current_row.append(block)
    
    if current_row:
        current_row.sort(key=lambda b: b.x0)
        rows.append(current_row)
    
    # Determine column boundaries
    all_x_coords = []
    for row in rows:
        for block in row:
            all_x_coords.append(block.x0)
            all_x_coords.append(block.x1)
    
    # Find column boundaries using x-coordinates
    x_coords = sorted(set(all_x_coords))
    column_bounds = []
    for i in range(len(x_coords) - 1):
        mid = (x_coords[i] + x_coords[i + 1]) / 2
        column_bounds.append(mid)
    
    # Convert rows of blocks to rows of cells
    cells = []
    for row_blocks in rows:
        row_cells = []
        current_col = 0
        
        for block in row_blocks:
            # Find which column this block belongs to
            while current_col < len(column_bounds) and block.x0 > column_bounds[current_col]:
                # Add empty cells for any skipped columns
                row_cells.append(TableCell(""))
                current_col += 1
            
            cell = TableCell(
                content=block.text,
                is_header=block.font.endswith("-Bold"),
                alignment="center" if block.font_size > 12 else "left"
            )
            row_cells.append(cell)
            current_col += 1
        
        # Fill any remaining columns with empty cells
        while current_col < len(column_bounds) + 1:
            row_cells.append(TableCell(""))
            current_col += 1
        
        cells.append(row_cells)
    
    return cells


def table_to_markdown(table: Table) -> str:
    """Convert a table to markdown format."""
    if not table.cells:
        return ""
    
    def format_row(cells):
        """Format a row of cells into markdown, handling empty cells correctly."""
        formatted = []
        for cell in cells:
            text = cell.content.strip() if cell.content else ""
            if cell.col_span > 1:
                formatted.append(text)
                formatted.extend([""] * (cell.col_span - 1))
            else:
                formatted.append(text)
        # Join cells with exactly one space between the |'s for empty cells
        parts = []
        for cell in formatted:
            if cell:
                parts.append(f" {cell} ")
            else:
                parts.append(" ")
        return "|" + "|".join(parts) + "|"
    
    # Build markdown rows
    rows = []
    
    # Handle header row
    header_row = format_row(table.cells[0])
    rows.append(header_row)
    
    # Add alignment row
    alignments = []
    for cell in table.cells[0]:
        if cell.alignment == "center":
            alignments.append(":---:")
        elif cell.alignment == "right":
            alignments.append("---:")
        else:
            alignments.append(":---")
        # Handle colspan
        if cell.col_span > 1:
            alignments.extend([":---"] * (cell.col_span - 1))
    rows.append("| " + " | ".join(alignments) + " |")
    
    # Add data rows
    for row in table.cells[1:]:
        rows.append(format_row(row))
    
    return "\n".join(rows)


def format_cell(cell: TableCell, is_header: bool = False) -> str:
    """Format cell content with proper formatting."""
    content = cell.content.strip()
    if not content:
        return ""
    
    # Apply formatting if specified
    if cell.formatting:
        for fmt in cell.formatting:
            if fmt == "bold":
                content = f"**{content}**"
            elif fmt == "italic":
                content = f"*{content}*"
            elif fmt == "code":
                content = f"`{content}`"
    
    return content
