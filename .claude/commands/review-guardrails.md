Audit the guardrail layers against a test input.

Argument: $ARGUMENTS (a test question/prompt to trace through all guardrails)

Steps:
1. Read the three guardrail modules:
   - `app/guardrails/injection.py` — regex injection patterns
   - `app/guardrails/pii.py` — PII redaction (Presidio + regex)
   - `app/guardrails/scope.py` — keyword blocklist + embedding similarity
2. Trace the provided input through each layer and report:
   - **Injection**: which patterns match (if any), or confirm no match
   - **PII**: what gets redacted and by which engine (presidio vs regex), show the redacted output
   - **Scope**: which blocklist patterns match (if any); note whether the embedding gate would apply
3. Report the overall verdict: would this input be ALLOWED, INJECTION_DETECTED, or OUT_OF_SCOPE
4. If the input *should* be caught but isn't (false negative), suggest a specific pattern to add
5. If the input *shouldn't* be caught but is (false positive), suggest how to tighten the pattern
6. Run any suggested changes through the existing test suite (`python -m pytest tests/unit/test_injection.py tests/unit/test_pii.py tests/unit/test_scope.py -v`) to verify no regressions
