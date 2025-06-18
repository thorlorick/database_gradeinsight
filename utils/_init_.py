# ==============================================================================
# utils/__init__.py - Utils package initialization
# ==============================================================================

"""
Utils package for GradeInsight application.
Provides database utilities, logging configuration, and other helper functions.
"""

# Import key functions and classes for easy access
from .database import (
    init_database,
    get_db,
    reset_database
)

from .logging import (
    setup_logging,
    get_logger,
    log_function_call,
    log_database_operation,
    LoggingContext,
    setup_development_logging,
    setup_production_logging,
    setup_testing_logging,
    auto_configure_logging,
    JSONFormatter,
    ColoredFormatter
)

# Package metadata
__version__ = "1.0.0"
__author__ = "GradeInsight Team"

# Define what gets imported with "from utils import *"
__all__ = [
    # Database utilities
    "init_database",
    "get_db", 
    "reset_database",
    
    # Logging utilities
    "setup_logging",
    "get_logger",
    "log_function_call",
    "log_database_operation", 
    "LoggingContext",
    "setup_development_logging",
    "setup_production_logging",
    "setup_testing_logging",
    "auto_configure_logging",
    "JSONFormatter",
    "ColoredFormatter",
]

# Initialize logging when the package is imported
try:
    auto_configure_logging()
except Exception as e:
    # Fallback to basic logging if auto-configuration fails
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.error(f"Failed to auto-configure logging in utils package: {e}")
