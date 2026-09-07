def chunk_parsed_content(
    pages_content: list[tuple[int, str]],
    max_words: int = 350,
    overlap: int = 50,
) -> list[dict]:
    """Splits parsed text from pages into chunks.
    
    Ensures that each chunk is associated with the page number it originated from.
    Each chunk has approximately `max_words` words, with `overlap` words shared
    between successive chunks of the same page.
    
    Returns a list of dicts:
        [
            {
                "page_number": int,
                "content": str
            },
            ...
        ]
    """
    chunks = []
    for page_num, text in pages_content:
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
                "content": chunk_text
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
