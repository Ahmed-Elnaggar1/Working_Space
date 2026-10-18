import re
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings


def _detect_heading(line: str) -> str | None:
    """Detects if a single line looks like a section heading."""
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip() or None
    if re.match(r"^(section|chapter|part)\s+\d+[:.]?", stripped, re.IGNORECASE):
        return stripped
    if stripped.isupper() and 3 <= len(stripped) <= 60 and not stripped.endswith("."):
        return stripped
    return None


def _split_page_by_sections(
    text: str,
    initial_section: str | None,
) -> tuple[list[tuple[str | None, str]], str | None]:
    """Splits a page's text into (section, segment_text) pairs as headings are encountered."""
    current_section = initial_section
    segments: list[tuple[str | None, str]] = []
    segment_lines: list[str] = []
    has_body = False

    for line in text.splitlines(keepends=True):
        heading = _detect_heading(line)
        if heading is not None:
            if segment_lines and has_body:
                segments.append((current_section, "".join(segment_lines)))
                segment_lines = []
                has_body = False
            current_section = heading
            segment_lines.append(line)
        else:
            segment_lines.append(line)
            if line.strip():
                has_body = True

    if segment_lines:
        segments.append((current_section, "".join(segment_lines)))

    return segments, current_section


def chunk_parsed_content(
    pages_content: list[tuple[int, str]],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    *,
    max_words: int | None = None,
    overlap: int | None = None,
) -> list[dict]:
    """Splits parsed text from pages into chunks using LangChain's RecursiveCharacterTextSplitter.

    Ensures that each chunk is associated with the page number and exact section it originated from.
    """
    settings = get_settings()
    if max_words is not None:
        effective_size = max_words
        effective_overlap = overlap if overlap is not None else min(50, max_words // 2)
        length_fn = lambda s: len(s.split())  # noqa: E731
    else:
        effective_size = chunk_size if chunk_size is not None else settings.CHUNK_SIZE
        effective_overlap = chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP
        length_fn = len

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=effective_size,
        chunk_overlap=effective_overlap,
        length_function=length_fn,
        is_separator_regex=False,
    )

    chunks = []
    current_section: str | None = None

    for page_num, text in pages_content:
        if not text or not text.strip():
            continue

        segments, current_section = _split_page_by_sections(text, current_section)

        for section_name, segment_text in segments:
            page_chunks = text_splitter.split_text(segment_text)
            for chunk_text in page_chunks:
                if not chunk_text.strip():
                    continue
                chunks.append({
                    "page_number": page_num,
                    "section": section_name,
                    "content": chunk_text,
                })

    return chunks

