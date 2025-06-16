import io
import os
import pandas as pd
import traceback
from fastapi import FastAPI, UploadFile, File, Depends, Request, HTTPException, APIRouter
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import Student, Assignment, Grade, Tag
from datetime import datetime
from sqlalchemy import and_
from sqlalchemy import or_, func
from pydantic import BaseModel
from typing import List, Optional
from downloadTemplate import router as downloadTemplate_router

# Pydantic models for request bodies
class TagCreate(BaseModel):
    name: str
    color: Optional[str] = '#3B82F6'
    description: Optional[str] = None

class TagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None

class AssignmentTagUpdate(BaseModel):
    tag_ids: List[int]

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
async def root():
    return RedirectResponse(url="/dashboard")

app.include_router(downloadTemplate_router) #trying to refactor endpoints. this one is to download the template from the dashboard


@app.get("/upload", response_class=HTMLResponse)
async def upload_form():
    return """
    <html>
        <head>
            <title>Upload CSV</title>
        </head>
        <body>
            <h1>Upload CSV File</h1>
            <form id="uploadForm">
                <input id="fileInput" name="file" type="file" accept=".csv" required>
                <input type="submit" value="Upload">
            </form>

            <div id="loadingMessage" style="display:none; margin-top:1rem; font-weight:bold;">
                Uploading... please wait.
            </div>

            <script>
                const form = document.getElementById('uploadForm');
                const loadingMessage = document.getElementById('loadingMessage');
                const fileInput = document.getElementById('fileInput');

                form.addEventListener('submit', async function(event) {
                    event.preventDefault();
                    loadingMessage.style.display = 'block';

                    const formData = new FormData();
                    formData.append('file', fileInput.files[0]);

                    try {
                        const response = await fetch('/upload', {
                            method: 'POST',
                            body: formData,
                        });
                        if (!response.ok) throw new Error('Upload failed');
                        window.location.href = '/dashboard';  // redirect to dashboard
                    } catch (err) {
                        loadingMessage.textContent = 'Upload failed. Please try again.';
                    }
                });
            </script>
        </body>
    </html>
    """

# Add this route to your main.py file to fix the student portal navigation

@app.get("/student-portal", response_class=HTMLResponse)
async def student_portal_redirect(request: Request):
    """Main student portal route that matches the navigation link"""
    try:
        return templates.TemplateResponse("student-portal.html", {"request": request})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading student portal: {str(e)}")


@app.get("/teacher-student-view", response_class=HTMLResponse)
async def teacher_student_view(request: Request):  # Fixed function name
    """Main teacher-student-view that matches the navigation link"""
    try:
        return templates.TemplateResponse("teacher-student-view.html", {"request": request})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading teacher student view: {str(e)}")

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
                    valid_assignments.append((assignment_name, max_points_val))  # Store as tuple
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
            for assignment_name, max_points_val in valid_assignments:  # Unpack tuple
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

                    # Get assignment date
                    assignment_index = assignment_cols_original.index(assignment_name)
                    original_col_index = assignment_index + 3  # +3 for student info columns

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
                            max_points=max_points_val  # Use the validated value
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
            "valid_assignments": [name for name, _ in valid_assignments],  # Extract names
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
    total_points = 0
    max_possible = 0

    for grade in student.grades:
        assignment = grade.assignment
        if assignment:
            score = grade.score or 0
            max_pts = assignment.max_points or 0
            total_points += score
            max_possible += max_pts

            grades_list.append({
                "assignment": assignment.name,
                "date": assignment.date.isoformat() if assignment.date else None,
                "score": score,
                "max_points": max_pts
            })

    overall_percentage = (total_points / max_possible * 100) if max_possible > 0 else 0

    return {
        "email": student.email,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "total_points": total_points,
        "max_possible": max_possible,
        "overall_percentage": overall_percentage,
        "total_assignments": len(grades_list),
        "grades": grades_list
    }


# Enhanced search endpoints with tags support

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
    """Get all assignments with their tags"""
    try:
        assignments = db.query(Assignment).order_by(Assignment.date.asc(), Assignment.name.asc()).all()
        result = []
        
        for assignment in assignments:
            # Count students who have grades for this assignment
            grade_count = db.query(Grade).filter_by(assignment_id=assignment.id).count()
            
            # Get tags for this assignment - with error handling
            tags = []
            try:
                for tag in assignment.tags:
                    tags.append({
                        "id": tag.id,
                        "name": tag.name,
                        "color": tag.color,
                        "description": tag.description
                    })
            except Exception as tag_error:
                print(f"Error getting tags for assignment {assignment.id}: {tag_error}")
                tags = []  # Continue without tags if there's an error
            
            result.append({
                "id": assignment.id,
                "name": assignment.name,
                "date": assignment.date.isoformat() if assignment.date else None,
                "max_points": assignment.max_points,
                "description": getattr(assignment, 'description', None),  # Safe attribute access
                "student_count": grade_count,
                "tags": tags
            })
        
        return {"assignments": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving assignments: {str(e)}")

# New Tag Management Endpoints

@app.get("/api/tags")
def get_all_tags(db: Session = Depends(get_db)):
    """Get all available tags"""
    try:
        tags = db.query(Tag).order_by(Tag.name).all()
        result = []
        
        for tag in tags:
            # Safe access to assignments count
            assignment_count = 0
            try:
                assignment_count = len(tag.assignments) if hasattr(tag, 'assignments') else 0
            except Exception:
                assignment_count = 0
                
            result.append({
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description,
                "assignment_count": assignment_count
            })
        
        return {"tags": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tags: {str(e)}")

@app.post("/api/tags")
def create_tag(tag_data: TagCreate, db: Session = Depends(get_db)):
    """Create a new tag"""
    try:
        # Check if tag name already exists
        existing_tag = db.query(Tag).filter_by(name=tag_data.name.strip()).first()
        if existing_tag:
            raise HTTPException(status_code=400, detail="Tag name already exists")
        
        new_tag = Tag(
            name=tag_data.name.strip(),
            color=tag_data.color,
            description=tag_data.description
        )
        
        db.add(new_tag)
        db.commit()
        db.refresh(new_tag)
        
        return {
            "id": new_tag.id,
            "name": new_tag.name,
            "color": new_tag.color,
            "description": new_tag.description,
            "assignment_count": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating tag: {str(e)}")

@app.put("/api/tags/{tag_id}")
def update_tag(tag_id: int, tag_data: TagUpdate, db: Session = Depends(get_db)):
    """Update an existing tag"""
    try:
        tag = db.query(Tag).filter_by(id=tag_id).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        # Check if new name already exists (if name is being changed)
        if tag_data.name and tag_data.name.strip() != tag.name:
            existing_tag = db.query(Tag).filter_by(name=tag_data.name.strip()).first()
            if existing_tag:
                raise HTTPException(status_code=400, detail="Tag name already exists")
        
        # Update fields
        if tag_data.name:
            tag.name = tag_data.name.strip()
        if tag_data.color:
            tag.color = tag_data.color
        if tag_data.description is not None:
            tag.description = tag_data.description
        
        db.commit()
        db.refresh(tag)
        
        # Safe access to assignments count
        assignment_count = 0
        try:
            assignment_count = len(tag.assignments) if hasattr(tag, 'assignments') else 0
        except Exception:
            assignment_count = 0
        
        return {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "description": tag.description,
            "assignment_count": assignment_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating tag: {str(e)}")

@app.delete("/api/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Delete a tag"""
    try:
        tag = db.query(Tag).filter_by(id=tag_id).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        db.delete(tag)
        db.commit()
        
        return {"message": "Tag deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting tag: {str(e)}")

# Assignment-Tag Management Endpoints

@app.put("/api/assignments/{assignment_id}/tags")
def update_assignment_tags(assignment_id: int, tag_data: AssignmentTagUpdate, db: Session = Depends(get_db)):
    """Update tags for an assignment"""
    try:
        assignment = db.query(Assignment).filter_by(id=assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Get the new tags
        new_tags = db.query(Tag).filter(Tag.id.in_(tag_data.tag_ids)).all()
        
        # Update the assignment's tags
        assignment.tags = new_tags
        db.commit()
        
        # Return updated assignment with tags
        tags = []
        for tag in assignment.tags:
            tags.append({
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description
            })
        
        return {
            "id": assignment.id,
            "name": assignment.name,
            "tags": tags,
            "message": "Assignment tags updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating assignment tags: {str(e)}")
# Enhanced search endpoints with tags support

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
    """Get all assignments with their tags"""
    try:
        assignments = db.query(Assignment).order_by(Assignment.date.asc(), Assignment.name.asc()).all()
        result = []
        
        for assignment in assignments:
            # Count students who have grades for this assignment
            grade_count = db.query(Grade).filter_by(assignment_id=assignment.id).count()
            
            # Get tags for this assignment - with error handling
            tags = []
            try:
                for tag in assignment.tags:
                    tags.append({
                        "id": tag.id,
                        "name": tag.name,
                        "color": tag.color,
                        "description": tag.description
                    })
            except Exception as tag_error:
                print(f"Error getting tags for assignment {assignment.id}: {tag_error}")
                tags = []  # Continue without tags if there's an error
            
            result.append({
                "id": assignment.id,
                "name": assignment.name,
                "date": assignment.date.isoformat() if assignment.date else None,
                "max_points": assignment.max_points,
                "description": getattr(assignment, 'description', None),  # Safe attribute access
                "student_count": grade_count,
                "tags": tags
            })
        
        return {"assignments": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving assignments: {str(e)}")

# New Tag Management Endpoints

@app.get("/api/tags")
def get_all_tags(db: Session = Depends(get_db)):
    """Get all available tags"""
    try:
        tags = db.query(Tag).order_by(Tag.name).all()
        result = []
        
        for tag in tags:
            # Safe access to assignments count
            assignment_count = 0
            try:
                assignment_count = len(tag.assignments) if hasattr(tag, 'assignments') else 0
            except Exception:
                assignment_count = 0
                
            result.append({
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description,
                "assignment_count": assignment_count
            })
        
        return {"tags": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tags: {str(e)}")

@app.post("/api/tags")
def create_tag(tag_data: TagCreate, db: Session = Depends(get_db)):
    """Create a new tag"""
    try:
        # Check if tag name already exists
        existing_tag = db.query(Tag).filter_by(name=tag_data.name.strip()).first()
        if existing_tag:
            raise HTTPException(status_code=400, detail="Tag name already exists")
        
        new_tag = Tag(
            name=tag_data.name.strip(),
            color=tag_data.color,
            description=tag_data.description
        )
        
        db.add(new_tag)
        db.commit()
        db.refresh(new_tag)
        
        return {
            "id": new_tag.id,
            "name": new_tag.name,
            "color": new_tag.color,
            "description": new_tag.description,
            "assignment_count": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating tag: {str(e)}")

@app.put("/api/tags/{tag_id}")
def update_tag(tag_id: int, tag_data: TagUpdate, db: Session = Depends(get_db)):
    """Update an existing tag"""
    try:
        tag = db.query(Tag).filter_by(id=tag_id).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        # Check if new name already exists (if name is being changed)
        if tag_data.name and tag_data.name.strip() != tag.name:
            existing_tag = db.query(Tag).filter_by(name=tag_data.name.strip()).first()
            if existing_tag:
                raise HTTPException(status_code=400, detail="Tag name already exists")
        
        # Update fields
        if tag_data.name:
            tag.name = tag_data.name.strip()
        if tag_data.color:
            tag.color = tag_data.color
        if tag_data.description is not None:
            tag.description = tag_data.description
        
        db.commit()
        db.refresh(tag)
        
        # Safe access to assignments count
        assignment_count = 0
        try:
            assignment_count = len(tag.assignments) if hasattr(tag, 'assignments') else 0
        except Exception:
            assignment_count = 0
        
        return {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "description": tag.description,
            "assignment_count": assignment_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating tag: {str(e)}")

@app.delete("/api/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Delete a tag"""
    try:
        tag = db.query(Tag).filter_by(id=tag_id).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        db.delete(tag)
        db.commit()
        
        return {"message": "Tag deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting tag: {str(e)}")

# Assignment-Tag Management Endpoints

@app.put("/api/assignments/{assignment_id}/tags")
def update_assignment_tags(assignment_id: int, tag_data: AssignmentTagUpdate, db: Session = Depends(get_db)):
    """Update tags for an assignment"""
    try:
        assignment = db.query(Assignment).filter_by(id=assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Get the new tags
        new_tags = db.query(Tag).filter(Tag.id.in_(tag_data.tag_ids)).all()
        
        # Update the assignment's tags
        assignment.tags = new_tags
        db.commit()
        
        # Return updated assignment with tags
        tags = []
        for tag in assignment.tags:
            tags.append({
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description
            })
        
        return {
            "id": assignment.id,
            "name": assignment.name,
            "tags": tags,
            "message": "Assignment tags updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating assignment tags: {str(e)}")

@app.get("/api/search-assignments")
def search_assignments(
    query: str = "",
    tag_ids: str = "",
    db: Session = Depends(get_db)
):
    """Search assignments by name, description, or tags"""
    try:
        assignments_query = db.query(Assignment)
        
        # Text search in assignment name and description
        if query.strip():
            search_term = f"%{query.lower()}%"
            assignments_query = assignments_query.filter(
                or_(
                    func.lower(Assignment.name).like(search_term),
                    func.lower(Assignment.description).like(search_term) if hasattr(Assignment, 'description') else False
                )
            )
        
        # Filter by tags
        if tag_ids.strip():
            try:
                tag_id_list = [int(id.strip()) for id in tag_ids.split(',') if id.strip()]
                if tag_id_list:
                    assignments_query = assignments_query.join(Assignment.tags).filter(
                        Tag.id.in_(tag_id_list)
                    )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid tag IDs provided")
        
        assignments = assignments_query.order_by(Assignment.date.asc(), Assignment.name.asc()).all()
        result = []
        
        for assignment in assignments:
            # Count students who have grades
          grade_count = db.query(Grade).filter_by(assignment_id=assignment.id).count()
            
            # Get tags for this assignment - with error handling
        tags = []
            try:
                for tag in assignment.tags:
                    tags.append({
                        "id": tag.id,
                        "name": tag.name,
                        "color": tag.color,
                        "description": tag.description
                    })
            except Exception as tag_error:
                print(f"Error getting tags for assignment {assignment.id}: {tag_error}")
                tags = []
            
            result.append({
                "id": assignment.id,
                "name": assignment.name,
                "date": assignment.date.isoformat() if assignment.date else None,
                "max_points": assignment.max_points,
                "description": getattr(assignment, 'description', None),
                "student_count": grade_count,
                "tags": tags
            })
        
        return {
            "assignments": result,
            "total_found": len(result),
            "search_query": query,
            "tag_filter": tag_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching assignments: {str(e)}")

# Existing endpoints continue...

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
    uvicorn.run(app, host="0.0.0.0", port=10000)
