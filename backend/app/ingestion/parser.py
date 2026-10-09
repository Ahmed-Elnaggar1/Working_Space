import io
import pdfplumber

class ParsingError(Exception):
    pass

def parse_pdf(file_bytes: bytes) -> list[tuple[int, str]]:
    """Parses PDF bytes and extracts text page-by-page using pdfplumber.
    
    Returns a list of (page_number, page_text) tuples.
    """
    if not file_bytes.startswith(b"%PDF"):
        raise ParsingError("Invalid file signature: Not a valid PDF file")

    try:
        pages_content = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text() or ""
                    pages_content.append((page_num, text))
                except Exception as e:
                    raise ParsingError(f"Error extracting text from page {page_num}: {str(e)}") from e
        return pages_content
    except Exception as e:
        if "PDF" in str(e) or "format" in str(e).lower():
            raise ParsingError(f"Failed to parse PDF document: {str(e)}") from e
        raise ParsingError(f"Unexpected error parsing PDF: {str(e)}") from e

def parse_txt(file_bytes: bytes) -> list[tuple[int, str]]:
    """Parses plain text bytes.
    
    Returns a single-item list: [(1, text)].
    """
    try:
        # Try decoding as UTF-8 first, fallback to latin-1
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")
        return [(1, text)]
    except Exception as e:
        raise ParsingError(f"Failed to decode text file: {str(e)}") from e

def parse_file(filename: str, file_bytes: bytes) -> list[tuple[int, str]]:
    """Dispatches to the correct parser based on file extension."""
    lower_filename = filename.lower()
    if lower_filename.endswith(".pdf"):
        return parse_pdf(file_bytes)
    elif lower_filename.endswith(".txt"):
        return parse_txt(file_bytes)
    else:
        raise ParsingError("Unsupported file type. Only PDF and plain text (.txt) files are supported.")
