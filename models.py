from sqlalchemy import Column, Integer, Float, String, DateTime, func
from database import Base  
class Lectura(Base):
    __tablename__ = "lecturas"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), nullable=False, index=True)
    temperatura = Column(Float, nullable=False)
    humedad = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Vinculacion(Base):
    __tablename__ = "vinculaciones"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, nullable=False, index=True)
    nombre_usuario = Column(String(100), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())