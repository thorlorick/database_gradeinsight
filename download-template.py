from fastapi import APIRouter

router = APIRouter()

@router.get("/downloadTemplate")
def download_template():
    file_path = "template.csv"
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename="grade_insight_template.csv", media_type='text/csv')
    else:
        return JSONResponse(
            status_code=404,
            content={"error": "Template file not found."}
        )
