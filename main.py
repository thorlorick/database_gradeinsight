import io
import os
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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

Base.metadata.create_all(bind=engine)

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

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    csv_io = io.StringIO(contents.decode("utf-8"))

    df = pd.read_csv(csv_io, header=0)

    # Force rename first three columns
    new_cols = ['last_name', 'first_name', 'email'] + list(df.columns[3:])
    df.columns = new_cols

    required_columns = {'last_name', 'first_name', 'email'}
    if not required_columns.issubset(df.columns):
        return {"error": f"Missing required columns: {required_columns}"}

    # Process Date row (row 1) for assignments dates
    if len(df) > 1:
        date_row = df.iloc[1]
    else:
        date_row = None

    # Process Points row (row 2) for max points
    if len(df) > 2:
        points_row = df.iloc[2]
    else:
        points_row = None

    # Actual student data from row 3 onwards
    student_df = df.iloc[3:].reset_index(drop=True)

    for index, row in student_df.iterrows():
        email = str(row['email']).strip().lower()

        if not email:
            continue  # skip rows without email

        student = db.query(Student).filter_by(email=email).first()
        if student:
            student.first_name = row['first_name']
            student.last_name = row['last_name']
        else:
            student = Student(
                email=email,
                first_name=row['first_name'],
                last_name=row['last_name'],
            )
            db.add(student)

        for col in student_df.columns[3:]:
            score = row[col]
            if pd.isna(score):
                continue

            # Parse date from date_row if available and valid
            assignment_date = None
            if date_row is not None:
                date_val = date_row.get(col, None)
                if pd.notna(date_val):
                    try:
                        assignment_date = pd.to_datetime(date_val).date()
                    except Exception:
                        assignment_date = None

            # Parse max points from points_row if available
            max_points = 100.0
            if points_row is not None:
                max_val = points_row.get(col, None)
                if pd.notna(max_val):
                    try:
                        max_points = float(max_val)
                    except Exception:
                        max_points = 100.0

            assignment = (
                db.query(Assignment)
                .filter_by(name=col, date=assignment_date)
                .first()
            )
            if not assignment:
                assignment = Assignment(name=col, date=assignment_date, max_points=max_points)
                db.add(assignment)
                db.flush()

            grade = (
                db.query(Grade)
                .filter_by(email=email, assignment_id=assignment.id)
                .first()
            )
            if grade:
                grade.score = float(score)
            else:
                grade = Grade(email=email, assignment_id=assignment.id, score=float(score))
                db.add(grade)

    db.commit()
    return {"status": "Upload processed successfully"}

@app.get("/view-students")
def view_students(db: Session = Depends(get_db)):
    students = db.query(Student).all()
    result = []
    for s in students:
        result.append({
            "email": s.email,
            "first_name": s.first_name,
            "last_name": s.last_name,
        })
    return {"students": result}
