import re
from database import get_connection, DEFAULT_DB

ALLOWED_INTENTS = {
    "total_revenue", "top_product", "monthly_trend", "top_region", "month_comparison",
    "revenue_by_category", "revenue_by_channel", "data_quality",
}
# Every revenue query only uses rows that passed validation (see database.load_and_clean).
COUNTED = "counted = 1"

MONTH_NAMES = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
}


def _rows(sql, params=(), db_path=DEFAULT_DB):
    conn = get_connection(db_path)
    try:
        conn.execute("PRAGMA query_only = ON")
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _default_year(db_path):
    r = _rows(f"SELECT MAX(substr(order_date,1,4)) AS y FROM sales WHERE {COUNTED}", db_path=db_path)
    return (r[0]["y"] if r and r[0]["y"] else "2026")


def _months(question, default_year):
    q = question.lower()
    found = re.findall(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b", q)
    if len(found) >= 2:
        return [f"{y}-{int(m):02d}" for y, m in found[:2]]
    year_match = re.search(r"\b(20\d{2})\b", q)
    year = year_match.group(1) if year_match else default_year
    names = sorted((q.find(n), m) for n, m in MONTH_NAMES.items() if re.search(rf"\b{n}\b", q))
    return [f"{year}-{names[0][1]}", f"{year}-{names[1][1]}"] if len(names) >= 2 else []


def _excluded(db_path):
    return _rows("SELECT transaction_id, order_date, product, issue FROM sales WHERE counted = 0 ORDER BY transaction_id", db_path=db_path)


def _caveats(db_path):
    """Plain-language warnings attached to every answer so excluded rows are never hidden."""
    ex = _excluded(db_path)
    if not ex:
        return []
    ids = ", ".join(f"{r['transaction_id']} ({r['issue']})" for r in ex)
    return [f"{len(ex)} row(s) excluded from revenue: {ids}."]


def _ok(intent, answer, data, db_path, **extra):
    out = {"ok": True, "intent": intent, "answer": answer, "supporting_data": data, "caveats": _caveats(db_path)}
    out.update(extra)
    return out


def run_analytics(intent, question="", db_path=DEFAULT_DB):
    if intent not in ALLOWED_INTENTS:
        return {"ok": False, "error": "Unsupported question. Try one of the example sales questions."}
    counts = _rows("SELECT COUNT(*) AS n, COALESCE(SUM(counted),0) AS c FROM sales", db_path=db_path)
    if not counts or counts[0]["n"] == 0:
        return {"ok": False, "error": "The sales dataset is empty. Load valid transactions first."}
    if counts[0]["c"] == 0 and intent != "data_quality":
        return {"ok": False, "error": "No valid transactions are available to analyse.", "caveats": _caveats(db_path)}

    if intent == "data_quality":
        ex = _excluded(db_path)
        msg = (f"{len(ex)} of {counts[0]['n']} rows are excluded from revenue calculations."
               if ex else "All rows passed validation.")
        return {"ok": True, "intent": intent, "answer": msg, "supporting_data": ex, "caveats": []}

    if intent == "total_revenue":
        data = _rows(f"SELECT ROUND(COALESCE(SUM(revenue),0),2) AS total_revenue, COUNT(*) AS transaction_count FROM sales WHERE {COUNTED}", db_path=db_path)
        r = data[0]
        return _ok(intent, f"Total revenue is {r['total_revenue']:,.2f} across {r['transaction_count']} completed transactions.", data, db_path)

    if intent == "top_product":
        data = _rows(f"SELECT product, ROUND(SUM(revenue),2) AS revenue FROM sales WHERE {COUNTED} GROUP BY product ORDER BY revenue DESC, product ASC", db_path=db_path)
        r = data[0]
        return _ok(intent, f"{r['product']} generated the highest revenue: {r['revenue']:,.2f}.", data, db_path)

    if intent == "top_region":
        data = _rows(f"SELECT region, ROUND(SUM(revenue),2) AS revenue FROM sales WHERE {COUNTED} GROUP BY region ORDER BY revenue DESC, region ASC", db_path=db_path)
        r = data[0]
        return _ok(intent, f"{r['region']} generated the highest revenue: {r['revenue']:,.2f}.", data, db_path)

    if intent == "revenue_by_category":
        data = _rows(f"SELECT category, ROUND(SUM(revenue),2) AS revenue FROM sales WHERE {COUNTED} GROUP BY category ORDER BY revenue DESC, category ASC", db_path=db_path)
        r = data[0]
        return _ok(intent, f"{r['category']} is the top category with {r['revenue']:,.2f} in revenue.", data, db_path)

    if intent == "revenue_by_channel":
        data = _rows(f"SELECT sales_channel, ROUND(SUM(revenue),2) AS revenue FROM sales WHERE {COUNTED} GROUP BY sales_channel ORDER BY revenue DESC, sales_channel ASC", db_path=db_path)
        r = data[0]
        return _ok(intent, f"{r['sales_channel']} is the top sales channel with {r['revenue']:,.2f} in revenue.", data, db_path)

    if intent == "monthly_trend":
        data = _rows(f"SELECT substr(order_date,1,7) AS month, ROUND(SUM(revenue),2) AS revenue FROM sales WHERE {COUNTED} GROUP BY substr(order_date,1,7) ORDER BY month", db_path=db_path)
        best = max(data, key=lambda x: x["revenue"])
        return _ok(intent, f"Monthly revenue trend covers {len(data)} month(s); the peak was {best['month']} at {best['revenue']:,.2f}.", data, db_path)

    # month_comparison
    months = _months(question, _default_year(db_path))
    if len(months) != 2:
        return {"ok": False, "intent": intent, "error": "Specify two months, e.g. 'Compare 2026-01 and 2026-03 revenue'."}
    data = _rows(f"SELECT substr(order_date,1,7) AS month, ROUND(SUM(revenue),2) AS revenue FROM sales WHERE {COUNTED} AND substr(order_date,1,7) IN (?,?) GROUP BY substr(order_date,1,7)", (months[0], months[1]), db_path)
    by_month = {r["month"]: r["revenue"] for r in data}
    first, second = months
    a, b = float(by_month.get(first, 0)), float(by_month.get(second, 0))
    change = round(b - a, 2)
    pct = None if a == 0 else round(change / a * 100, 2)
    details = [{"month": m, "revenue": v, "note": "No matching transactions; treated as zero" if m not in by_month else None} for m, v in [(first, a), (second, b)]]
    pct_text = "percentage change unavailable because the first month's revenue is zero" if pct is None else f"{pct:+.2f}%"
    return _ok(intent, f"Revenue changed by {change:,.2f} from {first} to {second} ({pct_text}).", details, db_path, change=change, percentage_change=pct)
