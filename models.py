from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func

class Vinculacion(Base):
    __tablename__ = "vinculaciones"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, nullable=False, index=True)
    nombre_usuario = Column(String(100), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())