from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from database import initialize_database, DEFAULT_CSV, DEFAULT_DB
from ai_interpreter import interpret_question
from analytics import run_analytics

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DEFAULT_DB.exists():
        initialize_database(DEFAULT_CSV, DEFAULT_DB)
    yield

app = FastAPI(title="Mini BI Assistant API", version="1.0.0", lifespan=lifespan)

class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

@app.get("/")
def root():
    return {"message": "Mini BI Assistant API is running"}


@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/ask")
def ask(request: QuestionRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be blank.")
    interpretation = interpret_question(question)
    if not interpretation["supported"]:
        return {"ok":False,"question":question,"error":"I cannot answer that with the supported sales analytics. Try total revenue, top product, top region, revenue by category or channel, monthly trend, a two-month comparison, or data quality.","interpretation_method":interpretation["method"]}
    result = run_analytics(interpretation["intent"], question, DEFAULT_DB)
    result["question"] = question
    result["interpretation_method"] = interpretation["method"]
    return result
