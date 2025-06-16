import io
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from database import SessionLocal
from models import Student, Assignment, Grade, Tag

templates = Jinja2Templates(directory="templates")
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request, db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse("upload.html", {"request": request, "tags": tags})

@router.post("/upload")
async def handle_upload(
    file: UploadFile = File(...),
    tags: str = Form(None),
    new_tags: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        # Parse selected tag IDs
        selected_tag_ids = []
        if tags:
            import json
            selected_tag_ids = json.loads(tags)

        # Parse new tags (comma separated)
        new_tag_ids = []
        if new_tags:
            tag_names = [t.strip() for t in new_tags.split(",") if t.strip()]
            for tag_name in tag_names:
                existing_tag = db.query(Tag).filter(func.lower(Tag.name) == tag_name.lower()).first()
                if existing_tag:
                    new_tag_ids.append(existing_tag.id)
                else:
                    new_tag = Tag(name=tag_name)
                    db.add(new_tag)
                    db.flush()
                    new_tag_ids.append(new_tag.id)

        all_tag_ids = list(set(selected_tag_ids + new_tag_ids))

        # --- CSV processing (your existing logic) ---
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")

        contents = await file.read()
        try:
            csv_io = io.StringIO(contents.decode("utf-8"))
            df = pd.read_csv(csv_io, header=0)
        except UnicodeDecodeError:
            csv_io = io.StringIO(contents.decode("latin-1"))
            df = pd.read_csv(csv_io, header=0)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading CSV file: {str(e)}")

        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        df.columns = [str(col).strip() for col in df.columns]
        if len(df) < 4:
            raise HTTPException(status_code=400, detail="CSV must have at least 4 rows")

        date_row = df.iloc[0] if len(df) > 1 else None
        points_row = df.iloc[1] if len(df) > 2 else None
        student_df = df.iloc[2:].reset_index(drop=True)

        if len(student_df.columns) < 3:
            raise HTTPException(status_code=400, detail="CSV must have at least 3 columns")

        original_columns = df.columns.tolist()
        assignment_cols_original = original_columns[3:]
        new_column_names = ['last_name', 'first_name', 'email'] + assignment_cols_original
        student_df.columns = new_column_names

        required_columns = {'last_name', 'first_name', 'email'}
        if not required_columns.issubset(student_df.columns):
            missing = required_columns - set(student_df.columns)
            raise HTTPException(status_code=400, detail=f"Missing columns: {list(missing)}")

        total_students = len(student_df)
        processed_students = 0
        valid_assignments = []
        skipped_assignments = []

        for i, assignment_name in enumerate(assignment_cols_original):
            col_index_in_student_df = i + 3
            col_index_in_original_df = i + 3
            try:
                max_points_val = None
                if points_row is not None and col_index_in_original_df < len(points_row):
                    max_points_val = points_row.iloc[col_index_in_original_df]
                if pd.isna(max_points_val) or str(max_points_val).strip() == '':
                    skipped_assignments.append(assignment_name)
                    continue
                else:
                    try:
                        max_points_val = float(max_points_val)
                    except (ValueError, TypeError):
                        skipped_assignments.append(assignment_name)
                        continue

                assignment_col = student_df.iloc[:, col_index_in_student_df]
                non_empty_count = 0
                for value in assignment_col:
                    if pd.notna(value) and str(value).strip() != '' and str(value).strip().lower() != 'nan':
                        try:
                            float(value)
                            non_empty_count += 1
                        except (ValueError, TypeError):
                            pass

                threshold = max(1, int(total_students * 0.1))
                if non_empty_count >= threshold:
                    valid_assignments.append((assignment_name, max_points_val))
                else:
                    skipped_assignments.append(assignment_name)
            except Exception:
                skipped_assignments.append(assignment_name)
                continue

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

        for index, row in student_df.iterrows():
            email = str(row['email']).strip().lower()
            if not email or email == 'nan':
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

            for assignment_name, max_points_val in valid_assignments:
                try:
                    score_value = row[assignment_name]
                    if pd.isna(score_value) or str(score_value).strip() == '' or str(score_value).strip().lower() == 'nan':
                        continue
                    try:
                        score = float(score_value)
                    except (ValueError, TypeError):
                        continue

                    assignment_index = assignment_cols_original.index(assignment_name)
                    original_col_index = assignment_index + 3

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
                            max_points=max_points_val
                        )
                        if all_tag_ids:
                            assignment.tags = db.query(Tag).filter(Tag.id.in_(all_tag_ids)).all()
                        db.add(assignment)
                        db.flush()

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
                except Exception:
                    continue

        db.commit()
        return {
            "status": f"File {file.filename} uploaded and processed successfully",
            "total_students": total_students,
            "processed_students": processed_students,
            "total_assignments_found": len(assignment_cols_original),
            "valid_assignments": [name for name, _ in valid_assignments],
            "skipped_assignments": skipped_assignments,
            "processed_assignments": len(valid_assignments),
            "threshold_used": max(1, int(total_students * 0.1))
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
