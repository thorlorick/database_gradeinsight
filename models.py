from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Student(Base):
    __tablename__ = 'students'
    email = Column(String, primary_key=True, index=True, nullable=False)  # email is now the unique ID
    first_name = Column(String)
    last_name = Column(String)
    student_number = Column(String, nullable=True)  # optional or legacy field
    grades = relationship("Grade", back_populates="student")

class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    date = Column(Date, nullable=True)
    max_points = Column(Float, nullable=False)
    grades = relationship("Grade", back_populates="assignment")

class Grade(Base):
    __tablename__ = 'grades'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, ForeignKey('students.email'), nullable=False)  # foreign key to student email
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)
    score = Column(Float)

    student = relationship("Student", back_populates="grades")
    assignment = relationship("Assignment", back_populates="grades")
