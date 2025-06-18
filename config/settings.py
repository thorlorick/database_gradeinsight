# ==============================================================================
# config/settings.py - Configuration management
# ==============================================================================

import os
from typing import Optional


class Settings:
    """Application settings and configuration"""
    
    # App settings
    APP_NAME: str = "Grade Insight"
    APP_VERSION: str = "1.0.0"
    
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./grades.db")
    
    # File upload settings
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    ALLOWED_EXTENSIONS: list = [".csv"]
    
    # CSV processing settings
    MIN_ROWS: int = 4
    MIN_COLUMNS: int = 3
    GRADE_THRESHOLD: float = 0.1  # 10% of students must have grades
    
    # Template settings
    TEMPLATES_DIR: str = "templates"
    STATIC_DIR: str = "static"
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")# settings for something??????
