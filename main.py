import io
import os
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import Student, Assignment, Grade
from datetime import datetime

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

@app.get("/")
def read_root():
    return {"message": "Grade Insight is running"}

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
    return templates.TemplateResponse("upload_success.html", {"request": request, "filename": file.filename})

@app.get("/testdb")
def test_db():
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "Database connection successful"}
    except OperationalError as e:
        return {"status": "Database connection failed", "error": str(e)}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    csv_io = io.StringIO(contents.decode("utf-8"))

    # Read full CSV
    full_df = pd.read_csv(csv_io, header=0)

    if len(full_df) < 3:
        return {"error": "CSV must have at least 3 rows (header, date, max points)."}

    date_row = full_df.iloc[1]
    max_points_row = full_df.iloc[2]
    df = full_df.iloc[3:].reset_index(drop=True)

    required_columns = {"email", "first_name", "last_name"}
    if not required_columns.issubset(df.columns):
        return {"error": f"Missing required student columns: {required_columns}"}

    for _, row in df.iterrows():
        email = str(row["email"]).strip()
        if not email:
            continue

        # UPSERT STUDENT
        student = db.query(Student).filter_by(email=email).first()
        if student:
            student.first_name = row["first_name"]
            student.last_name = row["last_name"]
        else:
            student = Student(
                email=email,
                first_name=row["first_name"],
                last_name=row["last_name"],
            )
            db.add(student)

        # UPSERT ASSIGNMENTS & GRADES
        for col in df.columns:
            if col in required_columns:
                continue

            score = row[col]
            if pd.isna(score):
                continue

            try:
                score = float(score)
                if not (0 <= score <= 100):
                    continue
            except:
                continue

            # Get max points
            try:
                max_point = float(max_points_row[col])
            except (ValueError, KeyError):
                max_point = 100.0

            # Get optional date
            date_str = str(date_row.get(col, "")).strip()
            try:
                date_obj = pd.to_datetime(date_str).date() if date_str else None
            except:
                date_obj = None

            # Use assignment name + optional date to uniquely identify
            assignment = db.query(Assignment).filter_by(name=col, date=date_obj).first()
            if not assignment:
                assignment = Assignment(name=col, max_points=max_point, date=date_obj)
                db.add(assignment)
                db.flush()

            # UPSERT grade
            grade = db.query(Grade).filter_by(email=email, assignment_id=assignment.id).first()
            if grade:
                grade.score = score
            else:
                grade = Grade(email=email, assignment_id=assignment.id, score=score)
                db.add(grade)

    db.commit()
    return {"status": "Upload processed successfully"}

@app.get("/view-students")
def view_students(db: Session = Depends(get_db)):
    students = db.query(Student).all()
    return {"students": [s.email for s in students]}

#@app.get("/reset-db")
#def reset_db():
 #   Base.metadata.drop_all(bind=engine)
  #  Base.metadata.create_all(bind=engine)
   # return {"status": "Database reset (GET)"}



