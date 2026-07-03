from unittest.mock import AsyncMock, MagicMock, patch

from app.generation.generator import Generator, _parse_citations


_CHUNKS = [
    {"chunk_id": "leave.md::chunk_0", "source": "leave.md", "header_path": "Annual Leave", "text": "15 days of annual leave."},
]


def test_well_formed_citation_parsed_and_stripped():
    answer_text = (
        "You get 15 days of annual leave.\n"
        "[SOURCE: leave.md | CHUNK: leave.md::chunk_0 | EXCERPT: 15 days of annual leave]"
    )
    clean_answer, citations = _parse_citations(answer_text, _CHUNKS)

    assert clean_answer == "You get 15 days of annual leave."
    assert len(citations) == 1
    assert citations[0].source == "leave.md"
    assert citations[0].chunk_id == "leave.md::chunk_0"
    assert citations[0].excerpt == "15 days of annual leave"
    assert "SOURCE" not in clean_answer


def test_duplicate_chunk_ids_deduplicated():
    answer_text = (
        "You get 15 days of annual leave.\n"
        "[SOURCE: leave.md | CHUNK: leave.md::chunk_0 | EXCERPT: 15 days]\n"
        "[SOURCE: leave.md | CHUNK: leave.md::chunk_0 | EXCERPT: another quote]"
    )
    _, citations = _parse_citations(answer_text, _CHUNKS)

    assert len(citations) == 1
    assert citations[0].chunk_id == "leave.md::chunk_0"


def test_citations_heading_stripped_with_citation_lines():
    answer_text = (
        "You get 15 days of annual leave.\n"
        "Citations:\n"
        "[SOURCE: leave.md | CHUNK: leave.md::chunk_0 | EXCERPT: 15 days of annual leave]"
    )
    clean_answer, citations = _parse_citations(answer_text, _CHUNKS)

    assert clean_answer == "You get 15 days of annual leave."
    assert len(citations) == 1


def test_bold_citations_heading_stripped():
    answer_text = (
        "You get 15 days of annual leave.\n"
        "**Citations:**\n"
        "[SOURCE: leave.md | CHUNK: leave.md::chunk_0 | EXCERPT: 15 days of annual leave]"
    )
    clean_answer, _ = _parse_citations(answer_text, _CHUNKS)

    assert clean_answer == "You get 15 days of annual leave."


def test_missing_citation_block_leaves_answer_untouched_and_no_fallback():
    answer_text = "You get 15 days of annual leave."
    clean_answer, citations = _parse_citations(answer_text, _CHUNKS)

    assert clean_answer == answer_text
    assert citations == []


def test_malformed_citation_line_ignored():
    answer_text = "You get 15 days of annual leave.\n[SOURCE: leave.md CHUNK missing pipes]"
    clean_answer, citations = _parse_citations(answer_text, _CHUNKS)

    assert citations == []
    assert clean_answer == answer_text


def _mock_chat_response(content: str):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage.prompt_tokens = 42
    resp.usage.completion_tokens = 7
    return resp


async def test_generate_passes_temperature_and_max_tokens_through():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_chat_response(
        "You get 15 days of annual leave.\n"
        "[SOURCE: leave.md | CHUNK: leave.md::chunk_0 | EXCERPT: 15 days of annual leave]"
    ))

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        generator = Generator(
            api_key="fake",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=256,
        )
        result = await generator.generate("How many days of annual leave?", _CHUNKS)

    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 256
    assert result["prompt_tokens"] == 42
    assert result["completion_tokens"] == 7
    assert len(result["citations"]) == 1
