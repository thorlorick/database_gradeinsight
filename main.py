import io
import os
from datetime import datetime
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import Student, Assignment, Grade

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
    # TODO: Add CSV processing here if needed
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

    # Read entire CSV without skipping rows, because we need headers + date + points + data
    raw_df = pd.read_csv(csv_io, header=None)

    # Validate minimum rows (header + date + points + at least one student)
    if raw_df.shape[0] < 4:
        return JSONResponse({"error": "CSV must have at least 4 rows: headers, dates, points, and student data"}, status_code=400)

    # Extract headers (row 0)
    headers = raw_df.iloc[0].tolist()

    # Check required student info columns exist
    required_cols = {"Email Address", "First Name", "Last Name"}
    if not required_cols.issubset(headers):
        return JSONResponse({"error": f"CSV missing required columns: {required_cols}"}, status_code=400)

    # Map column indexes for student info
    email_col = headers.index("Email Address")
    first_name_col = headers.index("First Name")
    last_name_col = headers.index("Last Name")

    # Extract assignment names (all headers after student info columns)
    # Assume first 3 columns are student info, assignments start from index 3
    assignment_names = headers[3:]

    # Extract max points (row 2)
    max_points_row = raw_df.iloc[2].tolist()
    max_points_map = {}
    for i, assign_name in enumerate(assignment_names):
        try:
            max_point_val = float(max_points_row[i + 3])
            max_points_map[assign_name] = max_point_val
        except (ValueError, IndexError):
            max_points_map[assign_name] = 100.0  # default

    # Extract dates row (row 1)
    dates_row = raw_df.iloc[1].tolist()
    dates_map = {}

    for i, assign_name in enumerate(assignment_names):
        raw_date = dates_row[i + 3]
        if isinstance(raw_date, str) and raw_date.strip():
            try:
                # Try parsing ISO or common date format, adjust as needed
                parsed_date = datetime.strptime(raw_date.strip(), "%Y-%m-%d").date()
                dates_map[assign_name] = parsed_date
            except ValueError:
                # Could not parse date, store None (ignore silently)
                dates_map[assign_name] = None
        else:
            dates_map[assign_name] = None

    # Student data starts at row index 3 to the end
    student_rows = raw_df.iloc[3:]

    for idx, row in student_rows.iterrows():
        email = str(row[email_col]).strip()
        if not email or email.lower() == 'nan':
            continue  # skip rows with empty email

        first_name = str(row[first_name_col]).strip()
        last_name = str(row[last_name_col]).strip()

        # UPSERT student
        student = db.query(Student).filter_by(email=email).first()
        if student:
            student.first_name = first_name
            student.last_name = last_name
        else:
            student = Student(email=email, first_name=first_name, last_name=last_name)
            db.add(student)

        # Process grades for each assignment
        for i, assign_name in enumerate(assignment_names):
            try:
                score_val = row[i + 3]
            except IndexError:
                continue  # no score for this assignment

            if pd.isna(score_val) or score_val == '':
                continue  # skip empty grade cells

            try:
                score = float(score_val)
            except ValueError:
                continue  # invalid score, skip

            if not (0 <= score <= max_points_map.get(assign_name, 100)):
                return JSONResponse({"error": f"Score {score} for assignment '{assign_name}' out of range"}, status_code=400)

            # Assign unique name for assignment if names repeat
            # Here we just assume names unique; if not, you might append index or handle separately
            # For now, use assign_name directly

            assignment = db.query(Assignment).filter_by(name=assign_name, date=dates_map.get(assign_name)).first()
            if not assignment:
                assignment = Assignment(
                    name=assign_name,
                    max_points=max_points_map.get(assign_name, 100),
                    date=dates_map.get(assign_name)
                )
                db.add(assignment)
                db.flush()  # assign ID for FK

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
    result = []
    for s in students:
        result.append({
            "email": s.email,
            "first_name": s.first_name,
            "last_name": s.last_name
        })
    return {"students": result}

# Optional: endpoint to reset DB - use with care
@app.get("/reset-db-1122334455")
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return {"status": "Database reset (GET)"}



