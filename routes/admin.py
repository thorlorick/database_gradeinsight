# ==============================================================================
# routes/admin.py - Admin routes
# ==============================================================================

import logging
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config.settings import Settings
from services import AdminService, DataImportService
from utils.database import get_db
from utils.exceptions import create_http_exception
from utils.auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize templates and services
settings = Settings()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)
admin_service = AdminService()
import_service = DataImportService()


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, current_user=Depends(require_admin)):
    """Render admin dashboard"""
    try:
        return templates.TemplateResponse("admin/dashboard.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {e}")
        raise create_http_exception(500, f"Error loading admin dashboard: {str(e)}")


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, current_user=Depends(require_admin)):
    """Render admin users management page"""
    try:
        return templates.TemplateResponse("admin/users.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading admin users page: {e}")
        raise create_http_exception(500, f"Error loading admin users page: {str(e)}")


@router.get("/admin/import", response_class=HTMLResponse)
async def admin_import(request: Request, current_user=Depends(require_admin)):
    """Render data import page"""
    try:
        return templates.TemplateResponse("admin/import.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading import page: {e}")
        raise create_http_exception(500, f"Error loading import page: {str(e)}")


@router.post("/admin/import-csv")
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    import_type: str = Form(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Handle CSV file import"""
    try:
        if not file.filename.endswith('.csv'):
            return templates.TemplateResponse(
                "admin/import.html", 
                {
                    "request": request, 
                    "error": "Please upload a CSV file"
                }
            )
        
        content = await file.read()
        result = import_service.import_csv_data(content, import_type, db)
        
        return templates.TemplateResponse(
            "admin/import.html", 
            {
                "request": request, 
                "success": f"Successfully imported {result['count']} records"
            }
        )
        
    except Exception as e:
        logger.error(f"Error importing CSV: {e}")
        return templates.TemplateResponse(
            "admin/import.html", 
            {
                "request": request, 
                "error": f"Import failed: {str(e)}"
            }
        )


@router.get("/admin/system", response_class=HTMLResponse)
async def admin_system(request: Request, current_user=Depends(require_admin)):
    """Render system management page"""
    try:
        return templates.TemplateResponse("admin/system.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading system page: {e}")
        raise create_http_exception(500, f"Error loading system page: {str(e)}")


@router.post("/admin/backup-database")
async def backup_database(current_user=Depends(require_admin), db: Session = Depends(get_db)):
    """Create database backup"""
    try:
        backup_path = admin_service.create_database_backup(db)
        return {"success": True, "backup_path": backup_path}
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        raise create_http_exception(500, f"Backup failed: {str(e)}")
