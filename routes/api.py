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
