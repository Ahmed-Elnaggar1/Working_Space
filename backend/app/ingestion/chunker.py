import re
from langchain_text_splitters import RecursiveCharacterTextSplitter

def _detect_heading(line: str) -> str | None:
    """Detects if a single line looks like a section heading."""
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()
    if re.match(r"^(section|chapter|part)\s+\d+[:.]?", stripped, re.IGNORECASE):
        return stripped
    if stripped.isupper() and 3 <= len(stripped) <= 60 and not stripped.endswith("."):
        return stripped
    return None

def chunk_parsed_content(
    pages_content: list[tuple[int, str]],
    chunk_size: int = 2000,
    chunk_overlap: int = 200,
) -> list[dict]:
    """Splits parsed text from pages into chunks using LangChain's RecursiveCharacterTextSplitter.
    
    Ensures that each chunk is associated with the page number and section it originated from.
    """
    chunks = []
    current_section: str | None = None

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )

    for page_num, text in pages_content:
        # Check lines on the page for section headings
        lines = text.splitlines()
        for line in lines:
            heading = _detect_heading(line)
            if heading:
                current_section = heading
                break

        page_chunks = text_splitter.split_text(text)
        
        for chunk_text in page_chunks:
            if not chunk_text.strip():
                continue
                
            chunks.append({
                "page_number": page_num,
                "section": current_section,
                "content": chunk_text,
            })

    return chunks
