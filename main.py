import io
import os
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Depends, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import Student, Assignment, Grade
from datetime import datetime
from sqlalchemy import and_
import traceback

app = FastAPI()

# Make sure templates and static directories exist
if not os.path.exists("templates"):
    os.makedirs("templates")
if not os.path.exists("static"):
    os.makedirs("static")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add error handling for database creation
try:
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")
except Exception as e:
    print(f"Error creating database tables: {e}")

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
        return JSONResponse(
            status_code=404,
            content={"error": "Template file not found."}
        )

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
                <input name="file" type="file" accept=".csv">
                <input type="submit" value="Upload">
            </form>
        </body>
    </html>
    """

@app.post("/upload")
async def handle_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        contents = await file.read()
        print("DEBUG: File received:", file.filename)

        # Better CSV parsing with error handling
        try:
            csv_io = io.StringIO(contents.decode("utf-8"))
            df = pd.read_csv(csv_io, header=0)
        except UnicodeDecodeError:
            # Try different encoding
            csv_io = io.StringIO(contents.decode("latin-1"))
            df = pd.read_csv(csv_io, header=0)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading CSV file: {str(e)}")

        print("DEBUG: CSV loaded successfully")
        print("DEBUG: CSV shape:", df.shape)
        
        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file is empty")
        
        # Strip whitespace from headers
        df.columns = [str(col).strip() for col in df.columns]
        print("DEBUG: Original columns:", df.columns.tolist())

        # Validate minimum rows
        if len(df) < 4:  # Need at least header + date + points + 1 student
            raise HTTPException(status_code=400, detail="CSV must have at least 4 rows (header, dates, points, and at least one student)")

        # Row indices: 0=headers, 1=dates, 2=points, 3+=students
        date_row = df.iloc[1] if len(df) > 1 else None
        points_row = df.iloc[2] if len(df) > 2 else None
        student_df = df.iloc[3:].reset_index(drop=True)

        if len(student_df.columns) < 3:
            raise HTTPException(status_code=400, detail="CSV file must have at least 3 columns (last_name, first_name, email)")

        # Only rename first 3 columns, preserve assignment column names exactly
        original_assignment_cols = list(student_df.columns[3:])
        student_df.columns = ['last_name', 'first_name', 'email'] + original_assignment_cols

        print("DEBUG: Renamed columns:", student_df.columns.tolist())

        # Validate required columns
        required_columns = {'last_name', 'first_name', 'email'}
        if not required_columns.issubset(student_df.columns):
            missing = required_columns - set(student_df.columns)
            raise HTTPException(status_code=400, detail=f"Missing required columns: {list(missing)}")

        print("DEBUG: Processing", len(student_df), "students")

        # Debug points row
    if points_row is not None:
    points_row_index = df[df.iloc[:, 0] == 'Points'].index[0]  # Get actual row index
    print(f"DEBUG: Points row (Row {points_row_index + 1}, index {points_row_index}):")
    
    assignment_columns = df.columns[3:]  # Assignment columns start at index 3
    for col_idx, col in enumerate(assignment_columns):
        try:
            val = points_row.iloc[3 + col_idx]  # Access correct column in points_row
            if pd.isna(val) or str(val).strip() == '':
                print(f"  {col}: BLANK (will use default 100.0)")
            else:
                print(f"  {col}: '{val}' (type: {type(val)})")
        except Exception as e:
            print(f"  {col}: ERROR accessing - {e}")

        total_students = len(student_df)
        threshold = max(1, int(total_students * 0.3))
        valid_assignments = []
        skipped_assignments = []

        # Debug: Show the points row values
        if points_row is not None:
            print("DEBUG: Points row values:")
            for i, val in enumerate(points_row):
                col_name = df.columns[i] if i < len(df.columns) else f"Column_{i}"
                print(f"  Index {i} ({col_name}): '{val}' (type: {type(val)})")

        # Process assignments (skip first 3 columns: last_name, first_name, email)
        assignment_columns = student_df.columns[3:]  # Only assignment columns
        print(f"DEBUG: Assignment columns to check: {list(assignment_columns)}")
        
        for col in assignment_columns:
            # Get the original column index in the DataFrame
            original_col_index = list(df.columns).index(col) if col in df.columns else None
            if original_col_index is None:
                print(f"DEBUG: Skipping '{col}' - column not found in original data")
                skipped_assignments.append(col)
                continue
                
            print(f"DEBUG: Checking '{col}' at original index {original_col_index}")
                
            # Check if max points in points_row is valid
            # Note: B3 and C3 (first_name, email columns) should be ignored for points check
            max_points_val = None
            try:
                if points_row is not None and original_col_index < len(points_row):
                    max_points_val = points_row.iloc[original_col_index]
                    print(f"DEBUG: '{col}' max_points_val from index {original_col_index}: '{max_points_val}' (type: {type(max_points_val)})")
                    
                    if pd.isna(max_points_val) or str(max_points_val).strip() == '':
                        print(f"DEBUG: Skipping '{col}' - no max points specified (intentionally blank in row 3)")
                        skipped_assignments.append(col)
                        continue
                    else:
                        print(f"DEBUG: '{col}' has max points: {max_points_val}")
                else:
                    print(f"DEBUG: Skipping '{col}' - points row not available or index out of range")
                    skipped_assignments.append(col)
                    continue
            except Exception as e:
                print(f"DEBUG: Skipping '{col}' due to error accessing max points: {e}")
                skipped_assignments.append(col)
                continue

            # Apply 30% threshold
            non_empty_count = student_df[col].notna().sum()
            print(f"DEBUG: '{col}' has {non_empty_count} non-empty grades out of {total_students} students")
            if non_empty_count >= threshold:
                valid_assignments.append(col)
                print(f"DEBUG: '{col}' is valid ({non_empty_count}/{total_students} students have grades)")
            else:
                skipped_assignments.append(col)
                print(f"DEBUG: Skipping '{col}' - only {non_empty_count}/{total_students} students have grades (below {threshold} threshold)")

        if not valid_assignments:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "No assignments meet the 30% threshold requirement",
                    "total_students": total_students,
                    "threshold": threshold,
                    "skipped_assignments": skipped_assignments
                }
            )

        processed_students = 0

        # Process students
        for index, row in student_df.iterrows():
            email = str(row['email']).strip().lower()
            if not email or email == 'nan':
                print(f"DEBUG: Skipping row {index} - no valid email")
                continue
            
            processed_students += 1

            # Get or create student
            student = db.query(Student).filter_by(email=email).first()
            if student:
                student.first_name = str(row['first_name']).strip()
                student.last_name = str(row['last_name']).strip()
            else:
                student = Student(
                    email=email, 
                    first_name=str(row['first_name']).strip(), 
                    last_name=str(row['last_name']).strip()
                )
                db.add(student)

            # Process grades for valid assignments
            for col in valid_assignments:
                try:
                    score = row[col]
                    if pd.isna(score):
                        continue

                    # Get assignment date
                    assignment_date = None
                    original_col_index = list(df.columns).index(col) if col in df.columns else None
                    
                    if date_row is not None and original_col_index is not None and original_col_index < len(date_row):
                        try:
                            date_val = date_row.iloc[original_col_index]
                            if pd.notna(date_val) and str(date_val).strip() != '':
                                parsed_date = pd.to_datetime(date_val, errors='coerce')
                                if pd.notna(parsed_date):
                                    assignment_date = parsed_date.date()
                                    # Skip epoch dates
                                    if assignment_date == datetime(1970, 1, 1).date():
                                        assignment_date = None
                        except Exception as e:
                            print(f"DEBUG: Date parsing error for '{col}': {e}")

                    # Get max points
                    max_points = 100.0
                    if points_row is not None and original_col_index is not None and original_col_index < len(points_row):
                        try:
                            max_val = points_row.iloc[original_col_index]
                            if pd.notna(max_val) and str(max_val).strip() != '':
                                max_points = float(max_val)
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG: Could not parse max points for '{col}': {e}")

                    # Get or create assignment
                    if assignment_date is None:
                        assignment = db.query(Assignment).filter(
                            and_(Assignment.name == col, Assignment.date.is_(None))
                        ).first()
                    else:
                        assignment = db.query(Assignment).filter_by(
                            name=col, date=assignment_date
                        ).first()

                    if not assignment:
                        assignment = Assignment(
                            name=col, 
                            date=assignment_date, 
                            max_points=max_points
                        )
                        db.add(assignment)
                        db.flush()  # Get the ID

                    # Create or update grade
                    grade = db.query(Grade).filter_by(
                        email=email, 
                        assignment_id=assignment.id
                    ).first()
                    
                    if grade:
                        grade.score = float(score)
                    else:
                        grade = Grade(
                            email=email, 
                            assignment_id=assignment.id, 
                            score=float(score)
                        )
                        db.add(grade)
                        
                except Exception as e:
                    print(f"DEBUG: Error processing grade for {email}, {col}: {e}")
                    continue

        # Commit all changes
        db.commit()
        print("DEBUG: Upload committed to DB successfully")

        return {
            "status": f"File {file.filename} uploaded and processed successfully",
            "total_students": total_students,
            "processed_students": processed_students,
            "threshold": threshold,
            "valid_assignments": valid_assignments,
            "skipped_assignments": skipped_assignments,
            "processed_assignments": len(valid_assignments)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Unexpected error in upload: {e}")
        print(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/view-students")
def view_students(db: Session = Depends(get_db)):
    try:
        students = db.query(Student).all()
        result = []
        for s in students:
            result.append({
                "email": s.email,
                "first_name": s.first_name,
                "last_name": s.last_name,
            })
        return {"students": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving students: {str(e)}")

@app.get("/view-grades")
def view_grades(db: Session = Depends(get_db)):
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving grades: {str(e)}")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading dashboard: {str(e)}")

@app.get("/students", response_class=HTMLResponse)
async def students_page(request: Request):
    try:
        return templates.TemplateResponse("students.html", {"request": request})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading students page: {str(e)}")

@app.get("/api/grades-table")
def get_grades_for_table(db: Session = Depends(get_db)):
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving grades table: {str(e)}")

@app.get("/api/students")
def get_students_list(db: Session = Depends(get_db)):
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving students list: {str(e)}")

@app.get("/reset-db")
def reset_db():
    db = SessionLocal()
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return {"status": "Database reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting database: {str(e)}")
    finally:
        db.close()

# Add a health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
