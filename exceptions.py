# ==============================================================================
# exceptions.py - Custom exception classes for GradeInsight
# ==============================================================================

"""
Custom exception classes for the GradeInsight application.
These exceptions provide specific error handling for database operations,
validation, and business logic errors.
"""

from typing import Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


class GradeInsightBaseException(Exception):
    """Base exception class for all GradeInsight-specific exceptions"""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
        
        # Log the exception when it's created
        logger.error(f"Exception raised: {self.__class__.__name__} - {message}", 
                    extra={"error_code": error_code, "details": details})


# ==============================================================================
# Database-related exceptions
# ==============================================================================

class DatabaseConnectionError(GradeInsightBaseException):
    """Raised when database connection fails"""
    pass


class DatabaseOperationError(GradeInsightBaseException):
    """Raised when a database operation fails"""
    pass


class TransactionError(GradeInsightBaseException):
    """Raised when a database transaction fails"""
    pass


class DatabaseIntegrityError(GradeInsightBaseException):
    """Raised when database integrity constraints are violated"""
    pass


# ==============================================================================
# Student-related exceptions
# ==============================================================================

class StudentError(GradeInsightBaseException):
    """Base exception for student-related errors"""
    pass


class StudentNotFoundError(StudentError):
    """Raised when a student cannot be found"""
    
    def __init__(self, email: str = None, student_number: str = None):
        identifier = email or student_number or "unknown"
        message = f"Student not found: {identifier}"
        super().__init__(message, "STUDENT_NOT_FOUND", {"identifier": identifier})


class StudentAlreadyExistsError(StudentError):
    """Raised when attempting to create a student that already exists"""
    
    def __init__(self, email: str):
        message = f"Student already exists with email: {email}"
        super().__init__(message, "STUDENT_EXISTS", {"email": email})


class InvalidStudentDataError(StudentError):
    """Raised when student data is invalid"""
    
    def __init__(self, field: str, value: Any, reason: str = None):
        message = f"Invalid student data - {field}: {value}"
        if reason:
            message += f" ({reason})"
        super().__init__(message, "INVALID_STUDENT_DATA", {"field": field, "value": value, "reason": reason})


# ==============================================================================
# Assignment-related exceptions
# ==============================================================================

class AssignmentError(GradeInsightBaseException):
    """Base exception for assignment-related errors"""
    pass


class AssignmentNotFoundError(AssignmentError):
    """Raised when an assignment cannot be found"""
    
    def __init__(self, assignment_id: int = None, assignment_name: str = None):
        identifier = assignment_id or assignment_name or "unknown"
        message = f"Assignment not found: {identifier}"
        super().__init__(message, "ASSIGNMENT_NOT_FOUND", {"identifier": identifier})


class InvalidAssignmentDataError(AssignmentError):
    """Raised when assignment data is invalid"""
    
    def __init__(self, field: str, value: Any, reason: str = None):
        message = f"Invalid assignment data - {field}: {value}"
        if reason:
            message += f" ({reason})"
        super().__init__(message, "INVALID_ASSIGNMENT_DATA", {"field": field, "value": value, "reason": reason})


class AssignmentDateError(AssignmentError):
    """Raised when assignment date is invalid"""
    
    def __init__(self, date_value: Any, reason: str = None):
        message = f"Invalid assignment date: {date_value}"
        if reason:
            message += f" ({reason})"
        super().__init__(message, "INVALID_ASSIGNMENT_DATE", {"date": date_value, "reason": reason})


# ==============================================================================
# Grade-related exceptions
# ==============================================================================

class GradeError(GradeInsightBaseException):
    """Base exception for grade-related errors"""
    pass


class GradeNotFoundError(GradeError):
    """Raised when a grade cannot be found"""
    
    def __init__(self, student_email: str = None, assignment_id: int = None, grade_id: int = None):
        if grade_id:
            message = f"Grade not found with ID: {grade_id}"
            details = {"grade_id": grade_id}
        elif student_email and assignment_id:
            message = f"Grade not found for student {student_email}, assignment {assignment_id}"
            details = {"student_email": student_email, "assignment_id": assignment_id}
        else:
            message = "Grade not found"
            details = {}
        super().__init__(message, "GRADE_NOT_FOUND", details)


class InvalidGradeError(GradeError):
    """Raised when a grade value is invalid"""
    
    def __init__(self, score: float, max_points: float, reason: str = None):
        message = f"Invalid grade: {score}/{max_points}"
        if reason:
            message += f" ({reason})"
        super().__init__(message, "INVALID_GRADE", {"score": score, "max_points": max_points, "reason": reason})


class GradeAlreadyExistsError(GradeError):
    """Raised when attempting to create a grade that already exists"""
    
    def __init__(self, student_email: str, assignment_id: int):
        message = f"Grade already exists for student {student_email}, assignment {assignment_id}"
        super().__init__(message, "GRADE_EXISTS", {"student_email": student_email, "assignment_id": assignment_id})


# ==============================================================================
# Validation exceptions
# ==============================================================================

class ValidationError(GradeInsightBaseException):
    """Base exception for validation errors"""
    pass


class EmailValidationError(ValidationError):
    """Raised when email format is invalid"""
    
    def __init__(self, email: str):
        message = f"Invalid email format: {email}"
        super().__init__(message, "INVALID_EMAIL", {"email": email})


class ScoreValidationError(ValidationError):
    """Raised when score validation fails"""
    
    def __init__(self, score: float, min_score: float = 0, max_score: float = None):
        message = f"Score {score} is out of valid range"
        if max_score is not None:
            message += f" ({min_score}-{max_score})"
        super().__init__(message, "INVALID_SCORE", {"score": score, "min_score": min_score, "max_score": max_score})


class RequiredFieldError(ValidationError):
    """Raised when a required field is missing or empty"""
    
    def __init__(self, field_name: str, entity_type: str = None):
        message = f"Required field missing: {field_name}"
        if entity_type:
            message += f" in {entity_type}"
        super().__init__(message, "REQUIRED_FIELD_MISSING", {"field": field_name, "entity_type": entity_type})


# ==============================================================================
# Import/Export exceptions
# ==============================================================================

class ImportExportError(GradeInsightBaseException):
    """Base exception for import/export operations"""
    pass


class FileNotFoundError(ImportExportError):
    """Raised when a file cannot be found"""
    
    def __init__(self, filepath: str):
        message = f"File not found: {filepath}"
        super().__init__(message, "FILE_NOT_FOUND", {"filepath": filepath})


class FileFormatError(ImportExportError):
    """Raised when file format is invalid or unsupported"""
    
    def __init__(self, filepath: str, expected_format: str = None, actual_format: str = None):
        message = f"Invalid file format: {filepath}"
        if expected_format:
            message += f" (expected: {expected_format}"
            if actual_format:
                message += f", got: {actual_format}"
            message += ")"
        super().__init__(message, "INVALID_FILE_FORMAT", 
                        {"filepath": filepath, "expected": expected_format, "actual": actual_format})


class DataParsingError(ImportExportError):
    """Raised when data cannot be parsed correctly"""
    
    def __init__(self, line_number: int = None, column: str = None, value: str = None, reason: str = None):
        message = "Data parsing error"
        if line_number:
            message += f" at line {line_number}"
        if column:
            message += f", column '{column}'"
        if value:
            message += f", value: {value}"
        if reason:
            message += f" ({reason})"
        
        super().__init__(message, "DATA_PARSING_ERROR", 
                        {"line": line_number, "column": column, "value": value, "reason": reason})


# ==============================================================================
# Configuration exceptions
# ==============================================================================

class ConfigurationError(GradeInsightBaseException):
    """Raised when configuration is invalid or missing"""
    pass


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when required environment variable is missing"""
    
    def __init__(self, variable_name: str):
        message = f"Required environment variable not set: {variable_name}"
        super().__init__(message, "MISSING_ENV_VAR", {"variable": variable_name})


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid"""
    
    def __init__(self, config_key: str, config_value: Any, reason: str = None):
        message = f"Invalid configuration - {config_key}: {config_value}"
        if reason:
            message += f" ({reason})"
        super().__init__(message, "INVALID_CONFIG", {"key": config_key, "value": config_value, "reason": reason})


# ==============================================================================
# Utility functions for exception handling
# ==============================================================================

def log_exception(exc: Exception, context: str = None, extra_data: Dict[str, Any] = None) -> None:
    """
    Log an exception with additional context and data.
    
    Args:
        exc: The exception to log
        context: Additional context about where the exception occurred
        extra_data: Additional data to include in the log
    """
    extra_info = {
        "exception_type": exc.__class__.__name__,
        "exception_message": str(exc)
    }
    
    if extra_data:
        extra_info.update(extra_data)
    
    if hasattr(exc, 'error_code'):
        extra_info["error_code"] = exc.error_code
    
    if hasattr(exc, 'details'):
        extra_info["exception_details"] = exc.details
    
    log_message = f"Exception occurred: {exc.__class__.__name__}"
    if context:
        log_message += f" in {context}"
    log_message += f" - {str(exc)}"
    
    logger.error(log_message, extra=extra_info)


def handle_database_error(exc: Exception, operation: str = None) -> GradeInsightBaseException:
    """
    Convert database exceptions to appropriate GradeInsight exceptions.
    
    Args:
        exc: The original database exception
        operation: The database operation that failed
        
    Returns:
        Appropriate GradeInsight exception
    """
    from sqlalchemy.exc import IntegrityError, OperationalError, DataError
    
    context = f"during {operation}" if operation else ""
    
    if isinstance(exc, IntegrityError):
        return DatabaseIntegrityError(f"Database integrity constraint violated {context}: {str(exc)}")
    elif isinstance(exc, OperationalError):
        return DatabaseConnectionError(f"Database connection failed {context}: {str(exc)}")
    elif isinstance(exc, DataError):
        return DatabaseOperationError(f"Database data error {context}: {str(exc)}")
    else:
        return DatabaseOperationError(f"Database operation failed {context}: {str(exc)}")
