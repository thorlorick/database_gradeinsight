from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from database import Base

Base = declarative_base()

class Student(Base):
    __tablename__ = 'students'
    student_number = Column(String, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True, nullable=True)
    grades = relationship("Grade", back_populates="student")

class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    date = Column(Date, nullable=True)
    max_points = Column(Float)
    grades = relationship("Grade", back_populates="assignment")

class Grade(Base):
    __tablename__ = 'grades'
    id = Column(Integer, primary_key=True, index=True)
    student_number = Column(String, ForeignKey('students.student_number'))
    assignment_id = Column(Integer, ForeignKey('assignments.id'))
    score = Column(Float)

    student = relationship("Student", back_populates="grades")
    assignment = relationship("Assignment", back_populates="grades")

