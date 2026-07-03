Guide adding a new policy document end-to-end.

Argument: $ARGUMENTS (policy topic or filename, e.g. "fraud_prevention" or a description like "policy about fraud prevention procedures")

Steps:
1. List existing policies in `policies/` to check for overlap or naming convention
2. Create the new policy markdown file in `policies/` following the existing format:
   - Top-level `#` heading with policy name
   - `##` sections for logical divisions
   - Specific numbers, thresholds, and actionable rules (these become eval targets)
   - Keep it synthetic — no real bank data
3. Add 1-2 scope anchor phrases to `app/guardrails/scope.py` `_ANCHOR_TEXTS` list covering the new policy area
4. Add 1 grounded eval question to `eval/qa_pairs.json` with:
   - A question targeting a specific fact from the new policy
   - `expected_keywords` matching exact text from the document
   - `expected_source` matching the new filename
5. Run `python scripts/ingest.py` to rebuild the FAISS index (requires OPENAI_API_KEY)
6. Run `python -m pytest -v --tb=short` to verify no regressions
7. Summarise what was added and remind the user to run `/eval` to verify the new question
