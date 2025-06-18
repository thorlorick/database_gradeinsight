# Project Structure:
# grade_insight/
# ├── main.py
# ├── config/
# │   ├── __init__.py
# │   └── settings.py
# ├── routes/
# │   ├── __init__.py
# │   ├── api.py
# │   ├── pages.py
# │   ├── upload.py
# │   └── utils.py
# ├── services/
# │   ├── __init__.py
# │   ├── csv_processor.py
# │   ├── student_service.py
# │   └── assignment_service.py
# ├── utils/
# │   ├── __init__.py
# │   ├── database.py
# │   ├── exceptions.py
# │   └── logging.py
# └── templates/
#     └── (your existing template files)

# ==============================================================================
# main.py - Application entry point
# ==============================================================================

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config.settings import Settings
from routes import api, pages, upload, utils as route_utils
from utils.database import init_database
from utils.logging import setup_logging
from downloadTemplate import router as downloadTemplate_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    # Setup logging
    setup_logging()
    
    # Initialize settings
    settings = Settings()
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Grade management system for educational institutions"
    )
    
    # Setup directories
    _setup_directories()
    
    # Setup static files and templates
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Initialize database
    init_database()
    
    # Include routers
    app.include_router(downloadTemplate_router)
    app.include_router(api.router, prefix="/api", tags=["api"])
    app.include_router(pages.router, tags=["pages"])
    app.include_router(upload.router, tags=["upload"])
    app.include_router(route_utils.router, tags=["utils"])
    
    return app


def _setup_directories() -> None:
    """Ensure required directories exist"""
    for directory in ["templates", "static"]:
        if not os.path.exists(directory):
            os.makedirs(directory)


# Create the application instance
app = create_app()

# For development server
if __name__ == "__main__":
    import uvicorn
    from config.settings import Settings
    
    settings = Settings()
    uvicorn.run(
        "main:app", 
        host=settings.HOST, 
        port=settings.PORT, 
        reload=settings.DEBUG
    )

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
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")

# ==============================================================================
# config/__init__.py
# ==============================================================================

from .settings import Settings

__all__ = ["Settings"]

# ==============================================================================
# utils/database.py - Database utilities
# ==============================================================================

import logging
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal

logger = logging.getLogger(__name__)


def init_database() -> None:
    """Initialize database tables with error handling"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def get_db() -> Session:
    """Database dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_database() -> None:
    """Reset the database (drop and recreate all tables)"""
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("Database reset successfully")
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise

# ==============================================================================
# utils/exceptions.py - Custom exceptions
# ==============================================================================

from fastapi import HTTPException


class GradeInsightException(Exception):
    """Base exception for Grade Insight application"""
    pass


class CSVProcessingError(GradeInsightException):
    """Exception raised during CSV processing"""
    pass


class StudentNotFoundError(GradeInsightException):
    """Exception raised when student is not found"""
    pass


class InvalidFileError(GradeInsightException):
    """Exception raised when uploaded file is invalid"""
    pass


def create_http_exception(status_code: int, detail: str) -> HTTPException:
    """Create standardized HTTP exception"""
    return HTTPException(status_code=status_code, detail=detail)

# ==============================================================================
# utils/logging.py - Logging configuration
# ==============================================================================

import logging
import sys
from config.settings import Settings


def setup_logging() -> None:
    """Setup application logging"""
    settings = Settings()
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Setup file handler if log file is specified
    handlers = [console_handler]
    if settings.LOG_FILE:
        file_handler = logging.FileHandler(settings.LOG_FILE)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        handlers=handlers
    )
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# ==============================================================================
# utils/__init__.py
# ==============================================================================

from .database import get_db, init_database, reset_database
from .exceptions import (
    GradeInsightException, 
    CSVProcessingError, 
    StudentNotFoundError, 
    InvalidFileError,
    create_http_exception
)
from .logging import setup_logging

__all__ = [
    "get_db", 
    "init_database", 
    "reset_database",
    "GradeInsightException",
    "CSVProcessingError", 
    "StudentNotFoundError", 
    "InvalidFileError",
    "create_http_exception",
    "setup_logging"
]

# ==============================================================================
# services/csv_processor.py - CSV processing service
# ==============================================================================

import io
import logging
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
from datetime import date

from config.settings import Settings
from utils.exceptions import CSVProcessingError, InvalidFileError

logger = logging.getLogger(__name__)


class CSVProcessor:
    """Service for processing CSV files"""
    
    def __init__(self):
        self.settings = Settings()
    
    async def process_csv_file(self, file_content: bytes, filename: str) -> pd.DataFrame:
        """Process uploaded CSV file"""
        try:
            logger.info(f"Processing CSV file: {filename}")
            
            # Read CSV with encoding fallback
            df = self._read_csv_content(file_content)
            
            # Validate basic structure
            self._validate_csv_structure(df)
            
            logger.info(f"CSV processed successfully. Shape: {df.shape}")
            return df
            
        except Exception as e:
            logger.error(f"Error processing CSV file {filename}: {e}")
            raise CSVProcessingError(f"Error processing CSV file: {str(e)}")
    
    def _read_csv_content(self, content: bytes) -> pd.DataFrame:
        """Read CSV content with encoding fallback"""
        try:
            csv_io = io.StringIO(content.decode("utf-8"))
            return pd.read_csv(csv_io, header=0)
        except UnicodeDecodeError:
            csv_io = io.StringIO(content.decode("latin-1"))
            return pd.read_csv(csv_io, header=0)
        except Exception as e:
            raise InvalidFileError(f"Cannot read CSV file: {str(e)}")
    
    def _validate_csv_structure(self, df: pd.DataFrame) -> None:
        """Validate basic CSV structure"""
        if df.empty:
            raise InvalidFileError("CSV file is empty")
        
        if len(df) < self.settings.MIN_ROWS:
            raise InvalidFileError(f"CSV must have at least {self.settings.MIN_ROWS} rows")
        
        if len(df.columns) < self.settings.MIN_COLUMNS:
            raise InvalidFileError(f"CSV must have at least {self.settings.MIN_COLUMNS} columns")
    
    def extract_metadata(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract metadata from CSV structure"""
        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        
        # Extract rows
        date_row = df.iloc[0] if len(df) > 1 else None
        points_row = df.iloc[1] if len(df) > 2 else None
        student_df = df.iloc[2:].reset_index(drop=True)
        
        # Get column information
        original_columns = df.columns.tolist()
        assignment_columns = original_columns[3:]  # Skip first 3 columns
        
        # Rename student dataframe columns
        new_column_names = ['last_name', 'first_name', 'email'] + assignment_columns
        student_df.columns = new_column_names
        
        # Validate required columns
        required_columns = {'last_name', 'first_name', 'email'}
        if not required_columns.issubset(student_df.columns):
            missing = required_columns - set(student_df.columns)
            raise InvalidFileError(f"Missing required columns: {list(missing)}")
        
        return {
            'date_row': date_row,
            'points_row': points_row,
            'student_df': student_df,
            'assignment_columns': assignment_columns,
            'original_columns': original_columns
        }
    
    def validate_assignments(self, assignment_columns: List[str], 
                           points_row: Optional[pd.Series], 
                           total_students: int) -> Tuple[List[str], List[str]]:
        """Validate which assignments have sufficient data"""
        valid_assignments = []
        skipped_assignments = []
        
        for i, assignment_name in enumerate(assignment_columns):
            col_index = i + 3  # +3 for student info columns
            
            try:
                # Check if assignment has max points defined
                if not self._has_valid_max_points(points_row, col_index):
                    logger.debug(f"Skipping assignment '{assignment_name}' - no valid max points")
                    skipped_assignments.append(assignment_name)
                    continue
                
                valid_assignments.append(assignment_name)
                logger.debug(f"Assignment '{assignment_name}' is valid")
                
            except Exception as e:
                logger.error(f"Error validating assignment '{assignment_name}': {e}")
                skipped_assignments.append(assignment_name)
        
        return valid_assignments, skipped_assignments
    
    def _has_valid_max_points(self, points_row: Optional[pd.Series], col_index: int) -> bool:
        """Check if assignment has valid max points"""
        if points_row is None or col_index >= len(points_row):
            return False
        
        max_points_val = points_row.iloc[col_index]
        
        if pd.isna(max_points_val) or str(max_points_val).strip() == '':
            return False
        
        try:
            float(max_points_val)
            return True
        except (ValueError, TypeError):
            return False
    
    def extract_assignment_metadata(self, assignment_name: str, 
                                  metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata for a specific assignment"""
        assignment_index = metadata['assignment_columns'].index(assignment_name)
        original_col_index = assignment_index + 3
        
        # Extract date
        assignment_date = self._extract_assignment_date(
            metadata['date_row'], original_col_index
        )
        
        # Extract max points
        max_points = self._extract_max_points(
            metadata['points_row'], original_col_index
        )
        
        return {
            'date': assignment_date,
            'max_points': max_points
        }
    
    def _extract_assignment_date(self, date_row: Optional[pd.Series], 
                               col_index: int) -> Optional[date]:
        """Extract assignment date from date row"""
        if date_row is None or col_index >= len(date_row):
            return None
        
        date_val = date_row.iloc[col_index]
        if pd.isna(date_val) or str(date_val).strip() == '':
            return None
        
        try:
            parsed_date = pd.to_datetime(date_val, errors='coerce')
            if pd.notna(parsed_date):
                return parsed_date.date()
        except Exception:
            logger.warning(f"Could not parse date: {date_val}")
        
        return None
    
    def _extract_max_points(self, points_row: Optional[pd.Series], 
                          col_index: int) -> float:
        """Extract max points for assignment"""
        default_points = 100.0
        
        if points_row is None or col_index >= len(points_row):
            return default_points
        
        try:
            max_val = points_row.iloc[col_index]
            if pd.notna(max_val) and str(max_val).strip() != '':
                return float(max_val)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse max points, using default: {default_points}")
        
        return default_points

# ==============================================================================
# services/student_service.py - Student management service
# ==============================================================================

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from models import Student, Grade
from utils.exceptions import StudentNotFoundError

logger = logging.getLogger(__name__)


class StudentService:
    """Service for managing students"""
    
    def get_all_students(self, db: Session) -> List[Dict[str, Any]]:
        """Get all students with basic information"""
        try:
            students = db.query(Student).all()
            return [
                {
                    "email": student.email,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                }
                for student in students
            ]
        except Exception as e:
            logger.error(f"Error retrieving students: {e}")
            raise
    
    def get_students_with_grades(self, db: Session) -> List[Dict[str, Any]]:
        """Get all students with their grades"""
        try:
            students = db.query(Student).all()
            result = []
            
            for student in students:
                grades_list = [
                    {
                        "assignment": grade.assignment.name,
                        "date": grade.assignment.date.isoformat() if grade.assignment.date else None,
                        "score": grade.score,
                        "max_points": grade.assignment.max_points,
                    }
                    for grade in student.grades
                ]
                
                result.append({
                    "email": student.email,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "grades": grades_list,
                })
            
            return result
        except Exception as e:
            logger.error(f"Error retrieving students with grades: {e}")
            raise
    
    def get_students_with_stats(self, db: Session) -> List[Dict[str, Any]]:
        """Get students with calculated statistics"""
        try:
            students = db.query(Student).all()
            result = []
            
            for student in students:
                stats = self._calculate_student_stats(student)
                result.append({
                    "email": student.email,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    **stats
                })
            
            return result
        except Exception as e:
            logger.error(f"Error retrieving students with stats: {e}")
            raise
    
    def get_student_by_email(self, email: str, db: Session) -> Dict[str, Any]:
        """Get detailed information for a specific student"""
        student = db.query(Student).filter_by(email=email.lower().strip()).first()
        if not student:
            raise StudentNotFoundError(f"Student with email {email} not found")
        
        grades_list = []
        total_points = 0
        max_possible = 0
        
        for grade in student.grades:
            assignment = grade.assignment
            if assignment:
                score = grade.score or 0
                max_pts = assignment.max_points or 0
                total_points += score
                max_possible += max_pts
                
                grades_list.append({
                    "assignment": assignment.name,
                    "date": assignment.date.isoformat() if assignment.date else None,
                    "score": score,
                    "max_points": max_pts
                })
        
        overall_percentage = (total_points / max_possible * 100) if max_possible > 0 else 0
        
        return {
            "email": student.email,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "total_points": total_points,
            "max_possible": max_possible,
            "overall_percentage": overall_percentage,
            "total_assignments": len(grades_list),
            "grades": grades_list
        }
    
    def search_students(self, query: str, db: Session) -> Dict[str, Any]:
        """Search students by name or email"""
        try:
            students_query = db.query(Student)
            
            if query.strip():
                search_term = f"%{query.lower()}%"
                students_query = students_query.filter(
                    or_(
                        func.lower(Student.first_name).like(search_term),
                        func.lower(Student.last_name).like(search_term),
                        func.lower(Student.email).like(search_term),
                        func.lower(func.concat(Student.first_name, ' ', Student.last_name)).like(search_term),
                        func.lower(func.concat(Student.last_name, ', ', Student.first_name)).like(search_term)
                    )
                )
            
            students = students_query.all()
            result = []
            
            for student in students:
                grades_list = [
                    {
                        "assignment": grade.assignment.name,
                        "date": grade.assignment.date.isoformat() if grade.assignment.date else None,
                        "max_points": grade.assignment.max_points,
                        "score": grade.score,
                    }
                    for grade in student.grades
                ]
                
                result.append({
                    "email": student.email,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "grades": grades_list,
                })
            
            return {
                "students": result,
                "total_found": len(result),
                "search_query": query
            }
            
        except Exception as e:
            logger.error(f"Error searching students: {e}")
            raise
    
    def create_or_update_student(self, student_data: Dict[str, str], db: Session) -> Student:
        """Create or update a student record"""
        email = student_data['email'].lower().strip()
        
        student = db.query(Student).filter_by(email=email).first()
        if student:
            student.first_name = student_data['first_name'].strip()
            student.last_name = student_data['last_name'].strip()
        else:
            student = Student(
                email=email,
                first_name=student_data['first_name'].strip(),
                last_name=student_data['last_name'].strip()
            )
            db.add(student)
        
        return student
    
    def _calculate_student_stats(self, student: Student) -> Dict[str, Any]:
        """Calculate statistics for a student"""
        total_grades = len(student.grades)
        total_points = sum(grade.score for grade in student.grades)
        max_possible = sum(grade.assignment.max_points for grade in student.grades)
        avg_percentage = (total_points / max_possible * 100) if max_possible > 0 else 0
        
        return {
            "total_assignments": total_grades,
            "total_points": total_points,
            "max_possible": max_possible,
            "average_percentage": round(avg_percentage, 1)
        }

# ==============================================================================
# services/assignment_service.py - Assignment management service
# ==============================================================================

import logging
from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import Assignment, Grade

logger = logging.getLogger(__name__)


class AssignmentService:
    """Service for managing assignments"""
    
    def get_all_assignments(self, db: Session) -> List[Dict[str, Any]]:
        """Get all assignments with metadata"""
        try:
            assignments = db.query(Assignment).order_by(
                Assignment.date.asc(), Assignment.name.asc()
            ).all()
            
            result = []
            for assignment in assignments:
                grade_count = db.query(Grade).filter_by(assignment_id=assignment.id).count()
                
                result.append({
                    "id": assignment.id,
                    "name": assignment.name,
                    "date": assignment.date.isoformat() if assignment.date else None,
                    "max_points": assignment.max_points,
                    "student_count": grade_count
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving assignments: {e}")
            raise
    
    def find_or_create_assignment(self, name: str, assignment_date: Optional[date], 
                                max_points: float, db: Session) -> Assignment:
        """Find existing assignment or create new one"""
        try:
            # Search for existing assignment
            if assignment_date is None:
                assignment = db.query(Assignment).filter(
                    and_(Assignment.name == name, Assignment.date.is_(None))
                ).first()
            else:
                assignment = db.query(Assignment).filter_by(
                    name=name, date=assignment_date
                ).first()
            
            # Create new assignment if not found
            if not assignment:
                assignment = Assignment(
                    name=name,
                    date=assignment_date,
                    max_points=max_points
                )
                db.add(assignment)
                db.flush()  # Get the ID
                logger.info(f"Created new assignment: {name}")
            
            return assignment
            
        except Exception as e:
            logger.error(f"Error finding/creating assignment {name}: {e}")
            raise
    
    def create_or_update_grade(self, email: str, assignment_id: int, 
                             score: float, db: Session) -> None:
        """Create or update grade record"""
        try:
            grade = db.query(Grade).filter_by(
                email=email, assignment_id=assignment_id
            ).first()
            
            if grade:
                grade.score = score
                logger.debug(f"Updated grade for {email}, assignment {assignment_id}")
            else:
                grade = Grade(
                    email=email,
                    assignment_id=assignment_id,
                    score=score
                )
                db.add(grade)
                logger.debug(f"Created grade for {email}, assignment {assignment_id}")
                
        except Exception as e:
            logger.error(f"Error creating/updating grade for {email}: {e}")
            raise

# ==============================================================================
# services/__init__.py
# ==============================================================================

from .csv_processor import CSVProcessor
from .student_service import StudentService
from .assignment_service import AssignmentService

__all__ = ["CSVProcessor", "StudentService", "AssignmentService"]
