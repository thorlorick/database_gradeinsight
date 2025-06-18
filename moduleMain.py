# ==============================================================================
# routes/api.py - API endpoints
# ==============================================================================

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services import StudentService, AssignmentService
from utils.database import get_db
from utils.exceptions import StudentNotFoundError, create_http_exception

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
student_service = StudentService()
assignment_service = AssignmentService()


@router.get("/students")
def get_students_list(db: Session = Depends(get_db)):
    """Get all students with calculated statistics"""
    try:
        students = student_service.get_students_with_stats(db)
        return {"students": students}
    except Exception as e:
        logger.error(f"Error in get_students_list: {e}")
        raise create_http_exception(500, f"Error retrieving students list: {str(e)}")


@router.get("/student/{email}")
def get_student_by_email(email: str, db: Session = Depends(get_db)):
    """Get detailed information for a specific student"""
    try:
        student_data = student_service.get_student_by_email(email, db)
        return student_data
    except StudentNotFoundError as e:
        raise create_http_exception(404, str(e))
    except Exception as e:
        logger.error(f"Error in get_student_by_email: {e}")
        raise create_http_exception(500, f"Error retrieving student: {str(e)}")


@router.get("/search-students")
def search_students(query: str = "", db: Session = Depends(get_db)):
    """Search students by name or email"""
    try:
        results = student_service.search_students(query, db)
        return results
    except Exception as e:
        logger.error(f"Error in search_students: {e}")
        raise create_http_exception(500, f"Error searching students: {str(e)}")


@router.get("/assignments")
def get_assignments(db: Session = Depends(get_db)):
    """Get all assignments with metadata"""
    try:
        assignments = assignment_service.get_all_assignments(db)
        return {"assignments": assignments}
    except Exception as e:
        logger.error(f"Error in get_assignments: {e}")
        raise create_http_exception(500, f"Error retrieving assignments: {str(e)}")


@router.get("/grades-table")
def get_grades_for_table(db: Session = Depends(get_db)):
    """Get students with their grades for table display"""
    try:
        students = student_service.get_students_with_grades(db)
        return {"students": students}
    except Exception as e:
        logger.error(f"Error in get_grades_for_table: {e}")
        raise create_http_exception(500, f"Error retrieving grades table: {str(e)}")


@router.get("/assignment/{assignment_id}/stats")
def get_assignment_stats(assignment_id: int, db: Session = Depends(get_db)):
    """Get statistics for a specific assignment"""
    try:
        stats = assignment_service.get_assignment_stats(assignment_id, db)
        return stats
    except Exception as e:
        logger.error(f"Error in get_assignment_stats: {e}")
        raise create_http_exception(500, f"Error retrieving assignment stats: {str(e)}")


@router.get("/class-analytics")
def get_class_analytics(db: Session = Depends(get_db)):
    """Get class-wide analytics data"""
    try:
        analytics = student_service.get_class_analytics(db)
        return analytics
    except Exception as e:
        logger.error(f"Error in get_class_analytics: {e}")
        raise create_http_exception(500, f"Error retrieving class analytics: {str(e)}")


# ==============================================================================
# routes/pages.py - HTML page routes
# ==============================================================================

import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config.settings import Settings
from utils.database import get_db
from utils.exceptions import create_http_exception

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize templates
settings = Settings()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)


@router.get("/", response_class=RedirectResponse)
async def root():
    """Redirect root to dashboard"""
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render dashboard page"""
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        raise create_http_exception(500, f"Error loading dashboard: {str(e)}")


@router.get("/students", response_class=HTMLResponse)
async def students_page(request: Request):
    """Render students page"""
    try:
        return templates.TemplateResponse("students.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading students page: {e}")
        raise create_http_exception(500, f"Error loading students page: {str(e)}")


@router.get("/student-portal", response_class=HTMLResponse)
async def student_portal(request: Request):
    """Render student portal page"""
    try:
        return templates.TemplateResponse("student-portal.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading student portal: {e}")
        raise create_http_exception(500, f"Error loading student portal: {str(e)}")


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Render analytics page"""
    try:
        return templates.TemplateResponse("analytics.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading analytics page: {e}")
        raise create_http_exception(500, f"Error loading analytics page: {str(e)}")


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    """Render reports page"""
    try:
        return templates.TemplateResponse("reports.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading reports page: {e}")
        raise create_http_exception(500, f"Error loading reports page: {str(e)}")


@router.get("/assignments", response_class=HTMLResponse)
async def assignments_page(request: Request):
    """Render assignments page"""
    try:
        return templates.TemplateResponse("assignments.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading assignments page: {e}")
        raise create_http_exception(500, f"Error loading assignments page: {str(e)}")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render settings page"""
    try:
        return templates.TemplateResponse("settings.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading settings page: {e}")
        raise create_http_exception(500, f"Error loading settings page: {str(e)}")


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Render help page"""
    try:
        return templates.TemplateResponse("help.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading help page: {e}")
        raise create_http_exception(500, f"Error loading help page: {str(e)}")


# ==============================================================================
# routes/auth.py - Authentication routes
# ==============================================================================

import logging
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config.settings import Settings
from services import AuthService
from utils.database import get_db
from utils.exceptions import create_http_exception

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize templates and services
settings = Settings()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)
auth_service = AuthService()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page"""
    try:
        return templates.TemplateResponse("auth/login.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading login page: {e}")
        raise create_http_exception(500, f"Error loading login page: {str(e)}")


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle login form submission"""
    try:
        user = auth_service.authenticate_user(username, password, db)
        if not user:
            return templates.TemplateResponse(
                "auth/login.html", 
                {
                    "request": request, 
                    "error": "Invalid username or password"
                }
            )
        
        # Set session or token here
        response = RedirectResponse(url="/dashboard", status_code=302)
        # Add authentication cookie/session logic
        return response
        
    except Exception as e:
        logger.error(f"Error during login: {e}")
        return templates.TemplateResponse(
            "auth/login.html", 
            {
                "request": request, 
                "error": "Login failed. Please try again."
            }
        )


@router.get("/logout")
async def logout():
    """Handle logout"""
    try:
        response = RedirectResponse(url="/login")
        # Clear authentication cookie/session logic
        return response
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        raise create_http_exception(500, f"Error during logout: {str(e)}")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render registration page"""
    try:
        return templates.TemplateResponse("auth/register.html", {"request": request})
    except Exception as e:
        logger.error(f"Error loading register page: {e}")
        raise create_http_exception(500, f"Error loading register page: {str(e)}")


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle registration form submission"""
    try:
        if password != confirm_password:
            return templates.TemplateResponse(
                "auth/register.html", 
                {
                    "request": request, 
                    "error": "Passwords do not match"
                }
            )
        
        user = auth_service.create_user(username, email, password, db)
        if not user:
            return templates.TemplateResponse(
                "auth/register.html", 
                {
                    "request": request, 
                    "error": "Username or email already exists"
                }
            )
        
        return RedirectResponse(url="/login?registered=true", status_code=302)
        
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        return templates.TemplateResponse(
            "auth/register.html", 
            {
                "request": request, 
                "error": "Registration failed. Please try again."
            }
        )


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


# ==============================================================================
# routes/__init__.py - Route module initialization
# ==============================================================================

from fastapi import APIRouter
from . import api, pages, auth, admin

def create_router():
    """Create and configure the main router with all sub-routers"""
    main_router = APIRouter()
    
    # Include page routes (no prefix for main pages)
    main_router.include_router(pages.router, tags=["pages"])
    
    # Include API routes with /api prefix
    main_router.include_router(api.router, prefix="/api", tags=["api"])
    
    # Include auth routes
    main_router.include_router(auth.router, tags=["auth"])
    
    # Include admin routes
    main_router.include_router(admin.router, tags=["admin"])
    
    return main_router
