Run the eval harness and analyse results.

Steps:
1. Run `python eval/run_eval.py` from the project root
2. Parse the output and present a summary table of all grounded and adversarial results
3. If any grounded questions FAIL keyword matching, read the actual LLM answer and suggest fixes to `eval/qa_pairs.json` (adjusted keywords or rephrased question)
4. If any adversarial questions FAIL, read the question and identify which guardrail (injection, scope, PII) should have caught it, then suggest a fix
5. Report overall score, average latency, and total token usage
6. Compare against the SLO targets in README.md (p95 < 5s, hallucination < 10%)

Note: Requires OPENAI_API_KEY in .env and a built FAISS index (run `python scripts/ingest.py` first if needed).
