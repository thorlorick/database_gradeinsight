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
from sqlalchemy import and_

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
async def upload_form():
    return """
    <html>
        <head>
            <title>Upload CSV</title>
        </head>
        <body>
            <h1>Upload CSV File</h1>
            <form action="/upload" enctype="multipart/form-data" method="post">
                <input name="file" type="file">
                <input type="submit">
            </form>
        </body>
    </html>
    """

@app.post("/upload")
async def handle_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    print("DEBUG: File received:", file.filename)

    csv_io = io.StringIO(contents.decode("utf-8"))
    df = pd.read_csv(csv_io, header=0)
    print("DEBUG: CSV shape:", df.shape)

    # Rename first 3 columns
    new_cols = ['last_name', 'first_name', 'email'] + list(df.columns[3:])
    df.columns = new_cols
    print("DEBUG: Renamed columns:", df.columns.tolist())

    required_columns = {'last_name', 'first_name', 'email'}
    if not required_columns.issubset(df.columns):
        return {"error": f"Missing required columns: {required_columns}"}

    date_row = df.iloc[1] if len(df) > 1 else None
    points_row = df.iloc[2] if len(df) > 2 else None
    student_df = df.iloc[3:].reset_index(drop=True)

    print("DEBUG: Processing", len(student_df), "students")

    for index, row in student_df.iterrows():
        email = str(row['email']).strip().lower()
        if not email:
            print(f"DEBUG: Skipping row {index} with no email")
            continue

        print(f"DEBUG: Processing student {email}")

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

            # Handle date with possible missing/invalid values
            assignment_date = None
            if date_row is not None:
                date_val = date_row.get(col, None)
                if pd.notna(date_val):
                    try:
                        parsed_date = pd.to_datetime(date_val, errors='coerce')
                        if pd.isna(parsed_date):
                            assignment_date = None
                        else:
                            assignment_date = parsed_date.date()
                            # Convert 1970-01-01 to None explicitly
                            if assignment_date == datetime(1970, 1, 1).date():
                                assignment_date = None
                    except Exception:
                        assignment_date = None

            max_points = 100.0
            if points_row is not None:
                max_val = points_row.get(col, None)
                if pd.notna(max_val):
                    try:
                        max_points = float(max_val)
                    except Exception:
                        max_points = 100.0

            # Query assignment with proper null handling for date
            if assignment_date is None:
                assignment = db.query(Assignment).filter(
                    and_(
                        Assignment.name == col,
                        Assignment.date.is_(None)
                    )
                ).first()
            else:
                assignment = db.query(Assignment).filter_by(
                    name=col,
                    date=assignment_date
                ).first()

            if not assignment:
                assignment = Assignment(name=col, date=assignment_date, max_points=max_points)
                db.add(assignment)
                db.flush()

            grade = db.query(Grade).filter_by(email=email, assignment_id=assignment.id).first()
            if grade:
                grade.score = float(score)
            else:
                grade = Grade(email=email, assignment_id=assignment.id, score=float(score))
                db.add(grade)

    db.commit()
    print("DEBUG: Upload committed to DB.")
    return {"status": f"File {file.filename} uploaded and processed"}




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


@app.get("/view-grades")
def view_grades(db: Session = Depends(get_db)):
    students = db.query(Student).all()
    result = []
    for s in students:
        grades_list = []
        for grade in s.grades:
            assignment = grade.assignment
            grades_list.append({
                "assignment": assignment.name,
                "date": assignment.date.isoformat() if assignment.date else None,
                "score": grade.score,
                "max_points": assignment.max_points,
            })
        result.append({
            "email": s.email,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "grades": grades_list,
        })
    return {"students": result}


@app.get("/reset-db")
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return {"status": "Database reset (GET)"}
