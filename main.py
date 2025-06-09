@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    csv_io = io.StringIO(contents.decode("utf-8"))

    full_df = pd.read_csv(csv_io, header=0)

    if len(full_df) < 3:
        return {"error": "CSV must have at least 3 rows (header, date, max points)."}

    max_points_row = full_df.iloc[2]
    df = full_df.iloc[3:].reset_index(drop=True)

    required_columns = {"email", "first_name", "last_name"}
    if not required_columns.issubset(df.columns):
        return {"error": "Missing required columns: email, first_name, last_name."}

    for _, row in df.iterrows():
        email = str(row["email"]).strip().lower()

        if not email:
            continue  # skip students without an email

        student = db.query(Student).filter_by(email=email).first()
        if student:
            student.first_name = row["first_name"]
            student.last_name = row["last_name"]
            student.student_number = row.get("student_number", None)
        else:
            student = Student(
                email=email,
                first_name=row["first_name"],
                last_name=row["last_name"],
                student_number=row.get("student_number", None)
            )
            db.add(student)

        for col in df.columns:
            if col in {"email", "first_name", "last_name", "student_number"}:
                continue

            score = row[col]
            if pd.isna(score):
                continue

            if not (0 <= float(score) <= 100):
                return {
                    "error": f"Invalid score {score} for assignment '{col}' (must be 0–100)."
                }

            assignment = db.query(Assignment).filter_by(name=col).first()
            if not assignment:
                try:
                    max_point = float(max_points_row[col])
                except (ValueError, KeyError):
                    max_point = 100
                assignment = Assignment(name=col, max_points=max_point)
                db.add(assignment)
                db.flush()

            grade = db.query(Grade).filter_by(email=email, assignment_id=assignment.id).first()
            if grade:
                grade.score = score
            else:
                grade = Grade(email=email, assignment_id=assignment.id, score=score)
                db.add(grade)

    db.commit()
    return {"status": "Upload processed successfully"}
