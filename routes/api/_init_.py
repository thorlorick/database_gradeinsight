# routes/api/__init__.py
from fastapi import APIRouter
from . import students  # import more files as you split them

router = APIRouter()
router.include_router(students.router)
