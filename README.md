# PDF Processor

A Python package to batch process PDFs into PNGs or extract text from PDFs using mutool and PyMuPDF, with advanced Markdown formatting and table detection.

---

## Purpose and Design Decisions

### Purpose
The goal of this tool is to make PDF content **machine-readable** for downstream processing, such as for Large Language Models (LLMs), using structured formats like **Markdown** and **plain text**, while supporting table and hyperlink extraction.

### Key Features
- **Image Extraction**: Converts each page of a PDF to PNG images using `mutool`.
- **Plain Text Extraction**: Extracts raw text from PDFs using `mutool`.
- **Markdown Generation**: Converts PDFs to Markdown, using:
  - **PyMuPDF (`fitz`)** for text layout analysis and hyperlink detection.
  - Table detection and conversion.
  - Hyperlink embedding.
  - GitHub-Flavored Markdown (GFM).

---

## Installation

### Production Installation
Install globally using pipx:
```bash
pipx install pdf_processor
```

### Development Installation
To install the package for development:
```bash
poetry install --with dev
```

---

## Requirements

This tool relies on:
- **`mutool`**: Part of the MuPDF tools suite, used for image extraction and plain text processing.
- **`PyMuPDF` (`fitz`)**: Python bindings for MuPDF, used for advanced text layout analysis, hyperlink detection, and Markdown generation.
- **`reportlab`**: Used for generating sample PDFs for testing purposes.

### Install Dependencies
Install `mutool` on macOS:
```bash
brew install mupdf
```

Verify installation:
```bash
mutool --version
```

Install Python dependencies:
```bash
pip install pymupdf pytest reportlab
```

---

## Project Structure

```
pdf_processor/
├── pdf_processor/
│   ├── __init__.py
│   ├── main.py
├── tests/
│   ├── tests.py
│   ├── sample.pdf
│   ├── generate_sample_pdf.py
├── README.md
├── pyproject.toml
```

### Key Components
- **`pdf_processor/`**:
  - Contains the core package logic, including text, Markdown, and image extraction.
- **`tests/`**:
  - `tests.py`: Includes unit tests for all major features.
  - `generate_sample_pdf.py`: Generates the `sample.pdf` used for testing.
  - `sample.pdf`: A simple PDF file with text, tables, and hyperlinks for test cases.

---

## Usage

### CLI Command
Use the `pdf-process` command to process PDF files. The command supports extracting images, plain text, or Markdown.

```bash
pdf-process -dir /path/to/pdfs -input '*.pdf' -output /path/to/output --extract-images --extract-markdown
```

### Arguments
- `-dir`: Directory containing PDF files (default: current directory).
- `-input`: File pattern to match PDFs (default: `*.pdf`).
- `-output`: Directory where output files will be saved (default: same as input).
- `--extract-images`: Extract each page of the PDF as PNG images.
- `--extract-text`: Extract the raw plain text from the PDF.
- `--extract-markdown`: Extract structured Markdown, including tables and hyperlinks.

---

## Markdown Features

### Table Detection
- Uses text alignment and vertical spacing to group text blocks into tables.
- Outputs Markdown tables in GitHub-Flavored Markdown format.

#### Example Input (PDF Table):
```
Name    Age    Location
John    29     New York
Alice   34     London
```

#### Markdown Output:
```markdown
| Name  | Age | Location  |
|-------|-----|-----------|
| John  | 29  | New York  |
| Alice | 34  | London    |
```

### Hyperlink Embedding
- Detects hyperlinks and embeds them directly into the Markdown.

#### Example Input (PDF Hyperlink):
```
Visit [GitHub](https://github.com) for more information.
```

#### Markdown Output:
```markdown
Visit [GitHub](https://github.com) for more information.
```

### Headings and Lists
- Converts large, bold text into Markdown headings (`#`, `##`, etc.).
- Converts bullet points into Markdown lists.

---

## Table Detection

### Current Implementation
The PDF processor includes a sophisticated table detection system that uses a two-pronged approach:

1. **Border-Based Detection (Primary Method)**
   - Analyzes geometric properties of lines in the PDF
   - Identifies grid patterns formed by horizontal and vertical lines
   - Works best with clearly bordered tables
   - Currently optimized for simple grid-based layouts

2. **Alignment-Based Detection (Fallback Method)**
   - Used when borders are not present
   - Analyzes text block alignment and spacing
   - Identifies table-like structures from text positioning

### Current Limitations
- Only detects tables with clear horizontal and vertical lines
- No support for diagonal lines or complex borders
- No handling of line opacity or color
- Assumes consistent line width (close to 1 point)
- May struggle with nested tables or complex layouts

### Development Process
The table detection system follows a test-driven development approach:

1. **Test PDF Generation**
   - All test cases are defined in `tests/generate_sample_pdf.py`
   - Each table type has a specific test case in the sample PDF
   - New features require corresponding examples in this file

2. **Test Implementation**
   - Test cases in `tests/test_pdf_processor.py` validate detection
   - Each feature has both positive and negative test cases
   - Edge cases and error conditions are explicitly tested

3. **Feature Addition Process**
   a. Add new table example to `generate_sample_pdf.py`
   b. Generate new test PDF
   c. Add corresponding test cases
   d. Implement detection improvements
   e. Document changes and limitations

4. **Future Improvements**
   - Support for partially bordered tables
   - Line opacity and color consideration
   - Improved handling of nested structures
   - Support for diagonal lines and complex borders
   - Machine learning-based table detection

---

## Testing

### Running Tests
Run the test suite with pytest:
```bash
pytest tests/
```

### Generating the Sample PDF
If `sample.pdf` is missing or needs regeneration, run:
```bash
python tests/generate_sample_pdf.py
```
This will create a `sample.pdf` in the `tests/` directory.

---

## Examples

### Extract Images from PDFs
To extract images from all matching PDFs:
```bash
pdf-process -dir /path/to/pdfs -input '*.pdf' -output /path/to/output --extract-images
```

### Extract Plain Text from PDFs
To extract plain text from all matching PDFs:
```bash
pdf-process -dir /path/to/pdfs -input '*.pdf' -output /path/to/output --extract-text
```

### Extract Markdown from PDFs
To extract structured Markdown from all matching PDFs:
```bash
pdf-process -dir /path/to/pdfs -input '*.pdf' -output /path/to/output --extract-markdown
```

### Combine Options
To extract both images and Markdown from PDFs:
```bash
pdf-process -dir /path/to/pdfs -input '*.pdf' -output /path/to/output --extract-images --extract-markdown
```

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
