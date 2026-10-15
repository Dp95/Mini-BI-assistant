# AI-Assisted Development Notes

## AI tools used
- ChatGPT: [interpreting the challenge, planning the architecture]
- Claude: [drafting code, writing tests, reviewing data-quality handling]
- OpenAI API (API key): used inside the app so the LLM classifies a question into a fixed list of intents
- VS Code: editor and debugging
- Git Bash: running the app, running tests, Git commits
- Streamlit: the front-end UI for asking questions

## How AI was used
AI helped with [planning the structure, drafting code, writing test cases]. 
I made these decisions myself: [exclude bad rows rather than impute, keep SQL out of the LLM, how revenue is defined].

## Data problems found and how they were handled
- The CSV has no revenue column, so revenue = quantity x unit_price - discount_amount.
- TXN0051 has a missing unit_price: excluded and reported, not imputed.
- TXN0034 has quantity 0 but status Completed: excluded and reported.
- TXN0033 is Returned: excluded from revenue and reported.
- Because of this, answers carry a caveat; the June figure is understated by the missing price.

## Design choices
- The LLM only picks an intent from a fixed list; SQL is written in code. This avoids wrong or unsafe generated SQL.
- Rows are flagged, not deleted, so nothing disappears silently.

## Where AI output needed correction
1. **Out-of-scope question (weather).**
   During manual testing I asked a question about the weather, which is not part of the sales data or the supported intents. [returned an unrelated revenue figure / returned an error] I did not fix this in the time available. With more time I would add an `unsupported` intent so the app replies with a clear "I can only answer questions about the sales data" message, and add a test for it.

2. **Import error in the tests.**
   The AI-generated test code used `from analytics import run_analytics`, which failed with [exact error, e.g. ModuleNotFoundError / ImportError] when run from the test folder. [Cause, e.g. Python could not find the module from the tests directory, or the test file was itself named analytics.py.] I fixed it by [what you did, e.g. configuring pytest in pyproject.toml, renaming the test file to test_analytics.py, or changing the import path], then re-ran the tests until they passed.

## Verification
- Automated tests on a small controlled CSV and on the real CSV (total revenue 1,439,200).
- Ran the API through /docs and the Streamlit UI manually. [Keep only if true.]

## With one more day
- Confirm metric definitions (returns, discount meaning) with the business.
- Add a data-quality report listing excluded transaction IDs and reasons.
- Add CSV upload, richer date parsing, more question types, logging, integration tests and CI.
- Handle out-of-scope questions (like the weather) with an `unsupported` intent and a test.
