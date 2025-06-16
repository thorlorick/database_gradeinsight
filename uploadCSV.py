import os  
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

router = APIRouter()

@router.get("/api/uploadCSV", response_class=HTMLResponse)
async def upload_form(request: Request, db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse("upload.html", {"request": request, "tags": tags})
