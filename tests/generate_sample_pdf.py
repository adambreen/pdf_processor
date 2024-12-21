"""Generate sample PDF for testing table processing features.

This module creates a comprehensive test PDF that serves as the foundation for
table detection testing. Each table in this file represents a specific test case
and is used to validate different aspects of the table detection algorithm.

Test Case Design:
----------------
1. Basic Table Features:
   - Simple tables with headers and borders
   - Column and row spans
   - Different text alignments
   - Various background colors
   - Different border styles

2. Current Test Cases:
   Table 1: Simple Table with Header
   - Tests basic grid detection
   - Tests header row recognition
   - Uses standard black borders

   Table 2: Column Spans
   - Tests handling of merged columns
   - Tests complex header structures

   Table 3: Row Spans
   - Tests handling of merged rows
   - Tests vertical cell merging

   Table 4: Different Alignments
   - Tests text alignment detection
   - Tests mixed alignment handling

   Table 5: No Borders
   - Tests alignment-based detection
   - Validates borderless table handling

   Table 6: Mixed Formatting
   - Tests rich text in cells
   - Tests complex cell content

3. Adding New Test Cases:
   - Add new table definitions following the existing pattern
   - Use ReportLab's TableStyle for consistent styling
   - Document the purpose of each new test case
   - Regenerate sample.pdf after changes
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch


def generate_sample_pdf(output_path: Path = None) -> Path:
    """Generate a sample PDF with various table formats for testing.
    
    Args:
        output_path: Optional custom output path. If not provided, 
                    will save to tests/sample.pdf
    
    Returns:
        Path: Path to the generated PDF file
    """
    # Define output file path
    if output_path is None:
        output_path = Path(__file__).parent / "sample.pdf"
    
    # Create document
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)

    # Sample content
    styles = getSampleStyleSheet()
    elements = []

    # Custom styles
    styles.add(ParagraphStyle(
        name='Caption',
        parent=styles['BodyText'],
        fontSize=10,
        leading=12,
        textColor=colors.grey
    ))

    # Add a heading
    heading = Paragraph("Sample PDF for Testing", styles["Heading1"])
    elements.append(heading)

    # Add a paragraph with different text styles
    paragraph = Paragraph(
        "This is a sample paragraph for testing text extraction. It contains "
        "<b>bold text</b>, <i>italic text</i>, and <b><i>bold italic text</i></b>. "
        "Below, you'll find various table examples and a hyperlink.",
        styles["BodyText"]
    )
    elements.append(paragraph)
    elements.append(Spacer(1, 0.2 * inch))

    # 1. Simple table with header
    elements.append(Paragraph("1. Simple Table with Header", styles["Heading2"]))
    elements.append(Paragraph("A basic table with header row.", styles["Caption"]))
    data = [
        ["Name", "Age", "Location"],
        ["Alice", "30", "New York"],
        ["Bob", "25", "London"],
        ["Charlie", "35", "Paris"]
    ]
    table = Table(data)
    table.setStyle(TableStyle([
        # Header style
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        # Body style
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3 * inch))

    # 2. Table with column spans
    elements.append(Paragraph("2. Table with Column Spans", styles["Heading2"]))
    elements.append(Paragraph("This table demonstrates column spanning.", styles["Caption"]))
    data = [
        ["Product Information", "", ""],  # Empty strings for spanned columns
        ["Name", "Category", "Price"],
        ["Widget", "Electronics", "$10.00"],
        ["Gadget", "Electronics", "$20.00"],
    ]
    t = Table(data)
    t.setStyle(TableStyle([
        # Header style
        ("BACKGROUND", (0, 0), (-1, 0), colors.blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("SPAN", (0, 0), (2, 0)),  # Span first row across all columns
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        # Body style
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # 3. Table with row spans
    elements.append(Paragraph("3. Table with Row Spans", styles["Heading2"]))
    elements.append(Paragraph("This table demonstrates row spanning.", styles["Caption"]))
    data = [
        ["Category", "Item", "Price"],
        ["Electronics", "Laptop", "$1000"],
        ["", "Mouse", "$25"],  # Empty for row span
        ["", "Keyboard", "$50"],  # Empty for row span
        ["Furniture", "Desk", "$200"],
        ["", "Chair", "$100"],  # Empty for row span
    ]
    t = Table(data)
    t.setStyle(TableStyle([
        # Header style
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkgreen),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        # Row spans
        ("SPAN", (0, 1), (0, 3)),  # Span "Electronics" down 3 rows
        ("SPAN", (0, 4), (0, 5)),  # Span "Furniture" down 2 rows
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # 4. Table with different alignments
    elements.append(Paragraph("4. Table with Different Alignments", styles["Heading2"]))
    elements.append(Paragraph("This table demonstrates different text alignments.", styles["Caption"]))
    data = [
        ["Left", "Center", "Right"],
        ["This is left-aligned", "This is centered", "This is right-aligned"],
        ["Short", "Medium text", "Longer text here"],
    ]
    t = Table(data)
    t.setStyle(TableStyle([
        # Header style
        ("BACKGROUND", (0, 0), (-1, 0), colors.purple),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        # Alignments
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # 5. Table with no borders
    elements.append(Paragraph("5. Table without Borders", styles["Heading2"]))
    elements.append(Paragraph("This table has no visible borders, testing alignment-based detection.", styles["Caption"]))
    data = [
        ["Column 1", "Column 2", "Column 3"],
        ["Data 1", "Data 2", "Data 3"],
        ["More 1", "More 2", "More 3"],
    ]
    t = Table(data, colWidths=[2*inch, 2*inch, 2*inch])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # 6. Table with mixed formatting
    elements.append(Paragraph("6. Table with Mixed Formatting", styles["Heading2"]))
    elements.append(Paragraph("This table includes various text formatting.", styles["Caption"]))
    data = [
        ["Style", "Example", "Notes"],
        [Paragraph("<b>Bold</b>", styles["BodyText"]), 
         Paragraph("Regular", styles["BodyText"]),
         Paragraph("<i>Italic notes</i>", styles["BodyText"])],
        [Paragraph("<i>Italic</i>", styles["BodyText"]),
         Paragraph("<b>Bold text</b>", styles["BodyText"]),
         Paragraph("Normal", styles["BodyText"])],
    ]
    t = Table(data)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.red),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # Add a hyperlink for testing link extraction
    hyperlink = Paragraph(
        '<a href="http://example.com" color="blue">Click here to visit example.com</a>',
        styles["BodyText"]
    )
    elements.append(hyperlink)

    # Build the document
    doc.build(elements)
    print(f"Sample PDF saved to {output_path}")
    return output_path


def main():
    """Generate sample PDF in the tests directory."""
    output_path = Path(__file__).parent / "sample.pdf"
    generate_sample_pdf(output_path)


if __name__ == "__main__":
    main()
