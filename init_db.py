from database import Base, engine
from models import Student, Assignment, Grade  # Import any other models you’ve added

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done.")


