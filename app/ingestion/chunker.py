from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def chunk_document(doc: dict, chunk_size: int = 400, chunk_overlap: int = 80) -> list[dict]:
    """
    Split a policy document into chunks.
    First splits by Markdown headers, then recursively splits long sections.
    Returns list of {chunk_id, source, header_path, text}.
    """
    source = doc["source"]
    content = doc["content"]

    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_HEADERS, strip_headers=False)
    header_chunks = header_splitter.split_text(content)

    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=["\n\n", "\n", " ", ""]
    )

    chunks = []
    idx = 0
    for hchunk in header_chunks:
        text = hchunk.page_content.strip()
        if not text:
            continue

        header_path = " > ".join(
            v for k in ("h1", "h2", "h3") if (v := hchunk.metadata.get(k))
        )

        if len(text) <= chunk_size:
            chunks.append(
                {
                    "chunk_id": f"{source}::chunk_{idx}",
                    "source": source,
                    "header_path": header_path,
                    "text": text,
                }
            )
            idx += 1
        else:
            sub_chunks = recursive_splitter.split_text(text)
            for sub in sub_chunks:
                sub = sub.strip()
                if sub:
                    chunks.append(
                        {
                            "chunk_id": f"{source}::chunk_{idx}",
                            "source": source,
                            "header_path": header_path,
                            "text": sub,
                        }
                    )
                    idx += 1

    return chunks
