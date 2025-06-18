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
