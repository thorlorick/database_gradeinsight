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

    # Debug: Show the first few rows to understand CSV structure
    print("DEBUG: CSV first 5 rows:")
    for i in range(min(5, len(df))):
        print(f"  Row {i}: {df.iloc[i].to_dict()}")
    
    date_row = df.iloc[1] if len(df) > 1 else None
    points_row = df.iloc[2] if len(df) > 2 else None
    student_df = df.iloc[3:].reset_index(drop=True)

    print("DEBUG: Processing", len(student_df), "students")
    
    # Debug: Print the points row to see what we're working with
    if points_row is not None:
        print("DEBUG: Points row (Row 3, index 2) data:")
        for col in df.columns[3:]:
            val = points_row.get(col, 'N/A')
            print(f"  {col}: '{val}' (type: {type(val)})")
    else:
        print("DEBUG: No points row found in CSV")

    # Calculate threshold (30% of students)
    total_students = len(student_df)
    threshold = max(1, int(total_students * 0.3))  # At least 1 student, or 30%
    print(f"DEBUG: Total students: {total_students}, Threshold: {threshold}")

    # Check each assignment column for data sufficiency
    valid_assignments = []
    skipped_assignments = []
    
    for col in student_df.columns[3:]:  # Skip first 3 columns (name, email)
        # Count non-null, non-empty values in this assignment column
        non_empty_count = student_df[col].notna().sum()
        
        if non_empty_count >= threshold:
            valid_assignments.append(col)
            print(f"DEBUG: Assignment '{col}' has {non_empty_count} entries - VALID")
        else:
            skipped_assignments.append(col)
            print(f"DEBUG: Assignment '{col}' has {non_empty_count} entries - SKIPPED (below threshold)")

    if not valid_assignments:
        return {
            "error": "No assignments meet the 30% threshold requirement",
            "total_students": total_students,
            "threshold": threshold,
            "skipped_assignments": skipped_assignments
        }

    # Process students
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

        # Only process valid assignments
        for col in valid_assignments:
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
                print(f"DEBUG: Raw max_val for '{col}': '{max_val}' (type: {type(max_val)})")
                
                if pd.notna(max_val) and str(max_val).strip() != '':
                    try:
                        # Convert to string first, then to float to handle any data type
                        max_val_str = str(max_val).strip()
                        
                        # Check if it looks like a valid number (not a name or text)
                        if max_val_str.replace('.', '').replace('-', '').isdigit():
                            max_points = float(max_val_str)
                            print(f"DEBUG: Assignment '{col}' max points set to: {max_points}")
                        else:
                            print(f"DEBUG: '{max_val_str}' doesn't look like a number for '{col}', using default 100.0")
                            max_points = 100.0
                    except (ValueError, TypeError) as e:
                        print(f"DEBUG: Could not convert max_val '{max_val}' to float for '{col}': {e}")
                        max_points = 100.0
                else:
                    print(f"DEBUG: No valid max points found for '{col}' (value was None/NaN/empty), using default 100.0")
            else:
                print(f"DEBUG: No points row found, using default 100.0 for '{col}'")

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
    
    return {
        "status": f"File {file.filename} uploaded and processed",
        "total_students": total_students,
        "threshold": threshold,
        "valid_assignments": valid_assignments,
        "skipped_assignments": skipped_assignments,
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

# Add these new routes to your main.py file (add them after your existing routes)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/students", response_class=HTMLResponse)
async def students_page(request: Request):
    """Students list page"""
    return templates.TemplateResponse("students.html", {"request": request})

@app.get("/api/grades-table")
def get_grades_for_table(db: Session = Depends(get_db)):
    """API endpoint to get grades formatted for table display"""
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
    """API endpoint to get just the students list"""
    students = db.query(Student).all()
    result = []
    
    for student in students:
        # Calculate some basic stats
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
