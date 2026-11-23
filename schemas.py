
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


# ============================================================
# ESQUEMA BASE DE LECTURA
# ============================================================

# Define la estructura básica de una lectura de la incubadora.
# Se utiliza como base para los demás esquemas.
class LecturaBase(BaseModel):

    # Temperatura registrada por el sensor.
    temperatura: float

    # Porcentaje de humedad registrado por el sensor.
    humedad: float

    # Identificador de la incubadora que envía los datos.
    # Si no se proporciona, utiliza "esp32_01" por defecto.
    # Optional permite que el campo pueda ser None.
    device_id: Optional[str] = "esp32_01"


# ============================================================
# ESQUEMA PARA CREAR LECTURAS
# ============================================================

# Hereda los campos de LecturaBase.
# Se utiliza cuando se necesita crear una nueva lectura.
class LecturaCreate(LecturaBase):

    # pass indica que no agregamos campos nuevos
    # y utilizamos directamente los de LecturaBase.
    pass


# ============================================================
# ESQUEMA PARA RESPONDER CON UNA LECTURA
# ============================================================

# Hereda los campos de LecturaBase y agrega
# los datos que se generan al guardar la lectura.
class LecturaResponse(LecturaBase):

    # Identificador único de la lectura en la base de datos.
    id: int

    # Fecha y hora en la que se registró la lectura.
    timestamp: datetime

    # Configuración de Pydantic para permitir que el esquema
    # pueda obtener los datos directamente desde objetos ORM
    # de SQLAlchemy, en lugar de necesitar diccionarios.
    class Config:
        from_attributes = True


# ============================================================
# ESQUEMA PARA DEVOLVER UNA LISTA DE LECTURAS
# ============================================================

# Define la estructura de una respuesta que contiene
# varias lecturas de la incubadora.
class LecturaList(BaseModel):

    # Lista de lecturas.
    # Cada elemento debe cumplir con la estructura LecturaResponse.
    data: List[LecturaResponse]

    # Cantidad total de lecturas incluidas en la respuesta.
    count: int
