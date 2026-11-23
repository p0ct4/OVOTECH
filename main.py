
# Importamos asyncio para trabajar con operaciones asíncronas
# y ejecutar tareas dentro del bucle principal de FastAPI.
import asyncio

# Importamos os para acceder a las variables de entorno del sistema,
# como el puerto en el que se ejecutará el servidor.
import os

# Importamos asynccontextmanager para gestionar el inicio y cierre
# de la aplicación FastAPI.
from contextlib import asynccontextmanager

# Importamos datetime para trabajar con fechas y horarios.
from datetime import datetime

# Importamos BaseModel para crear modelos de validación de datos
# que recibirá nuestra API.
from pydantic import BaseModel

# Importamos FastAPI para crear la API.
# WebSocket permite mantener conexiones en tiempo real.
# WebSocketDisconnect detecta cuando un cliente se desconecta.
# Depends permite utilizar dependencias, como la conexión a la base de datos.
# HTTPException permite devolver errores HTTP personalizados.
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException

# Importamos CORSMiddleware para permitir que el frontend
# pueda comunicarse con el backend desde otros dominios.
from fastapi.middleware.cors import CORSMiddleware

# Importamos StaticFiles para servir archivos estáticos,
# como HTML, CSS, JavaScript e imágenes.
from fastapi.staticfiles import StaticFiles

# Importamos Session para indicar el tipo de sesión
# que utilizaremos al trabajar con SQLAlchemy.
from sqlalchemy.orm import Session


# Importamos los elementos necesarios para trabajar con la base de datos.
# engine: motor de conexión con PostgreSQL.
# Base: clase base de nuestros modelos.
# SessionLocal: fábrica que crea sesiones de base de datos.
# get_db: función que proporciona una sesión a los endpoints.
from database import engine, Base, SessionLocal, get_db

# Importamos los modelos que representan las tablas de la base de datos.
# Lectura: almacena las mediciones de temperatura y humedad.
# Vinculacion: almacena los dispositivos vinculados.
from models import Lectura, Vinculacion

# Importamos los esquemas que definen la estructura
# de los datos que devolverán los endpoints.
from schemas import LecturaResponse, LecturaList

# Importamos el administrador de conexiones WebSocket.
# Se encarga de gestionar los clientes conectados y enviarles información.
from websocket_manager import manager

# Importamos la clase encargada de conectarse al servidor MQTT
# y recibir los mensajes enviados por las incubadoras ESP32.
from mqtt_client import MQTTClient


# Variable global que almacenará el bucle principal de eventos de FastAPI.
# Se utiliza para poder ejecutar operaciones asíncronas desde el hilo de MQTT.
_loop_principal = None


# ============================================================
# PROCESADOR MQTT
# ============================================================

# Esta función se ejecuta cada vez que el cliente MQTT recibe
# un mensaje enviado por una incubadora ESP32.
# Recibe un diccionario (payload) con los datos del sensor.
def process_mqtt_message(payload: dict):

    # Creamos una sesión independiente con la base de datos.
    db = SessionLocal()

    try:
        # Creamos un nuevo objeto Lectura con los datos recibidos.
        lectura = Lectura(

            # Obtenemos la temperatura del mensaje MQTT.
            # Si no existe el dato, utilizamos 0 como valor predeterminado.
            # float() convierte el valor a número decimal.
            temperatura=float(payload.get("temperatura", 0)),

            # Obtenemos la humedad recibida desde el ESP32.
            # También la convertimos a número decimal.
            humedad=float(payload.get("humedad", 0)),

            # Obtenemos el identificador de la incubadora.
            # str() garantiza que el valor sea una cadena de texto.
            device_id=str(payload.get("device_id", "desconocido"))
        )

        # Agregamos la nueva lectura a la sesión de la base de datos.
        db.add(lectura)

        # Confirmamos los cambios y guardamos la lectura en PostgreSQL.
        db.commit()

        # Actualizamos el objeto para obtener los datos generados
        # por la base de datos, como el ID y la fecha de registro.
        db.refresh(lectura)

        # Mostramos en la terminal información de la lectura guardada.
        print(f"[{lectura.device_id}] ID={lectura.id}, Temp={lectura.temperatura}°C")


        # ============================================================
        # ROTACIÓN DE LECTURAS
        # ============================================================

        # Consultamos cuántas lecturas existen para esta incubadora.
        # El filtro device_id permite que cada dispositivo
        # tenga su propio límite de almacenamiento.
        total = db.query(Lectura).filter(
            Lectura.device_id == lectura.device_id
        ).count()

        # Si existen más de 50 lecturas, eliminamos las más antiguas.
        if total > 50:

            # Buscamos la fecha de la lectura número 51,
            # ordenando las lecturas desde la más reciente
            # hasta la más antigua.
            #
            # offset(50) salta las primeras 50 lecturas.
            # limit(1) obtiene solamente una fecha.
            # scalar() devuelve directamente el valor encontrado.
            limite = db.query(Lectura.timestamp)\
                .filter(Lectura.device_id == lectura.device_id)\
                .order_by(Lectura.timestamp.desc())\
                .offset(50)\
                .limit(1)\
                .scalar()

            # Si encontramos una fecha límite, eliminamos
            # las lecturas anteriores o iguales a esa fecha.
            if limite:

                db.query(Lectura)\
                    .filter(
                        Lectura.device_id == lectura.device_id,
                        Lectura.timestamp <= limite
                    )\
                    .delete(synchronize_session=False)

                # Confirmamos la eliminación en PostgreSQL.
                db.commit()

                # Informamos que se realizó la limpieza de lecturas.
                print(f"Rotación: {lectura.device_id} limpiado")


        # ============================================================
        # ENVÍO DE DATOS POR WEBSOCKET
        # ============================================================

        # Creamos un diccionario con la información de la lectura.
        # Este será el mensaje que recibirá el frontend en tiempo real.
        msg = {
            "type": "lectura",
            "data": {

                # Identificador único de la lectura.
                "id": lectura.id,

                # Temperatura registrada por el sensor.
                "temperatura": lectura.temperatura,

                # Humedad registrada por el sensor.
                "humedad": lectura.humedad,

                # Identificador de la incubadora que envió los datos.
                "device_id": lectura.device_id,

                # Fecha y hora de la lectura convertida a formato ISO.
                # Si no existe un timestamp, utilizamos la fecha actual.
                "timestamp": lectura.timestamp.isoformat()
                if lectura.timestamp else datetime.now().isoformat()
            }
        }

        # Comprobamos que el bucle principal de FastAPI esté disponible.
        if _loop_principal is not None:

            # Ejecutamos la operación asíncrona de broadcast
            # desde el hilo en el que se está ejecutando MQTT.
            #
            # Esto permite enviar la lectura a todos los clientes
            # conectados mediante WebSocket.
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(msg),
                _loop_principal
            )

    except Exception as e:

        # Si ocurre algún error durante el procesamiento,
        # mostramos el mensaje en la terminal.
        print(f"Error MQTT: {e}")

        # Deshacemos los cambios pendientes de la transacción.
        db.rollback()

    finally:

        # Cerramos la sesión de la base de datos
        # independientemente de si ocurrió un error o no.
        db.close()


# Creamos una instancia del cliente MQTT.
# Le pasamos process_mqtt_message como función encargada
# de procesar los mensajes recibidos desde las incubadoras.
mqtt_client = MQTTClient(message_handler=process_mqtt_message)


# ============================================================
# LIFESPAN
# ============================================================

# Definimos el ciclo de vida de la aplicación FastAPI.
# Esta función controla qué sucede cuando el servidor inicia
# y qué sucede cuando se apaga.
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Indicamos que vamos a modificar la variable global
    # que almacena el bucle principal de eventos.
    global _loop_principal

    # Obtenemos el bucle de eventos que utiliza FastAPI.
    # Será necesario para enviar mensajes WebSocket desde MQTT.
    _loop_principal = asyncio.get_running_loop()

    # Creamos automáticamente las tablas de la base de datos
    # que todavía no existan, utilizando los modelos definidos en Base.
    Base.metadata.create_all(bind=engine)

    # Informamos que las tablas de la base de datos están listas.
    print("Tablas listas")

    # Iniciamos el cliente MQTT para comenzar a recibir
    # información enviada por las incubadoras ESP32.
    mqtt_client.start()

    # Informamos que el servidor de OVOTECH está funcionando.
    print("OVOTECH en línea")

    # A partir de yield, la aplicación permanece funcionando
    # y atendiendo las solicitudes de los usuarios.
    yield

    # Cuando FastAPI se apaga, detenemos la conexión MQTT.
    mqtt_client.stop()


# ============================================================
# APP FASTAPI (CREAR PRIMERO)
# ============================================================

# Creamos la aplicación principal de FastAPI.
# title establece el nombre que aparecerá en la documentación de la API.
# lifespan conecta nuestra función de inicio y cierre con FastAPI.
app = FastAPI(title="OVOTECH API", lifespan=lifespan)


# ============================================================
# CONFIGURACIÓN CORS
# ============================================================

# Definimos los dominios que tienen permiso para comunicarse
# con nuestro backend.
origins = [

    # Dirección local donde puede ejecutarse el frontend.
    "http://localhost:8000",

    # Dirección alternativa para ejecutar el frontend localmente.
    "http://localhost:5500",

    # Dominio donde está publicado el frontend de OVOTECH.
    "https://ovo-tech.netlify.app",
]

# Agregamos el middleware CORS a FastAPI.
app.add_middleware(

    # Middleware encargado de controlar las solicitudes entre dominios.
    CORSMiddleware,

    # Permitimos solicitudes desde los dominios definidos anteriormente.
    allow_origins=origins,

    # Permitimos el envío de credenciales en las solicitudes.
    allow_credentials=True,

    # Permitimos todos los métodos HTTP, como GET, POST, PUT y DELETE.
    allow_methods=["*"],

    # Permitimos todos los encabezados HTTP.
    allow_headers=["*"],
)


# ============================================================
# ARCHIVOS ESTÁTICOS
# ============================================================

# Publicamos la carpeta static para que pueda accederse
# desde el navegador mediante la ruta /static.
#
# Por ejemplo: /static/index.html
# Esto permite servir archivos HTML, CSS, JavaScript e imágenes.
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================
# SCHEMAS
# ============================================================

# Creamos un esquema de validación para recibir los datos
# necesarios al momento de vincular una incubadora.
class VinculacionCreate(BaseModel):

    # Identificador único de la incubadora.
    # Ejemplo: OVOTECH_001.
    device_id: str

    # Nombre opcional que el usuario puede asignarle
    # a la incubadora.
    # Si no se proporciona, su valor será None.
    nombre_usuario: str | None = None


# ============================================================
# ENDPOINTS
# ============================================================

# Los endpoints son las rutas que permiten al frontend
# comunicarse con el backend y realizar diferentes operaciones.


# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================

# Definimos una ruta GET en la dirección principal de la API.
# Se utiliza para comprobar que el backend está funcionando.
@app.get("/")
async def root():

    # Devolvemos un objeto JSON con el nombre de la API
    # y la dirección de la documentación o página estática.
    return {
        "message": "OVOTECH API",
        "docs": "/static/index.html"
    }


# ============================================================
# VINCULAR DISPOSITIVO
# ============================================================

# Definimos una ruta POST para vincular una incubadora
# con el usuario que la va a utilizar.
@app.post("/api/vincular")
async def vincular_dispositivo(
    data: VinculacionCreate,
    db: Session = Depends(get_db)
):

    # PASO 1:
    # Comprobamos que la incubadora exista en el sistema.
    # Para ello buscamos si tiene al menos una lectura guardada.
    existe_lectura = db.query(Lectura).filter(
        Lectura.device_id == data.device_id
    ).first()

    # Si no encontramos ninguna lectura, significa que el dispositivo
    # todavía no envió información al backend.
    if not existe_lectura:

        # Devolvemos un error HTTP 404 indicando que no se encontró
        # la incubadora y que debe encenderse para enviar datos.
        raise HTTPException(
            status_code=404,
            detail=f"Incubadora '{data.device_id}' no encontrada. Encendela y esperá que envíe datos primero."
        )


    # PASO 2:
    # Comprobamos si la incubadora ya estaba vinculada.
    existente = db.query(Vinculacion).filter(
        Vinculacion.device_id == data.device_id
    ).first()

    # Si ya existe una vinculación, evitamos crear otra duplicada.
    if existente:

        # Devolvemos un mensaje indicando que ya estaba vinculada.
        return {
            "message": "Ya vinculado",
            "device_id": data.device_id
        }


    # PASO 3:
    # Si la incubadora existe y todavía no está vinculada,
    # creamos un nuevo registro en la tabla Vinculacion.
    vinculo = Vinculacion(
        device_id=data.device_id,
        nombre_usuario=data.nombre_usuario
    )

    # Agregamos la vinculación a la sesión de la base de datos.
    db.add(vinculo)

    # Confirmamos los cambios y guardamos la vinculación.
    db.commit()

    # Devolvemos una respuesta confirmando que se vinculó correctamente.
    return {
        "message": "Vinculado correctamente",
        "device_id": data.device_id
    }


# ============================================================
# OBTENER DISPOSITIVOS VINCULADOS
# ============================================================

# Definimos una ruta GET para consultar todos los dispositivos
# que se encuentran registrados en la tabla Vinculacion.
@app.get("/api/mis-dispositivos")
async def mis_dispositivos(db: Session = Depends(get_db)):

    # Consultamos todos los registros de la tabla Vinculacion.
    dispositivos = db.query(Vinculacion).all()

    # Devolvemos una lista con el identificador y el nombre
    # asignado a cada incubadora.
    return {
        "dispositivos": [
            {
                "id": d.device_id,
                "nombre": d.nombre_usuario
            }
            for d in dispositivos
        ]
    }


# ============================================================
# OBTENER TODAS LAS LECTURAS
# ============================================================

# Definimos una ruta GET para obtener las lecturas almacenadas.
# limit permite establecer cuántas lecturas queremos recuperar.
# Por defecto devuelve las últimas 50.
@app.get("/api/lecturas", response_model=LecturaList)
async def get_lecturas(
    limit: int = 50,
    db: Session = Depends(get_db)
):

    # Consultamos las lecturas ordenándolas desde la más reciente
    # hasta la más antigua.
    # limit() establece la cantidad máxima de registros.
    lecturas = db.query(Lectura)\
        .order_by(Lectura.timestamp.desc())\
        .limit(limit)\
        .all()

    # Invertimos la lista para devolver las lecturas
    # desde la más antigua hasta la más reciente.
    #
    # Esto puede resultar útil para mostrar los datos
    # en orden cronológico en el frontend.
    #
    # También devolvemos la cantidad de registros obtenidos.
    return {
        "data": list(reversed(lecturas)),
        "count": len(lecturas)
    }


# ============================================================
# OBTENER LECTURAS DE UNA INCUBADORA ESPECÍFICA
# ============================================================

# Definimos una ruta GET que permite consultar las lecturas
# de una incubadora determinada utilizando su device_id.
@app.get("/api/lecturas/{device_id}", response_model=LecturaList)
async def get_lecturas_device(
    device_id: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):

    # Consultamos las lecturas que pertenecen al device_id recibido.
    # Las ordenamos desde la más reciente hasta la más antigua.
    # limit establece cuántas lecturas queremos obtener.
    lecturas = db.query(Lectura)\
        .filter(Lectura.device_id == device_id)\
        .order_by(Lectura.timestamp.desc())\
        .limit(limit)\
        .all()

    # Invertimos los resultados para devolverlos
    # en orden cronológico y enviamos la cantidad de registros.
    return {
        "data": list(reversed(lecturas)),
        "count": len(lecturas)
    }


# ============================================================
# OBTENER LA ÚLTIMA LECTURA DE UNA INCUBADORA
# ============================================================

# Definimos una ruta GET para recuperar solamente
# la última medición de una incubadora específica.
@app.get(
    "/api/lecturas/ultima/{device_id}",
    response_model=LecturaResponse
)
async def get_ultima_lectura(
    device_id: str,
    db: Session = Depends(get_db)
):

    # Buscamos las lecturas que pertenecen a la incubadora indicada.
    # Las ordenamos por timestamp desde la más reciente.
    # first() devuelve solamente el primer resultado.
    lectura = db.query(Lectura)\
        .filter(Lectura.device_id == device_id)\
        .order_by(Lectura.timestamp.desc())\
        .first()

    # Si no encontramos ninguna lectura, devolvemos un error HTTP 404.
    if not lectura:
        raise HTTPException(
            status_code=404,
            detail="Sin lecturas para este dispositivo"
        )

    # Si encontramos una lectura, la devolvemos al frontend.
    # FastAPI utiliza LecturaResponse para validar la respuesta.
    return lectura


# ============================================================
# WEBSOCKET
# ============================================================

# Definimos un endpoint WebSocket en la dirección /ws.
# A diferencia de HTTP, WebSocket mantiene una conexión abierta
# entre el frontend y el backend.
#
# Esto permite enviar información en tiempo real sin que
# el frontend tenga que consultar constantemente la API.
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    # Registramos la conexión del cliente en el administrador WebSocket.
    # A partir de este momento puede recibir mensajes enviados
    # mediante manager.broadcast().
    await manager.connect(websocket)

    try:

        # Mantenemos la conexión abierta dentro de un bucle infinito.
        while True:

            # Esperamos recibir un mensaje de texto del frontend.
            data = await websocket.receive_text()

            # Comprobamos si el mensaje recibido es "ping".
            if data == "ping":

                # Respondemos con "pong".
                # Esto permite comprobar que la conexión sigue activa.
                await websocket.send_text("pong")

    # Detectamos cuando el cliente cierra la conexión WebSocket.
    except WebSocketDisconnect:

        # Eliminamos al cliente de la lista de conexiones activas.
        manager.disconnect(websocket)

    # Capturamos otros errores que puedan ocurrir durante
    # la comunicación WebSocket.
    except Exception:

        # También eliminamos la conexión si ocurre un error.
        manager.disconnect(websocket)


# ============================================================
# EJECUCIÓN DEL SERVIDOR
# ============================================================

# Comprobamos si este archivo se está ejecutando directamente.
# Esto evita iniciar el servidor automáticamente cuando
# main.py es importado desde otro archivo.
if __name__ == "__main__":

    # Importamos Uvicorn, el servidor ASGI que ejecutará FastAPI.
    import uvicorn

    # Iniciamos el servidor de OVOTECH.
    uvicorn.run(

        # Aplicación FastAPI que queremos ejecutar.
        app,

        # host="0.0.0.0" permite recibir conexiones externas,
        # no solamente conexiones desde la propia computadora.
        host="0.0.0.0",

        # Obtenemos el puerto desde la variable de entorno PORT.
        # Si no existe, utilizamos el puerto 8000 por defecto.
        port=int(os.getenv("PORT", 8000))
    )
