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
