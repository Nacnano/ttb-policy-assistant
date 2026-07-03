Add new eval question(s) to the eval harness.

Argument: $ARGUMENTS (either a policy filename to generate questions for, or a specific question to add)

Steps:
1. Read `eval/qa_pairs.json` to find the next available ID (G## or A##)
2. If a policy filename is given:
   - Read the policy file from `policies/`
   - Identify 1-2 specific, testable facts (numbers, thresholds, named rules)
   - Generate grounded questions with `expected_keywords` drawn directly from the document text
   - Set `expected_source` to the policy filename
3. If a specific question is given:
   - Determine if it's grounded (expects a factual answer) or adversarial (expects rejection)
   - For grounded: search the policies directory for relevant content and set keywords + source
   - For adversarial: set the appropriate `expected_error_code` (INJECTION_DETECTED or OUT_OF_SCOPE)
4. Add the new entries to `eval/qa_pairs.json` maintaining valid JSON format
5. Run `python -m pytest -v --tb=short` to verify no test regressions
6. Remind the user to run `/eval` to verify the new questions pass with the live API
