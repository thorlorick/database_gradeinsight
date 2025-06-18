# ==============================================================================
# utils/logging.py - Logging configuration for GradeInsight
# ==============================================================================

"""
Centralized logging configuration for the GradeInsight application.
Provides structured logging with different levels, formatters, and handlers
for development, testing, and production environments.
"""

import logging
import logging.config
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
import json
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if they exist and include_extra is True
        if self.include_extra and hasattr(record, '__dict__'):
            extra_fields = {
                key: value for key, value in record.__dict__.items()
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                              'filename', 'module', 'lineno', 'funcName', 'created', 'msecs',
                              'relativeCreated', 'thread', 'threadName', 'processName',
                              'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']
            }
            if extra_fields:
                log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors:
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            
            # Format: [TIMESTAMP] LEVEL LOGGER:FUNCTION:LINE - MESSAGE
            formatted = (
                f"{color}[{datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{record.levelname:8} {record.name}:{record.funcName}:{record.lineno} - "
                f"{record.getMessage()}{reset}"
            )
        else:
            formatted = (
                f"[{datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{record.levelname:8} {record.name}:{record.funcName}:{record.lineno} - "
                f"{record.getMessage()}"
            )
        
        # Add exception information if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


def setup_logging(
    level: str = None,
    log_file: str = None,
    log_dir: str = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    use_json: bool = False,
    use_colors: bool = True,
    include_extra: bool = True
) -> None:
    """
    Setup logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Name of the log file (default: gradeinsight.log)
        log_dir: Directory for log files (default: logs)
        max_file_size: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        use_json: Whether to use JSON formatting for file logs
        use_colors: Whether to use colors in console output
        include_extra: Whether to include extra fields in JSON logs
    """
    # Set default values
    level = level or os.getenv('LOG_LEVEL', 'INFO').upper()
    log_file = log_file or 'gradeinsight.log'
    log_dir = log_dir or os.getenv('LOG_DIR', 'logs')
    
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Full path to log file
    full_log_path = log_path / log_file
    
    # Create formatters
    if use_json:
        file_formatter = JSONFormatter(include_extra=include_extra)
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
    
    console_formatter = ColoredFormatter(use_colors=use_colors)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        full_log_path,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, level))
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Suppress some noisy loggers in production
    if level in ['WARNING', 'ERROR', 'CRITICAL']:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logging.info(f"Logging initialized - Level: {level}, File: {full_log_path}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_function_call(logger: logging.Logger, include_args: bool = True, include_result: bool = False):
    """
    Decorator to log function calls.
    
    Args:
        logger: Logger instance to use
        include_args: Whether to log function arguments
        include_result: Whether to log function return value
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log function entry
            if include_args:
                logger.debug(f"Calling {func_name} with args={args}, kwargs={kwargs}")
            else:
                logger.debug(f"Calling {func_name}")
            
            try:
                result = func(*args, **kwargs)
                
                # Log successful completion
                if include_result:
                    logger.debug(f"{func_name} completed successfully, result={result}")
                else:
                    logger.debug(f"{func_name} completed successfully")
                
                return result
                
            except Exception as e:
                logger.error(f"{func_name} failed with exception: {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator


def log_database_operation(logger: logging.Logger, operation: str):
    """
    Decorator to log database operations.
    
    Args:
        logger: Logger instance to use
        operation: Description of the database operation
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Starting database operation: {operation}")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Database operation completed: {operation}")
                return result
                
            except Exception as e:
                logger.error(f"Database operation failed: {operation} - {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator


class LoggingContext:
    """Context manager for adding extra logging context"""
    
    def __init__(self, logger: logging.Logger, **extra_fields):
        self.logger = logger
        self.extra_fields = extra_fields
        self.old_logger = None
    
    def __enter__(self):
        # Create a new logger adapter with extra fields
        self.old_logger = self.logger
        return logging.LoggerAdapter(self.logger, self.extra_fields)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original logger
        pass


# ==============================================================================
# Logging configuration dictionaries
# ==============================================================================

def get_development_config() -> Dict[str, Any]:
    """Get logging configuration for development environment"""
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            },
            'simple': {
                'format': '%(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': 'logs/gradeinsight_dev.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 3,
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            'gradeinsight': {
                'level': 'DEBUG',
                'handlers': ['console', 'file'],
                'propagate': False
            },
            'sqlalchemy.engine': {
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }


def get_production_config() -> Dict[str, Any]:
    """Get logging configuration for production environment"""
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': 'utils.logging.JSONFormatter',
                'include_extra': True
            },
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'INFO',
                'formatter': 'json',
                'filename': 'logs/gradeinsight.log',
                'maxBytes': 50485760,  # 50MB
                'backupCount': 10,
                'encoding': 'utf-8'
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'json',
                'filename': 'logs/gradeinsight_errors.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            'gradeinsight': {
                'level': 'INFO',
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False
            }
        },
        'root': {
            'level': 'WARNING',
            'handlers': ['console']
        }
    }


def configure_logging_from_dict(config: Dict[str, Any]) -> None:
    """Configure logging using a dictionary configuration"""
    # Ensure log directory exists
    for handler_name, handler_config in config.get('handlers', {}).items():
        if 'filename' in handler_config:
            log_file = Path(handler_config['filename'])
            log_file.parent.mkdir(parents=True, exist_ok=True)
    
    logging.config.dictConfig(config)


# ==============================================================================
# Environment-specific setup functions
# ==============================================================================

def setup_development_logging():
    """Setup logging for development environment"""
    config = get_development_config()
    configure_logging_from_dict(config)


def setup_production_logging():
    """Setup logging for production environment"""
    config = get_production_config()
    configure_logging_from_dict(config)


def setup_testing_logging():
    """Setup minimal logging for testing environment"""
    logging.basicConfig(
        level=logging.ERROR,  # Only log errors during testing
        format='%(levelname)s - %(name)s - %(message)s'
    )
    
    # Suppress database logs during testing
    logging.getLogger('sqlalchemy').setLevel(logging.ERROR)


# ==============================================================================
# Auto-configuration based on environment
# ==============================================================================

def auto_configure_logging():
    """Automatically configure logging based on environment variables"""
    env = os.getenv('ENVIRONMENT', 'development').lower()
    
    if env == 'production':
        setup_production_logging()
    elif env == 'testing':
        setup_testing_logging()
    else:  # development or any other environment
        setup_development_logging()
    
    logger = get_logger(__name__)
    logger.info(f"Logging configured for {env} environment")


# Initialize logging when module is imported
if __name__ != '__main__':
    # Only auto-configure if not being run as a script
    try:
        auto_configure_logging()
    except Exception as e:
        # Fallback to basic configuration if auto-configuration fails
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Failed to auto-configure logging: {e}")


if __name__ == '__main__':
    # Demo/testing code when run as a script
    print("Testing logging configuration...")
    
    setup_development_logging()
    logger = get_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test with extra context
    with LoggingContext(logger, user_id="test_user", operation="demo") as ctx_logger:
        ctx_logger.info("This message has extra context")
    
    print("Logging test completed. Check logs directory for output files.")
