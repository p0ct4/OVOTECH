
# Importamos create_engine para establecer la conexión con la base de datos
from sqlalchemy import create_engine

# Importamos declarative_base para crear la clase base de nuestros modelos
from sqlalchemy.ext.declarative import declarative_base

# Importamos sessionmaker para crear sesiones de conexión con la base de datos
from sqlalchemy.orm import sessionmaker

# Importamos os para acceder a las variables de entorno del sistema
import os

# Importamos load_dotenv para cargar las variables del archivo .env
from dotenv import load_dotenv


# Cargamos las variables de entorno del archivo .env
load_dotenv()


# Obtenemos la URL de conexión a la base de datos desde el archivo .env
DATABASE_URL = os.getenv("DATABASE_URL")


# Comprobamos que exista la URL de conexión
# Si no está configurada, detenemos la ejecución y mostramos un error
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL no está configurada")


# Creamos el motor de conexión con la base de datos
# pool_pre_ping=True comprueba que la conexión esté activa antes de utilizarla
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


# Creamos una fábrica de sesiones para interactuar con la base de datos
# autocommit=False: los cambios deben confirmarse manualmente
# autoflush=False: evita enviar cambios automáticamente antes de ciertas consultas
# bind=engine: vincula las sesiones con el motor de conexión creado anteriormente
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Creamos la clase base de la que heredarán todos nuestros modelos
# Por ejemplo: Usuario, Lectura, Dispositivo, etc.
Base = declarative_base()


# Función que proporciona una sesión de base de datos
# Se utiliza normalmente como dependencia en los endpoints de FastAPI
def get_db():

    # Creamos una nueva sesión de conexión con la base de datos
    db = SessionLocal()

    try:
        # Entregamos la sesión para que pueda utilizarse en las consultas
        yield db

    finally:
        # Cerramos la sesión cuando termina la operación
        # Esto evita dejar conexiones abiertas innecesariamente
        db.close()
