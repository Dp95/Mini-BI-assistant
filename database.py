from pathlib import Path
import sqlite3
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "data" / "ai_bi_assistant_sales_data.csv"
DEFAULT_DB = BASE_DIR / "sales.db"

REQUIRED_COLUMNS = [
    "transaction_id", "order_date", "product", "category", "region",
    "sales_channel", "quantity", "unit_price", "discount_amount", "status",
]
# Only rows with this status count toward revenue. Anything else (e.g. Returned) is excluded.
COUNTED_STATUS = "Completed"


def get_connection(db_path=DEFAULT_DB):
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def load_and_clean(csv_path):
    """Read the CSV and return a DataFrame with revenue, a `counted` flag and an `issue` note.

    No row is silently dropped: rows that cannot be trusted are kept in the table but flagged
    (counted = 0) with a human-readable reason, so the assistant can report them.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    raw = pd.read_csv(csv_path, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    missing = set(REQUIRED_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    df = raw[REQUIRED_COLUMNS].copy()
    for col in ("transaction_id", "product", "category", "region", "sales_channel", "status"):
        df[col] = df[col].astype("string").str.strip()
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    for col in ("quantity", "unit_price", "discount_amount"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["discount_amount"] = df["discount_amount"].fillna(0.0)

    # The CSV has no revenue column: revenue = quantity * unit_price - discount_amount
    # (discount_amount is a flat amount per row, not a percentage). NULL if price/quantity is missing.
    df["revenue"] = df["quantity"] * df["unit_price"] - df["discount_amount"]

    duplicate = df["transaction_id"].duplicated(keep="first")

    def issue_for(i):
        row = df.loc[i]
        if pd.isna(row["transaction_id"]) or row["transaction_id"] == "":
            return "missing transaction_id"
        if duplicate[i]:
            return "duplicate transaction_id"
        if pd.isna(row["order_date"]):
            return "invalid order_date"
        if pd.isna(row["unit_price"]):
            return "missing unit_price"
        if pd.isna(row["quantity"]) or row["quantity"] <= 0:
            return "quantity is zero or invalid"
        if row["revenue"] < 0:
            return "discount exceeds line value"
        if row["status"] != COUNTED_STATUS:
            return f"status is {row['status']} (excluded from revenue)"
        return None

    df["issue"] = [issue_for(i) for i in df.index]
    df["counted"] = df["issue"].isna().astype(int)
    df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d")
    return df


def initialize_database(csv_path=DEFAULT_CSV, db_path=DEFAULT_DB):
    df = load_and_clean(csv_path)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        df.to_sql("sales", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(order_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_region ON sales(region)")
    return {
        "loaded_rows": int(len(df)),
        "counted_rows": int(df["counted"].sum()),
        "excluded_rows": int((df["counted"] == 0).sum()),
        "database": str(db_path),
        "table": "sales",
    }


if __name__ == "__main__":
    print(initialize_database())
