"""
Manager-Department mapping model
"""
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base


class ManagerDepartment(Base):
    __tablename__ = "manager_departments"

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint('manager_id', 'department_id', name='uq_manager_department'),
    )

    # Relationships
    manager = relationship("Employee", back_populates="managed_departments")
    department = relationship("Department")
