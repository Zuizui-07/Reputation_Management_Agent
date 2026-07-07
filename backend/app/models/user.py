"""
================================================
  User Model — Admin user for dashboard access
================================================
"""

import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        SAEnum("superadmin", "admin", name="user_role_enum"),
        default="admin",
        server_default="admin",
        nullable=False,
    )
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
