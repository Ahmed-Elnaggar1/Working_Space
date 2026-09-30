import re


def _detect_heading(line: str) -> str | None:
    """Detects if a single line looks like a section heading."""
    stripped = line.strip()
    if not stripped:
        return None
    # Markdown headings (# Heading, ## Subheading)
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()
    # Explicit Section / Chapter headers (e.g. 'Section 1: Intro', 'Chapter 2')
    if re.match(r"^(section|chapter|part)\s+\d+[:.]?", stripped, re.IGNORECASE):
        return stripped
    # Short all-caps headings (e.g. 'INTRODUCTION', 'OVERVIEW')
    if stripped.isupper() and 3 <= len(stripped) <= 60 and not stripped.endswith("."):
        return stripped
    return None


def chunk_parsed_content(
    pages_content: list[tuple[int, str]],
    max_words: int = 350,
    overlap: int = 50,
) -> list[dict]:
    """Splits parsed text from pages into chunks.
    
    Ensures that each chunk is associated with the page number and section it originated from.
    Each chunk has approximately `max_words` words, with `overlap` words shared
    between successive chunks of the same page.
    
    Returns a list of dicts:
        [
            {
                "page_number": int,
                "section": str | None,
                "content": str
            },
            ...
        ]
    """
    chunks = []
    current_section: str | None = None

    for page_num, text in pages_content:
        # Check lines on the page for section headings
        lines = text.splitlines()
        for line in lines:
            heading = _detect_heading(line)
            if heading:
                current_section = heading
                break

        words = text.split()
        if not words:
            continue

        i = 0
        while i < len(words):
            # Take a slice of words
            chunk_words = words[i : i + max_words]
            chunk_text = " ".join(chunk_words)
            
            chunks.append({
                "page_number": page_num,
                "section": current_section,
                "content": chunk_text,
            })
            
            # Step forward by (max_words - overlap)
            i += max_words - overlap
            
            # Prevent infinite loops if overlap >= max_words (sanity check)
            if max_words - overlap <= 0:
                break

            # If we've processed all words, or the current slice was smaller
            # than max_words (reached the end), we can stop.
            if i >= len(words) or len(chunk_words) < max_words:
                break

    return chunks
