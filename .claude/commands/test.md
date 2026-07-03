Run the test suite and analyse results.

Steps:
1. Run `python -m pytest -v --tb=short` from the project root
2. Summarise: total passed, failed, errors, and warnings
3. If any tests fail:
   - Read the failing test file and the source file it tests
   - Identify the root cause
   - Propose a fix (or apply it if the fix is obvious and safe)
4. If all tests pass, report the count and confirm no regressions

Optional argument: a specific test path or pattern to run (e.g. `tests/unit/test_injection.py` or `-k pii`)
