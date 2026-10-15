import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from analytics import run_analytics


import sqlite3
import pytest
from analytics import run_analytics
from ai_interpreter import interpret_question
from database import initialize_database, DEFAULT_CSV

HEADER = "transaction_id,order_date,product,category,region,sales_channel,quantity,unit_price,discount_amount,status\n"


@pytest.fixture
def test_db(tmp_path):
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        HEADER
        + "T1,2026-01-05,Laptop Stand,Accessories,South,Online,2,100,0,Completed\n"   # 200
        + "T2,2026-01-09,Wireless Mouse,Accessories,North,Retail,3,10,0,Completed\n"  # 30
        + "T3,2026-02-02,Laptop Stand,Accessories,South,Online,1,100,0,Completed\n"   # 100
        + "T4,2026-02-03,Monitor,Electronics,West,Retail,1,500,50,Completed\n"        # 450
        + "T5,2026-02-04,Monitor,Electronics,West,Retail,2,500,0,Returned\n"          # excluded: returned
        + "T6,2026-02-05,Keyboard,Accessories,East,Online,0,90,0,Completed\n"         # excluded: qty 0
        + "T7,2026-02-06,Laptop Stand,Accessories,East,Online,5,,0,Completed\n"       # excluded: no price
        + "T1,2026-02-07,Desk,Furniture,East,Online,1,900,0,Completed\n",             # excluded: duplicate id
        encoding="utf-8",
    )
    db_path = tmp_path / "test.db"
    initialize_database(csv_path, db_path)
    return db_path


def test_load_summary_counts_every_row(tmp_path):
    csv_path = tmp_path / "s.csv"
    csv_path.write_text(HEADER + "T1,2026-01-05,A,C,North,Online,1,10,0,Completed\nT2,2026-01-06,A,C,North,Online,1,,0,Completed\n", encoding="utf-8")
    summary = initialize_database(csv_path, tmp_path / "x.db")
    assert summary["loaded_rows"] == 2 and summary["counted_rows"] == 1 and summary["excluded_rows"] == 1


def test_total_revenue_uses_formula_and_excludes_bad_rows(test_db):
    r = run_analytics("total_revenue", db_path=test_db)
    assert r["supporting_data"][0]["total_revenue"] == 780.0  # 200+30+100+450
    assert r["supporting_data"][0]["transaction_count"] == 4


def test_caveats_list_every_excluded_row(test_db):
    caveat = run_analytics("total_revenue", db_path=test_db)["caveats"][0]
    for txt in ("T5", "T6", "T7", "returned", "missing unit_price", "duplicate"):
        assert txt.lower() in caveat.lower()


def test_top_product(test_db):
    r = run_analytics("top_product", db_path=test_db)
    assert r["supporting_data"][0] == {"product": "Monitor", "revenue": 450.0}


def test_top_region(test_db):
    r = run_analytics("top_region", db_path=test_db)
    assert r["supporting_data"][0]["region"] == "West"


def test_revenue_by_category_and_channel(test_db):
    cat = run_analytics("revenue_by_category", db_path=test_db)["supporting_data"]
    assert {c["category"]: c["revenue"] for c in cat} == {"Accessories": 330.0, "Electronics": 450.0}
    ch = run_analytics("revenue_by_channel", db_path=test_db)["supporting_data"]
    assert {c["sales_channel"]: c["revenue"] for c in ch} == {"Online": 300.0, "Retail": 480.0}


def test_monthly_trend_sorted(test_db):
    r = run_analytics("monthly_trend", db_path=test_db)
    assert [x["month"] for x in r["supporting_data"]] == ["2026-01", "2026-02"]
    assert [x["revenue"] for x in r["supporting_data"]] == [230.0, 550.0]


def test_month_comparison(test_db):
    r = run_analytics("month_comparison", "Compare 2026-01 and 2026-02", test_db)
    assert r["change"] == 320.0 and r["percentage_change"] == 139.13


def test_month_comparison_names_default_to_dataset_year(test_db):
    r = run_analytics("month_comparison", "compare january and february", test_db)
    assert r["ok"] and r["change"] == 320.0


def test_data_quality_lists_excluded_rows(test_db):
    r = run_analytics("data_quality", db_path=test_db)
    assert {x["transaction_id"] for x in r["supporting_data"]} == {"T5", "T6", "T7", "T1"}


def test_unsupported_intent(test_db):
    assert run_analytics("drop_table", db_path=test_db)["ok"] is False


def test_fallback_interpreter_routes_and_declines(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert interpret_question("What is the total revenue?")["intent"] == "total_revenue"
    assert interpret_question("Which category earns the most?")["intent"] == "revenue_by_category"
    assert interpret_question("Online vs retail revenue?")["intent"] == "revenue_by_channel"
    assert interpret_question("Show data quality issues")["intent"] == "data_quality"
    assert interpret_question("Write me a poem")["supported"] is False


def test_empty_database(tmp_path):
    db = tmp_path / "empty.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE sales (transaction_id TEXT, order_date TEXT, product TEXT, category TEXT, region TEXT, sales_channel TEXT, quantity REAL, unit_price REAL, discount_amount REAL, status TEXT, revenue REAL, issue TEXT, counted INTEGER)")
    r = run_analytics("total_revenue", db_path=db)
    assert not r["ok"] and "empty" in r["error"].lower()


def test_real_hr_csv_known_totals(tmp_path):
    db = tmp_path / "real.db"
    summary = initialize_database(DEFAULT_CSV, db)
    assert summary["loaded_rows"] == 51 and summary["excluded_rows"] == 3
    r = run_analytics("total_revenue", db_path=db)
    assert r["supporting_data"][0]["total_revenue"] == 1439200.0
    assert any("TXN0051" in c and "TXN0034" in c and "TXN0033" in c for c in r["caveats"])
