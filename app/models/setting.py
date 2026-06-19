from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())
