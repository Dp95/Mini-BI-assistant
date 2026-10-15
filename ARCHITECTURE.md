# Architecture

```text
ai_bi_assistant_sales_data.csv
  -> pandas validation (revenue formula, counted flag, issue reason)
  -> SQLite `sales` table (all rows kept)
  <- fixed, read-only SQL analytics (counted rows only)
  <- allowlisted question intent (LLM or rule-based)
  <- FastAPI POST /ask
  <- Streamlit UI (answer, table, chart, caveats)
```

## Key decisions
- **No silent drops:** invalid rows are flagged (`counted = 0`, `issue`) instead of deleted, so answers can say what was excluded.
- **Revenue** is computed as `quantity * unit_price - discount_amount`; only `Completed` rows count.
- **Fixed SQL + allowlisted intents** instead of LLM-generated SQL: predictable, testable, and safe from prompt injection.
- Duplicate `transaction_id` values after the first are excluded as duplicates.

## Safety
- LLM output is untrusted and only an allowlisted intent label is accepted; it is told not to produce SQL or numbers.
- Analytics connections use `PRAGMA query_only = ON`.
- Month values are passed as SQL parameters; table and column names are never built from user input.
- Unsupported questions are declined.
