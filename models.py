from sqlalchemy import Column, Integer, Float, DateTime, String, func
from database import Base

class Lectura(Base):
    __tablename__ = "lecturas"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), default="esp32_01")
    temperatura = Column(Float, nullable=False)
    humedad = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())