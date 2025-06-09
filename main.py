import io
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import FileResponse
import pandas as pd
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import Student, Assignment, Grade
import models


app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")


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
        
@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    with open("temp_upload.csv", "wb") as f:
        f.write(contents)
    # TODO: Add your CSV processing logic here
    return templates.TemplateResponse("upload_success.html", {"request": request, "filename": file.filename})


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
    csv_io = io.StringIO(contents.decode("utf-8"))

    # Step 1: Read entire CSV
    full_df = pd.read_csv(csv_io, header=0)

    # Step 2: Extract max points (row 3, index 2) as Series
    if len(full_df) < 3:
        return {"error": "CSV must have at least 3 rows (header, date, max points)."}

    max_points_row = full_df.iloc[2]

    # Step 3: Drop header+date+max points to get actual student data
    df = full_df.iloc[3:].reset_index(drop=True)

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

            # Validate score range
            if not (0 <= score <= 100):
                return {
                    "error": f"Invalid score {score} for assignment '{col}' for student '{student_number}'. Scores must be between 0 and 100."
                }

            # Upsert assignment with max points
            assignment = db.query(Assignment).filter_by(name=col).first()
            if not assignment:
                try:
                    max_point = float(max_points_row[col])
                except (ValueError, KeyError):
                    max_point = 100  # fallback default
                assignment = Assignment(name=col, max_points=max_point)
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



