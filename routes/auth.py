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
