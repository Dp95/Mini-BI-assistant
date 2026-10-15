import requests
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Mini BI Assistant", page_icon="📊", layout="wide")
st.title("📊 Mini AI Business Intelligence Assistant")
st.caption("Ask questions about sales. Figures are calculated from the SQLite database.")
API_URL = st.sidebar.text_input("Backend API URL", "http://127.0.0.1:8000")
st.sidebar.info("Dataset: sales CSV provided by RSG Research HR for this assessment.")
examples = [
    "What is the total revenue?",
    "Which product generated the highest revenue?",
    "What is the monthly revenue trend?",
    "Which region generated the highest sales?",
    "Compare 2026-01 and 2026-03 revenue",
    "Which category earns the most?",
    "Online vs retail revenue?",
    "Show data quality issues",
]
with st.sidebar:
    st.subheader("Example questions")
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["question"] = ex
question = st.text_input("Enter your business question", key="question", placeholder="e.g. Which product generated the highest revenue?")
if st.button("Ask question", type="primary") and question.strip():
    try:
        response = requests.post(f"{API_URL.rstrip('/')}/ask", json={"question":question}, timeout=30)
        if response.status_code >= 400:
            st.error(f"API error ({response.status_code}): {response.text}")
        else:
            result = response.json()
            if result.get("ok"):
                st.success(result["answer"])
                st.caption(f"Interpretation method: {result.get('interpretation_method','unknown')}")
                data = result.get("supporting_data", [])
                if data:
                    frame = pd.DataFrame(data)
                    st.subheader("Supporting data")
                    st.dataframe(frame, use_container_width=True, hide_index=True)
                    if "month" in frame.columns and "revenue" in frame.columns and len(frame)>1:
                        st.subheader("Monthly revenue")
                        st.line_chart(frame.set_index("month")["revenue"])
                    else:
                        label = next((c for c in ("product","region","category","sales_channel") if c in frame.columns), None)
                        if label and "revenue" in frame.columns and len(frame)>1:
                            st.bar_chart(frame.set_index(label)["revenue"])
                for note in result.get("caveats", []):
                    st.warning(note)
            else:
                st.warning(result.get("error","The question could not be answered."))
    except requests.RequestException as exc:
        st.error(f"Could not reach the API. Start the backend first. Details: {exc}")
st.divider()
st.caption("Revenue = quantity x unit_price - discount_amount, counting Completed orders only. Rows that fail validation are excluded and listed in each answer.")
