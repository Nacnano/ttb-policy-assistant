"""
Eval harness: runs 18 grounded + 6 adversarial questions against the /ask API.
Runs in-process using httpx — no running server needed.

Determinism: generation runs at temperature 0 (see GENERATION_TEMPERATURE), so runs are
reproducible. The model + embedding IDs are printed in the summary for provenance.

Metrics reported (grounded set):
  - keyword   : the expected fact phrase appears in the answer (and it is not a refusal)
  - citation  : the expected source document is cited
  - grounded  : keyword AND citation — the answer is both correct and attributed
The headline RAG score is `grounded`; adversarial pass-rate is reported separately, not
folded into the RAG score.

Usage:
    python eval/run_eval.py

Requires OPENAI_API_KEY and a built FAISS index (run scripts/ingest.py first).
"""
import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure repo root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import httpx
from asgi_lifespan import LifespanManager
from app.main import app

from app.config import get_settings

QA_PATH = Path(__file__).parent / "qa_pairs.json"

_REFUSAL = "could not find the answer"  # substring of the grounded-refusal message

_COL_W = (5, 52, 9, 9, 9, 9)
_SEP = "-" * (sum(_COL_W) + len(_COL_W) * 3)


def _fmt_row(*cells):
    parts = []
    for cell, w in zip(cells, _COL_W):
        parts.append(str(cell).ljust(w)[:w])
    return " | ".join(parts)


async def run_eval():
    qa = json.loads(QA_PATH.read_text(encoding="utf-8"))

    grounded_results = []
    adversarial_results = []

    total_prompt_tokens = 0
    total_completion_tokens = 0

    async with LifespanManager(app) as manager, httpx.AsyncClient(
        transport=httpx.ASGITransport(app=manager.app), base_url="http://test"
    ) as client:
        # ---- Grounded questions ----
        print("\n=== Grounded Questions ===")
        print(_fmt_row("ID", "Question", "Keyword", "Cite", "Ground", "Latency"))
        print(_SEP)

        for item in qa["grounded"]:
            t0 = time.perf_counter()
            try:
                resp = await client.post("/ask", json={"question": item["question"]}, timeout=60.0)
                latency = (time.perf_counter() - t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["answer"].lower()

                    # Keyword correctness — the expected fact phrase must appear, and the
                    # answer must not be the grounded-refusal message.
                    is_refusal = _REFUSAL in answer
                    keyword_hit = (not is_refusal) and any(
                        kw.lower() in answer for kw in item["expected_keywords"]
                    )

                    # Citation correctness
                    cited_sources = [c["source"] for c in data.get("citations", [])]
                    citation_hit = item["expected_source"] in cited_sources

                    # Groundedness — correct AND attributed to the right source.
                    grounded_hit = keyword_hit and citation_hit

                    total_prompt_tokens += data.get("prompt_tokens", 0)
                    total_completion_tokens += data.get("completion_tokens", 0)

                    grounded_results.append({
                        "id": item["id"],
                        "keyword": keyword_hit,
                        "citation": citation_hit,
                        "grounded": grounded_hit,
                        "latency_ms": latency,
                    })
                    print(_fmt_row(
                        item["id"],
                        item["question"][:50],
                        "PASS" if keyword_hit else "FAIL",
                        "PASS" if citation_hit else "FAIL",
                        "PASS" if grounded_hit else "FAIL",
                        f"{latency:.0f}ms",
                    ))
                else:
                    grounded_results.append({"id": item["id"], "keyword": False, "citation": False, "grounded": False, "latency_ms": latency})
                    print(_fmt_row(item["id"], item["question"][:50], "ERROR", f"HTTP {resp.status_code}", "", ""))

            except Exception as e:
                latency = (time.perf_counter() - t0) * 1000
                grounded_results.append({"id": item["id"], "keyword": False, "citation": False, "grounded": False, "latency_ms": latency})
                print(_fmt_row(item["id"], item["question"][:50], "ERROR", str(e)[:9], "", ""))

        # ---- Adversarial questions ----
        print(f"\n=== Adversarial Questions ===")
        print(_fmt_row("ID", "Question", "Expected", "Got", "Pass", ""))
        print(_SEP)

        for item in qa["adversarial"]:
            try:
                resp = await client.post("/ask", json={"question": item["question"]}, timeout=30.0)
                if resp.status_code == 400:
                    detail = resp.json().get("detail", {})
                    got_code = detail.get("code", "UNKNOWN")
                    passed = got_code == item["expected_error_code"]
                elif resp.status_code == 422:
                    got_code = "VALIDATION_ERROR"
                    passed = item["expected_error_code"] == "VALIDATION_ERROR"
                else:
                    got_code = f"HTTP {resp.status_code}"
                    passed = False

                adversarial_results.append({"id": item["id"], "passed": passed})
                print(_fmt_row(
                    item["id"],
                    item["question"][:50],
                    item["expected_error_code"],
                    got_code,
                    "PASS" if passed else "FAIL",
                    "",
                ))
            except Exception as e:
                adversarial_results.append({"id": item["id"], "passed": False})
                print(_fmt_row(item["id"], item["question"][:50], item["expected_error_code"], "ERROR", "FAIL", ""))

    # ---- Summary ----
    print(f"\n{'=' * (sum(_COL_W) + len(_COL_W) * 3)}")
    print("SUMMARY")
    print(_SEP)

    n_grounded = len(grounded_results)
    keyword_score = sum(1 for r in grounded_results if r["keyword"]) / n_grounded if n_grounded else 0
    citation_score = sum(1 for r in grounded_results if r["citation"]) / n_grounded if n_grounded else 0
    grounded_score = sum(1 for r in grounded_results if r["grounded"]) / n_grounded if n_grounded else 0
    avg_latency = sum(r["latency_ms"] for r in grounded_results) / n_grounded if n_grounded else 0

    n_adv = len(adversarial_results)
    adv_score = sum(1 for r in adversarial_results if r["passed"]) / n_adv if n_adv else 0

    settings = get_settings()
    print(f"Model / Embeddings        : {settings.chat_model} / {settings.embedding_model} "
          f"(temp={settings.generation_temperature})")
    print(f"Grounded Keyword Accuracy : {keyword_score:.0%} ({sum(r['keyword'] for r in grounded_results)}/{n_grounded})")
    print(f"Grounded Citation Accuracy: {citation_score:.0%} ({sum(r['citation'] for r in grounded_results)}/{n_grounded})")
    print(f"Groundedness (kw & cite)  : {grounded_score:.0%} ({sum(r['grounded'] for r in grounded_results)}/{n_grounded})")
    print(f"Adversarial Pass Rate     : {adv_score:.0%} ({sum(r['passed'] for r in adversarial_results)}/{n_adv})")
    print(f"Avg Latency (grounded)    : {avg_latency:.0f}ms")
    print(f"Total Prompt Tokens       : {total_prompt_tokens}")
    print(f"Total Completion Tokens   : {total_completion_tokens}")

    # Headline RAG score = groundedness (correct AND attributed). Adversarial is reported
    # separately, not folded in. CI gate requires strong grounding AND full adversarial pass.
    print(f"\nRAG Groundedness Score: {grounded_score:.1%}")
    passed = grounded_score >= 0.8 and adv_score >= 1.0
    print(f"Gate (grounded>=80% and adversarial==100%): {'PASS' if passed else 'FAIL'}")

    return passed


if __name__ == "__main__":
    ok = asyncio.run(run_eval())
    sys.exit(0 if ok else 1)
