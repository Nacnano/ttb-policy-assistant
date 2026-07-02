from pathlib import Path


def load_policies(directory: str) -> list[dict]:
    """Load all .md files from directory, return list of {source, content}."""
    docs = []
    policy_dir = Path(directory)
    for path in sorted(policy_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        docs.append({"source": path.name, "content": content})
    return docs
