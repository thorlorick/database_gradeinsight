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
    
    # Strip whitespace from headers
    df.columns = [str(col).strip() for col in df.columns]
    print("DEBUG: CSV shape:", df.shape)
    print("DEBUG: Original columns:", df.columns.tolist())

    date_row = df.iloc[1] if len(df) > 1 else None
    points_row = df.iloc[2] if len(df) > 2 else None
    student_df = df.iloc[3:].reset_index(drop=True)

    if len(student_df.columns) < 3:
        return {"error": "CSV file must have at least 3 columns (last_name, first_name, email)"}

    # Only rename first 3 columns, preserve assignment column names exactly
    original_assignment_cols = list(student_df.columns[3:])
    student_df.columns = ['last_name', 'first_name', 'email'] + original_assignment_cols

    print("DEBUG: Renamed columns:", student_df.columns.tolist())

    required_columns = {'last_name', 'first_name', 'email'}
    if not required_columns.issubset(student_df.columns):
        return {"error": f"Missing required columns: {required_columns}"}

    print("DEBUG: Processing", len(student_df), "students")

    if points_row is not None:
        print("DEBUG: Points row (Row 3, index 2) data:")
        print("DEBUG: B3 and C3 are expected to be blank (metadata row)")
        for col in df.columns[3:]:
            try:
                val = points_row[col] if col in points_row.index else 'N/A'
                if pd.isna(val) or str(val).strip() == '':
                    print(f"  {col}: BLANK (will use default 100.0)")
                else:
                    print(f"  {col}: '{val}' (type: {type(val)})")
            except Exception as e:
                print(f"  {col}: ERROR accessing - {e}")
    else:
        print("DEBUG: No points row found in CSV")

    total_students = len(student_df)
    threshold = max(1, int(total_students * 0.3))
    valid_assignments = []
    skipped_assignments = []

    for col in student_df.columns[3:]:
        non_empty_count = student_df[col].notna().sum()
        if non_empty_count >= threshold:
            valid_assignments.append(col)
        else:
            skipped_assignments.append(col)

    if not valid_assignments:
        return {
            "error": "No assignments meet the 30% threshold requirement",
            "total_students": total_students,
            "threshold": threshold,
            "skipped_assignments": skipped_assignments
        }

    # Build column mapping (student_df column -> original df column)
    col_mapping = {}
    for i, assignment_col in enumerate(student_df.columns[3:]):
        original_col_index = i + 3
        if original_col_index < len(df.columns):
            original_col = df.columns[original_col_index]
            col_mapping[assignment_col] = original_col
            print(f"DEBUG: Mapping '{assignment_col}' -> '{original_col}'")

    for index, row in student_df.iterrows():
        email = str(row['email']).strip().lower()
        if not email:
            continue

        student = db.query(Student).filter_by(email=email).first()
        if student:
            student.first_name = row['first_name']
            student.last_name = row['last_name']
        else:
            student = Student(email=email, first_name=row['first_name'], last_name=row['last_name'])
            db.add(student)

        for col in valid_assignments:
            score = row[col]
            if pd.isna(score):
                continue

            # Get original column name for metadata lookup
            original_col = col_mapping.get(col, col)

            assignment_date = None
            if date_row is not None and original_col in date_row.index:
                try:
                    date_val = date_row[original_col]
                    if pd.notna(date_val) and str(date_val).strip() != '':
                        parsed_date = pd.to_datetime(date_val, errors='coerce')
                        if pd.notna(parsed_date):
                            assignment_date = parsed_date.date()
                            if assignment_date == datetime(1970, 1, 1).date():
                                assignment_date = None
                except Exception as e:
                    print(f"DEBUG: Date parsing error for '{col}': {e}")

            max_points = 100.0
            if points_row is not None and original_col in points_row.index:
                try:
                    max_val = points_row[original_col]
                    if pd.notna(max_val) and str(max_val).strip() != '':
                        max_points = float(max_val)
                        print(f"DEBUG: Assignment '{col}' max points: {max_points}")
                    else:
                        print(f"DEBUG: No max points for '{col}', using default 100.0")
                except (ValueError, TypeError) as e:
                    print(f"DEBUG: Could not parse max points for '{col}': {e}")

            if assignment_date is None:
                assignment = db.query(Assignment).filter(and_(Assignment.name == col, Assignment.date.is_(None))).first()
            else:
                assignment = db.query(Assignment).filter_by(name=col, date=assignment_date).first()

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

    return {
        "status": f"File {file.filename} uploaded and processed",
        "total_students": total_students,
        "threshold": threshold,
        "valid_assignments": valid_assignments,
        "skipped_assignments": skipped_assignments,  # Fixed typo
        "processed_assignments": len(valid_assignments)
    }
    

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

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/students", response_class=HTMLResponse)
async def students_page(request: Request):
    return templates.TemplateResponse("students.html", {"request": request})

@app.get("/api/grades-table")
def get_grades_for_table(db: Session = Depends(get_db)):
    students = db.query(Student).all()
    result = []
    for student in students:
        grades_list = []
        for grade in student.grades:
            assignment = grade.assignment
            grades_list.append({
                "assignment": assignment.name,
                "date": assignment.date.isoformat() if assignment.date else None,
                "max_points": assignment.max_points,
                "score": grade.score,
            })
        result.append({
            "email": student.email,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "grades": grades_list,
        })
    return {"students": result}

@app.get("/api/students")
def get_students_list(db: Session = Depends(get_db)):
    students = db.query(Student).all()
    result = []
    for student in students:
        total_grades = len(student.grades)
        total_points = sum(grade.score for grade in student.grades)
        max_possible = sum(grade.assignment.max_points for grade in student.grades)
        avg_percentage = (total_points / max_possible * 100) if max_possible > 0 else 0
        result.append({
            "email": student.email,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "total_assignments": total_grades,
            "total_points": total_points,
            "max_possible": max_possible,
            "average_percentage": round(avg_percentage, 1)
        })
    return {"students": result}

@app.get("/reset-db")
def reset_db():
    db = SessionLocal()
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return {"status": "Database reset (GET)"}
    finally:
        db.close()
