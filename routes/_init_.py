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
    
    return main_router#_init_.py
