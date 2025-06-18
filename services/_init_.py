# services/__init__.py

"""
Services package for Grade Insight application.

This package contains all business logic services for managing:
- Students and their information
- Assignments and grading
- CSV file processing and data import/export

Usage:
    from services import StudentService, AssignmentService, CSVProcessor
    
    # Or import specific services
    from services.student_service import StudentService
    from services.assignment_service import AssignmentService
    from services.csv_processor import CSVProcessor
"""

from .student_service import StudentService
from .assignment_service import AssignmentService
from .csv_processor import CSVProcessor

# Make services available at package level
__all__ = [
    "StudentService",
    "AssignmentService", 
    "CSVProcessor"
]

# Version info
__version__ = "1.0.0"

# Service factory functions for dependency injection
def get_student_service(db=None):
    """Factory function to create StudentService instance"""
    return StudentService(db)

def get_assignment_service(db=None):
    """Factory function to create AssignmentService instance"""
    return AssignmentService(db)

def get_csv_processor(db=None):
    """Factory function to create CSVProcessor instance"""
    return CSVProcessor(db)
