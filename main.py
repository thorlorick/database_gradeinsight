import io
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import FileResponse
import pandas as pd
import os
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import Student, Assignment, Grade
import models

app = FastAPI()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "Database connection successful"}
    except OperationalError as e:
        return {"status": "Database connection failed", "error": str(e)}

@app.get("/")
def read_root():
    return {"message": "Grade Insight is running"}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    df = pd.read_csv(io.StringIO(contents.decode("utf-8")))

    # Validate column presence
    required_columns = {"student_number", "first_name", "last_name", "email"}
    if not required_columns.issubset(df.columns):
        return {"error": "Missing required student columns."}

    # Start processing
    for index, row in df.iterrows():
        student_number = str(row["student_number"]).strip()

        # === UPSERT STUDENT ===
        student = db.query(Student).filter_by(student_number=student_number).first()
        if student:
            student.first_name = row["first_name"]
            student.last_name = row["last_name"]
            student.email = row.get("email", None)
        else:
            student = Student(
                student_number=student_number,
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row.get("email", None)
            )
            db.add(student)

        # === UPSERT ASSIGNMENTS & GRADES ===
        for col in df.columns:
            if col in required_columns:
                continue  # skip student info

            score = row[col]
            if pd.isna(score):
                continue  # skip empty grades

            # Use default max_points and optional date logic
            assignment = db.query(Assignment).filter_by(name=col).first()
            if not assignment:
                assignment = Assignment(name=col, max_points=100)  # default
                db.add(assignment)
                db.flush()  # get assignment.id

            # Upsert grade
            grade = (
                db.query(Grade)
                .filter_by(student_number=student_number, assignment_id=assignment.id)
                .first()
            )
            if grade:
                grade.score = score
            else:
                grade = Grade(
                    student_number=student_number,
                    assignment_id=assignment.id,
                    score=score,
                )
                db.add(grade)

    db.commit()
    return {"status": "Upload processed successfully"}

