# Mini AI Business Intelligence Assistant

Ask plain-English questions about sales data and get answers calculated from a database, with data-quality caveats.

## Dataset
Uses the sales CSV supplied by RSG Research HR for this assessment: `data/ai_bi_assistant_sales_data.csv` (51 rows, Jan-Jun 2026).
Columns: `transaction_id, order_date, product, category, region, sales_channel, quantity, unit_price, discount_amount, status`.

## Metric definitions (assumptions)
- **Revenue** = `quantity * unit_price - discount_amount`. The CSV has no revenue column, and `discount_amount` is treated as a flat amount per row.
- Only rows with status **Completed** and valid data count toward revenue.
- Rows are never silently dropped. Rows that fail validation stay in the database with `counted = 0` and a reason in `issue`, and every answer lists them as a caveat.

Rows excluded from the supplied file:
| transaction_id | reason |
|---|---|
| TXN0033 | status is Returned |
| TXN0034 | quantity is 0 |
| TXN0051 | unit_price is missing (not guessed or imputed) |

Please confirm these rules with the business if they differ (for example, whether returns should be netted off instead).

## Features
- FastAPI endpoint `POST /ask`
- Eight analytics: total revenue, top product, top region, revenue by category, revenue by channel, monthly trend, two-month comparison, data-quality report
- SQLite database; fixed, read-only SQL written in application code
- Streamlit UI with supporting table, chart and caveat warnings
- Optional OpenAI intent classification, with a rule-based fallback when no API key is set
- Automated tests

## Architecture
`CSV -> pandas validation -> SQLite <- fixed SQL analytics <- allowlisted intent interpreter <- FastAPI <- Streamlit`

The LLM only classifies a question into one of the allowed intents. It never writes SQL or returns numbers, so every figure comes from application-authored SQL. Anything unsupported is declined.

## How data is stored and queried
- On startup (or `python database.py`) the CSV is read with pandas, validated, and written to one SQLite table, `sales`, in `sales.db`.
- Besides the original columns the table has `revenue` (computed), `counted` (1 = valid, 0 = excluded) and `issue` (the reason a row was excluded).
- Each question type maps to one fixed SQL query in `analytics.py` that filters on `counted = 1`. User text is never put into SQL; month values are bound as parameters, and the connection is opened with `PRAGMA query_only = ON`, so writes and destructive statements are impossible.

## How unsupported or incorrect answers are prevented
- The interpreter (LLM or fallback) can only return one of eight allowed intent labels; anything else is declined.
- The LLM never writes SQL and never supplies numbers, so no figure can be invented. Text-to-SQL is deliberately not used, so there is no generated query to validate.
- Excluded or suspicious rows are reported with every answer instead of being hidden.
- Empty questions, an empty database, a missing month pair, and LLM/API failures all return a clear error or fall back to the rule-based interpreter.

## Setup (Python 3.10+)
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python database.py
```

## Optional LLM
```bash
export OPENAI_API_KEY="your-key"     # PowerShell: $env:OPENAI_API_KEY="your-key"
export OPENAI_MODEL="gpt-4o-mini"
```
Never commit keys. Without a key the rule-based fallback is used.

## Run
```bash
uvicorn main:app --reload        # terminal 1, docs at http://127.0.0.1:8000/docs
streamlit run app.py             # terminal 2
```

## Example questions
- What is the total revenue?
- Which product generated the highest revenue?
- Which region generated the highest sales?
- Which category earns the most?
- Online vs retail revenue?
- What is the monthly revenue trend?
- Compare 2026-01 and 2026-03 revenue (or "compare April and May")
- Show data quality issues

## Tests
```bash
pytest -q
```
Covers the revenue formula, exclusion of returned / zero-quantity / missing-price / duplicate rows, each analytic, month parsing, the interpreter fallback, unsupported questions, an empty database, and known totals on the real CSV (total revenue 1,439,200).

## Known limitations
- The fallback interpreter recognises a limited set of phrasings; the LLM path handles more.
- Month names without a year default to the latest year in the data.
- Only five question types plus category, channel and data-quality; anything else is declined rather than guessed.
- Prototype only: production use would need authentication, logging, rate limits and a security review.
