from fastapi import FastAPI
from fastapi.responses import FileResponse
import os
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from database import Base, engine
from models import Student, Assignment, Grade  # Add any other models you have


app = FastAPI()

@app.get("/download-template")
def download_template():
    file_path = "template.csv"
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename="grade_insight_template.csv", media_type='text/csv')
    else:
        return {"error": "Template file not found."}

@app.get("/testdb")
def test_db():
    database_url = os.getenv("DATABASE_URL")
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "Database connection successful"}
    except OperationalError as e:
        return {"status": "Database connection failed", "error": str(e)}

@app.get("/")
def read_root():
    return {"message": "Grade Insight is running"}
