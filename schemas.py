from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class LecturaBase(BaseModel):
    temperatura: float
    humedad: float
    device_id: Optional[str] = "esp32_01"

class LecturaCreate(LecturaBase):
    pass

class LecturaResponse(LecturaBase):
    id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True

class LecturaList(BaseModel):
    data: List[LecturaResponse]
    count: int