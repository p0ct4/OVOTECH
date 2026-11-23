
# Importamos las herramientas necesarias de SQLAlchemy para definir
# las columnas y los tipos de datos de nuestras tablas.
from sqlalchemy import Column, Integer, Float, String, DateTime, func

# Importamos Base desde database.py.
# Es la clase base de la que heredarán nuestros modelos.
from database import Base


# ============================================================
# MODELO LECTURA
# ============================================================

# Creamos la clase Lectura que representa la tabla de lecturas
# dentro de la base de datos PostgreSQL.
class Lectura(Base):

    # Definimos el nombre de la tabla en PostgreSQL.
    __tablename__ = "lecturas"

    # Identificador único de cada lectura.
    # primary_key=True indica que es la clave primaria.
    # index=True permite realizar búsquedas más rápidas por este campo.
    id = Column(Integer, primary_key=True, index=True)

    # Identificador de la incubadora que envió los datos.
    # String(50) permite almacenar hasta 50 caracteres.
    # nullable=False significa que este campo no puede estar vacío.
    # index=True facilita las búsquedas por dispositivo.
    device_id = Column(String(50), nullable=False, index=True)

    # Almacena la temperatura registrada por el sensor.
    # Float permite guardar números decimales.
    # nullable=False indica que el valor es obligatorio.
    temperatura = Column(Float, nullable=False)

    # Almacena el porcentaje de humedad registrado por el sensor.
    # Float permite guardar números decimales.
    # nullable=False indica que el valor es obligatorio.
    humedad = Column(Float, nullable=False)

    # Almacena la fecha y hora en la que se registra la lectura.
    # DateTime(timezone=True) permite trabajar con fechas que incluyen zona horaria.
    # server_default=func.now() establece automáticamente
    # la fecha y hora actual desde PostgreSQL al insertar un registro.
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# MODELO VINCULACION
# ============================================================

# Creamos la clase Vinculacion que representa la tabla
# donde se almacenan las incubadoras vinculadas al sistema.
class Vinculacion(Base):

    # Definimos el nombre de la tabla en PostgreSQL.
    __tablename__ = "vinculaciones"

    # Identificador único de cada vinculación.
    # primary_key=True establece que es la clave primaria.
    # index=True permite realizar búsquedas más rápidas.
    id = Column(Integer, primary_key=True, index=True)

    # Identificador de la incubadora que se está vinculando.
    # String(50) permite almacenar hasta 50 caracteres.
    # unique=True impide que un mismo dispositivo
    # se vincule más de una vez.
    # nullable=False significa que el campo es obligatorio.
    # index=True facilita las búsquedas por device_id.
    device_id = Column(String(50), unique=True, nullable=False, index=True)

    # Almacena el nombre asignado por el usuario a la incubadora.
    # String(100) permite almacenar hasta 100 caracteres.
    # nullable=True significa que este campo puede quedar vacío.
    nombre_usuario = Column(String(100), nullable=True)

    # Guarda la fecha y hora en la que se realizó la vinculación.
    # DateTime(timezone=True) permite almacenar información de zona horaria.
    # server_default=func.now() establece automáticamente
    # la fecha y hora actual desde PostgreSQL al crear el registro.
    creado_en = Column(DateTime(timezone=True), server_default=func.now())
