from app.ingestion.loader import load_policies


def test_loads_all_markdown_files(tmp_path):
    (tmp_path / "leave.md").write_text("# Leave Policy\nContent A", encoding="utf-8")
    (tmp_path / "kyc.md").write_text("# KYC Policy\nContent B", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not markdown", encoding="utf-8")

    docs = load_policies(str(tmp_path))

    assert len(docs) == 2
    for doc in docs:
        assert set(doc.keys()) == {"source", "content"}


def test_returned_content_matches_file_contents(tmp_path):
    (tmp_path / "leave.md").write_text("# Leave Policy\nContent A", encoding="utf-8")

    docs = load_policies(str(tmp_path))

    assert docs[0]["source"] == "leave.md"
    assert docs[0]["content"] == "# Leave Policy\nContent A"


def test_deterministic_sorted_order(tmp_path):
    (tmp_path / "zeta.md").write_text("z", encoding="utf-8")
    (tmp_path / "alpha.md").write_text("a", encoding="utf-8")
    (tmp_path / "mid.md").write_text("m", encoding="utf-8")

    docs = load_policies(str(tmp_path))

    assert [d["source"] for d in docs] == ["alpha.md", "mid.md", "zeta.md"]


def test_empty_directory_returns_empty_list(tmp_path):
    docs = load_policies(str(tmp_path))
    assert docs == []
