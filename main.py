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
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")

        contents = await file.read()
        print("DEBUG: File received:", file.filename)

        try:
            csv_io = io.StringIO(contents.decode("utf-8"))
            df = pd.read_csv(csv_io, header=0)
        except UnicodeDecodeError:
            csv_io = io.StringIO(contents.decode("latin-1"))
            df = pd.read_csv(csv_io, header=0)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading CSV file: {str(e)}")

        print("DEBUG: CSV loaded successfully")
        print("DEBUG: CSV shape:", df.shape)

        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        df.columns = [str(col).strip() for col in df.columns]
        print("DEBUG: Original columns:", df.columns.tolist())

        if len(df) < 4:
            raise HTTPException(status_code=400, detail="CSV must have at least 4 rows")

        date_row = df.iloc[0] if len(df) > 1 else None
        points_row = df.iloc[1] if len(df) > 2 else None
        student_df = df.iloc[2:].reset_index(drop=True)

        if len(student_df.columns) < 3:
            raise HTTPException(status_code=400, detail="CSV must have at least 3 columns")

        original_assignment_cols = list(student_df.columns[3:])
        student_df.columns = ['last_name', 'first_name', 'email'] + original_assignment_cols

        required_columns = {'last_name', 'first_name', 'email'}
        if not required_columns.issubset(student_df.columns):
            missing = required_columns - set(student_df.columns)
            raise HTTPException(status_code=400, detail=f"Missing columns: {list(missing)}")

        print("DEBUG: Processing", len(student_df), "students")

        total_students = len(student_df)
        threshold = max(1, int(total_students * 0.3))
        valid_assignments = []
        skipped_assignments = []

        assignment_columns = student_df.columns[3:]
        print(f"DEBUG: Assignment columns to check: {list(assignment_columns)}")

        for col in assignment_columns:
            original_col_index = list(df.columns).index(col) if col in df.columns else None
            if original_col_index is None:
                print(f"DEBUG: Skipping '{col}' - column not found")
                skipped_assignments.append(col)
                continue

            max_points_val = None
            try:
                if points_row is not None and original_col_index < len(points_row):
                    max_points_val = points_row.iloc[original_col_index]
                    if pd.isna(max_points_val) or str(max_points_val).strip() == '':
                        print(f"DEBUG: Skipping '{col}' - no max points")
                        skipped_assignments.append(col)
                        continue
                    else:
                        print(f"DEBUG: '{col}' has max points: {max_points_val}")
                else:
                    print(f"DEBUG: Skipping '{col}' - no points row")
                    skipped_assignments.append(col)
                    continue
            except Exception as e:
                print(f"DEBUG: Skipping '{col}' - error: {e}")
                skipped_assignments.append(col)
                continue

            # Count non-empty numeric scores for this assignment
            non_empty_count = student_df[col].apply(lambda x: isinstance(x, (int, float)) and not pd.isna(x)).sum()
            if non_empty_count >= threshold:
                valid_assignments.append(col)
                print(f"DEBUG: '{col}' is valid")
            else:
                skipped_assignments.append(col)
                print(f"DEBUG: Skipping '{col}' - below threshold")

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

        for index, row in student_df.iterrows():
            email = str(row['email']).strip().lower()
            if not email or email == 'nan':
                print(f"DEBUG: Skipping row {index} - no email")
                continue

            processed_students += 1
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

            for col in valid_assignments:
                try:
                    score = row[col]
                    if pd.isna(score):
                        continue

                    assignment_date = None
                    original_col_index = list(df.columns).index(col) if col in df.columns else None

                    if date_row is not None and original_col_index is not None and original_col_index < len(date_row):
                        date_val = date_row.iloc[original_col_index]
                        if pd.notna(date_val) and str(date_val).strip() != '':
                            parsed_date = pd.to_datetime(date_val, errors='coerce')
                            if pd.notna(parsed_date) and parsed_date.date() != datetime(1970, 1, 1).date():
                                assignment_date = parsed_date.date()

                    max_points = 100.0
                    if points_row is not None and original_col_index is not None and original_col_index < len(points_row):
                        try:
                            max_val = points_row.iloc[original_col_index]
                            if pd.notna(max_val) and str(max_val).strip() != '':
                                max_points = float(max_val)
                        except (ValueError, TypeError):
                            pass

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
                        db.flush()

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

        db.commit()
        print("DEBUG: Upload committed successfully")

        return {
            "status": f"File {file.filename} uploaded and processed",
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

