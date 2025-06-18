##### START OF FILE ######
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class Tenant(Base):
    __tablename__ = 'tenants'
    id = Column(String, primary_key=True)  # e.g., "lincoln_high"
    name = Column(String, nullable=False)  # e.g., "Lincoln High School"

    students = relationship("Student", back_populates="tenant")
    assignments = relationship("Assignment", back_populates="tenant")
    tags = relationship("Tag", back_populates="tenant")

class Student(Base):
    __tablename__ = 'students'
    email = Column(String, primary_key=True, index=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    student_number = Column(String, nullable=True)
    tenant_id = Column(String, ForeignKey('tenants.id'), nullable=False)

    grades = relationship("Grade", back_populates="student")
    tenant = relationship("Tenant", back_populates="students")

class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    date = Column(Date, nullable=True)
    max_points = Column(Float, nullable=False)
    tenant_id = Column(String, ForeignKey('tenants.id'), nullable=False)

    grades = relationship("Grade", back_populates="assignment")
    tenant = relationship("Tenant", back_populates="assignments")
    assignment_tags = relationship("AssignmentTag", back_populates="assignment")

class Grade(Base):
    __tablename__ = 'grades'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, ForeignKey('students.email'), nullable=False)
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)
    score = Column(Float)

    student = relationship("Student", back_populates="grades")
    assignment = relationship("Assignment", back_populates="grades")

class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey('tenants.id'), nullable=False)

    tenant = relationship("Tenant", back_populates="tags")
    assignment_tags = relationship("AssignmentTag", back_populates="tag")

    __table_args__ = (UniqueConstraint('name', 'tenant_id'),)

class AssignmentTag(Base):
    __tablename__ = 'assignment_tags'
    assignment_id = Column(Integer, ForeignKey('assignments.id'), primary_key=True)
    tag_id = Column(Integer, ForeignKey('tags.id'), primary_key=True)

    assignment = relationship("Assignment", back_populates="assignment_tags")
    tag = relationship("Tag", back_populates="assignment_tags")
###### END OF FILE ########
