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
from sqlalchemy import or_, func
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

        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        print("DEBUG: Original columns:", df.columns.tolist())

        if len(df) < 4:
            raise HTTPException(status_code=400, detail="CSV must have at least 4 rows")

        # Extract metadata rows
        date_row = df.iloc[0] if len(df) > 1 else None
        points_row = df.iloc[1] if len(df) > 2 else None
        student_df = df.iloc[2:].reset_index(drop=True)

        if len(student_df.columns) < 3:
            raise HTTPException(status_code=400, detail="CSV must have at least 3 columns")

        # Get original column names for assignments
        original_columns = df.columns.tolist()
        assignment_cols_original = original_columns[3:]  # Skip first 3 columns (student info)
        
        # Rename columns for easier processing
        new_column_names = ['last_name', 'first_name', 'email'] + assignment_cols_original
        student_df.columns = new_column_names

        print(f"DEBUG: Found {len(assignment_cols_original)} assignment columns")
        print(f"DEBUG: Assignment columns: {assignment_cols_original}")

        # Validate required columns
        required_columns = {'last_name', 'first_name', 'email'}
        if not required_columns.issubset(student_df.columns):
            missing = required_columns - set(student_df.columns)
            raise HTTPException(status_code=400, detail=f"Missing columns: {list(missing)}")

        total_students = len(student_df)
        processed_students = 0
        valid_assignments = []
        skipped_assignments = []

        # Process each assignment column
        for i, assignment_name in enumerate(assignment_cols_original):
            col_index_in_student_df = i + 3  # +3 because first 3 are student info
            col_index_in_original_df = i + 3  # Same index in original df
            
            try:
                # Check if we have max points for this assignment
                max_points_val = None
                if points_row is not None and col_index_in_original_df < len(points_row):
                    max_points_val = points_row.iloc[col_index_in_original_df]
                    
                # Skip assignments that don't have max points defined
                if pd.isna(max_points_val) or str(max_points_val).strip() == '':
                    print(f"DEBUG: Skipping assignment '{assignment_name}' - no max points defined")
                    skipped_assignments.append(assignment_name)
                    continue
                else:
                    try:
                        max_points_val = float(max_points_val)
                        print(f"DEBUG: Assignment '{assignment_name}' has max points: {max_points_val}")
                    except (ValueError, TypeError):
                        print(f"DEBUG: Skipping assignment '{assignment_name}' - invalid max points value: {max_points_val}")
                        skipped_assignments.append(assignment_name)
                        continue

                # Count non-empty grades (less strict check)
                assignment_col = student_df.iloc[:, col_index_in_student_df]
                non_empty_count = 0
                for value in assignment_col:
                    if pd.notna(value) and str(value).strip() != '' and str(value).strip().lower() != 'nan':
                        try:
                            float(value)  # Try to convert to number
                            non_empty_count += 1
                        except (ValueError, TypeError):
                            pass  # Skip non-numeric values

                print(f"DEBUG: Assignment '{assignment_name}' has {non_empty_count} valid grades out of {total_students} students")
                
                # More lenient threshold - accept assignments with at least 1 valid grade
                # or use a lower threshold (e.g., 10% instead of 30%)
                threshold = max(1, int(total_students * 0.1))  # Reduced from 0.3 to 0.1
                
                if non_empty_count >= threshold:
                    valid_assignments.append(assignment_name)
                    print(f"DEBUG: Assignment '{assignment_name}' is valid ({non_empty_count} >= {threshold})")
                else:
                    skipped_assignments.append(assignment_name)
                    print(f"DEBUG: Skipping assignment '{assignment_name}' - insufficient data ({non_empty_count} < {threshold})")
                    
            except Exception as e:
                print(f"DEBUG: Error processing assignment '{assignment_name}': {e}")
                skipped_assignments.append(assignment_name)
                continue

        print(f"DEBUG: Valid assignments: {len(valid_assignments)}")
        print(f"DEBUG: Skipped assignments: {len(skipped_assignments)}")

        if not valid_assignments:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "No assignments have sufficient data",
                    "total_students": total_students,
                    "threshold": max(1, int(total_students * 0.1)),
                    "all_assignments": assignment_cols_original,
                    "skipped_assignments": skipped_assignments
                }
            )

        # Process students and their grades
        for index, row in student_df.iterrows():
            email = str(row['email']).strip().lower()
            if not email or email == 'nan':
                print(f"DEBUG: Skipping row {index} - invalid email")
                continue

            processed_students += 1
            
            # Create or update student
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
            for assignment_name in valid_assignments:
                try:
                    # Get the score for this assignment
                    score_value = row[assignment_name]
                    
                    if pd.isna(score_value) or str(score_value).strip() == '' or str(score_value).strip().lower() == 'nan':
                        continue  # Skip empty scores
                    
                    try:
                        score = float(score_value)
                    except (ValueError, TypeError):
                        print(f"DEBUG: Invalid score '{score_value}' for {email}, {assignment_name}")
                        continue

                    # Get assignment metadata
                    assignment_index = assignment_cols_original.index(assignment_name)
                    original_col_index = assignment_index + 3  # +3 for student info columns

                    # Get assignment date
                    assignment_date = None
                    if date_row is not None and original_col_index < len(date_row):
                        date_val = date_row.iloc[original_col_index]
                        if pd.notna(date_val) and str(date_val).strip() != '':
                            try:
                                parsed_date = pd.to_datetime(date_val, errors='coerce')
                                if pd.notna(parsed_date):
                                    assignment_date = parsed_date.date()
                            except:
                                pass

                    # Get max points (we know it exists because we validated it above)
                    max_points = max_points_val  # Use the validated value from above
                    assignment_index = assignment_cols_original.index(assignment_name)
                    original_col_index = assignment_index + 3
                    if points_row is not None and original_col_index < len(points_row):
                        try:
                            max_val = points_row.iloc[original_col_index]
                            if pd.notna(max_val) and str(max_val).strip() != '':
                                max_points = float(max_val)
                        except (ValueError, TypeError):
                            # This shouldn't happen since we validated above, but just in case
                            max_points = max_points_val

                    # Find or create assignment
                    if assignment_date is None:
                        assignment = db.query(Assignment).filter(
                            and_(Assignment.name == assignment_name, Assignment.date.is_(None))
                        ).first()
                    else:
                        assignment = db.query(Assignment).filter_by(
                            name=assignment_name, date=assignment_date
                        ).first()

                    if not assignment:
                        assignment = Assignment(
                            name=assignment_name,
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
                        grade.score = score
                    else:
                        grade = Grade(
                            email=email,
                            assignment_id=assignment.id,
                            score=score
                        )
                        db.add(grade)

                except Exception as e:
                    print(f"DEBUG: Error processing grade for {email}, {assignment_name}: {e}")
                    continue

        db.commit()
        print("DEBUG: Upload committed successfully")

        return {
            "status": f"File {file.filename} uploaded and processed successfully",
            "total_students": total_students,
            "processed_students": processed_students,
            "total_assignments_found": len(assignment_cols_original),
            "valid_assignments": valid_assignments,
            "skipped_assignments": skipped_assignments,
            "processed_assignments": len(valid_assignments),
            "threshold_used": max(1, int(total_students * 0.1))
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

@app.get("/api/student/{email}")
def get_student_by_email(email: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(email=email.lower().strip()).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    grades_list = []
    for grade in student.grades:
        assignment = grade.assignment
        grades_list.append({
            "assignment": assignment.name,
            "date": assignment.date.isoformat() if assignment.date else None,
            "score": grade.score,
            "max_points": assignment.max_points
        })

    return {
        "email": student.email,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "grades": grades_list
    }

# Add these endpoints to your main.py file

@app.get("/api/search-students")
def search_students(query: str = "", db: Session = Depends(get_db)):
    """Search students by name or email"""
    try:
        students_query = db.query(Student)
        
        if query.strip():
            search_term = f"%{query.lower()}%"
            students_query = students_query.filter(
                or_(
                    func.lower(Student.first_name).like(search_term),
                    func.lower(Student.last_name).like(search_term),
                    func.lower(Student.email).like(search_term),
                    func.lower(func.concat(Student.first_name, ' ', Student.last_name)).like(search_term),
                    func.lower(func.concat(Student.last_name, ', ', Student.first_name)).like(search_term)
                )
            )
        
        students = students_query.all()
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
        
        return {
            "students": result,
            "total_found": len(result),
            "search_query": query
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching students: {str(e)}")

@app.get("/api/assignments")
def get_assignments(db: Session = Depends(get_db)):
    """Get all assignments"""
    try:
        assignments = db.query(Assignment).order_by(Assignment.date.asc(), Assignment.name.asc()).all()
        result = []
        
        for assignment in assignments:
            # Count students who have grades for this assignment
            grade_count = db.query(Grade).filter_by(assignment_id=assignment.id).count()
            
            result.append({
                "id": assignment.id,
                "name": assignment.name,
                "date": assignment.date.isoformat() if assignment.date else None,
                "max_points": assignment.max_points,
                "student_count": grade_count
            })
        
        return {"assignments": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving assignments: {str(e)}")

@app.get("/api/student/{email}")
def get_student_details(email: str, db: Session = Depends(get_db)):
    """Get detailed information for a specific student"""
    try:
        student = db.query(Student).filter_by(email=email.lower()).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        grades_list = []
        total_points = 0
        max_possible = 0
        
        for grade in student.grades:
            assignment = grade.assignment
            grade_info = {
                "assignment": assignment.name,
                "date": assignment.date.isoformat() if assignment.date else None,
                "max_points": assignment.max_points,
                "score": grade.score,
                "percentage": round((grade.score / assignment.max_points) * 100, 1) if assignment.max_points > 0 else 0
            }
            grades_list.append(grade_info)
            total_points += grade.score
            max_possible += assignment.max_points
        
        # Sort grades by date, then by assignment name
        grades_list.sort(key=lambda x: (x['date'] or '', x['assignment']))
        
        overall_percentage = round((total_points / max_possible) * 100, 1) if max_possible > 0 else 0
        
        return {
            "email": student.email,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "grades": grades_list,
            "total_assignments": len(grades_list),
            "total_points": total_points,
            "max_possible": max_possible,
            "overall_percentage": overall_percentage
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving student details: {str(e)}")

# Don't forget to add these imports at the top of your main.py file:
# from sqlalchemy import or_, func

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

