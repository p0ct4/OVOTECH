import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import engine, Base, SessionLocal, get_db
from models import Lectura
from schemas import LecturaResponse, LecturaList
from websocket_manager import manager
from mqtt_client import MQTTClient

# ============================================================
# VARIABLE GLOBAL: Guarda el loop principal de asyncio
# Necesaria porque MQTT corre en un hilo separado y necesita
# enviar datos a los WebSockets que viven en el loop principal.
# ============================================================
_loop_principal = None


# ============================================================
# 1. PROCESADOR DE MENSAJES MQTT
# Esta función se ejecuta CADA VEZ que la ESP32 envía datos
# a HiveMQ. Corre en un hilo separado (no en async).
# ============================================================
def process_mqtt_message(payload: dict):
    """
    1. Guarda la lectura en PostgreSQL
    2. Envía el dato a todos los navegadores conectados vía WebSocket
    """
    db = SessionLocal()
    try:
        # Crear objeto para la base de datos
        lectura = Lectura(
            temperatura=float(payload.get("temperatura", 0)),
            humedad=float(payload.get("humedad", 0)),
            device_id=str(payload.get("device_id", "esp32_01"))
        )
        
        # Guardar en PostgreSQL
        db.add(lectura)
        db.commit()
        db.refresh(lectura)
        
        print(f"💾 PostgreSQL: Guardada lectura ID={lectura.id} | "
              f"Temp={lectura.temperatura}°C | Hum={lectura.humedad}%")

        # Preparar mensaje para los navegadores
        msg = {
            "type": "lectura",
            "data": {
                "id": lectura.id,
                "temperatura": lectura.temperatura,
                "humedad": lectura.humedad,
                "device_id": lectura.device_id,
                "timestamp": lectura.timestamp.isoformat() if lectura.timestamp else datetime.now().isoformat()
            }
        }

        # Enviar a todos los clientes WebSocket conectados
        # asyncio.run_coroutine_threadsafe es SEGURO desde un hilo
        if _loop_principal is not None:
            asyncio.run_coroutine_threadsafe(manager.broadcast(msg), _loop_principal)
        else:
            print("⚠️ Loop principal aún no listo, mensaje no enviado a WS")

    except Exception as e:
        print(f"❌ Error en process_mqtt_message: {e}")
        db.rollback()
    finally:
        db.close()


# ============================================================
# 2. CLIENTE MQTT
# Instanciamos DESPUÉS de definir process_mqtt_message
# ============================================================
mqtt_client = MQTTClient(message_handler=process_mqtt_message)


# ============================================================
# 3. LIFESPAN: Controla el arranque y apagado limpio
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop_principal
    
    # Guardar el loop principal (el de uvicorn/asyncio)
    _loop_principal = asyncio.get_running_loop()
    print(f"🔄 Loop principal capturado: {_loop_principal}")
    
    # Crear tablas en PostgreSQL si no existen
    # (En producción usa Alembic, esto es solo para desarrollo rápido)
    print("🗄️  Verificando tablas en PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas listas")
    
    # Iniciar conexión a HiveMQ
    print("🚀 Iniciando OVOTECH Backend...")
    mqtt_client.start()
    
    yield  # La aplicación corre aquí
    
    # Apagado
    print("🛑 Apagando OVOTECH Backend...")
    mqtt_client.stop()


# ============================================================
# 4. APLICACIÓN FASTAPI
# ============================================================
app = FastAPI(
    title="OVOTECH API",
    description="Backend para incubadora automatizada con PostgreSQL",
    version="2.0.0",
    lifespan=lifespan
)

# CORS: Permite que el navegador hable con el backend
# desde cualquier origen (útil si usas Live Server en desarrollo)
origins = [
    "http://localhost:8000",
    "http://localhost:5500",
    "https://ovo-tech.netlify.app/",  # ← TU URL DE NETLIFY
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Cambia ["*"] por esto
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Servir archivos estáticos (HTML, CSS, JS del frontend)
# Tu index.html debe estar en la carpeta "static/"
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================
# 5. ENDPOINTS REST (HTTP)
# ============================================================

@app.get("/")
async def root():
    """Página de bienvenida con info de la API"""
    return {
        "message": "OVOTECH API v2.0",
        "base_de_datos": "PostgreSQL",
        "endpoints": {
            "lecturas": "/api/lecturas?limit=50",
            "ultima_lectura": "/api/lecturas/ultima",
            "websocket": "/ws"
        }
    }


@app.get("/api/lecturas", response_model=LecturaList)
async def get_lecturas(limit: int = 50, db: Session = Depends(get_db)):
    """
    Devuelve las últimas N lecturas guardadas en PostgreSQL.
    El frontend usa esto para dibujar el gráfico histórico al cargar.
    """
    lecturas = db.query(Lectura).order_by(Lectura.timestamp.desc()).limit(limit).all()
    # Las devolvemos en orden cronológico (más antigua primero)
    return {"data": list(reversed(lecturas)), "count": len(lecturas)}


@app.get("/api/lecturas/ultima", response_model=LecturaResponse)
async def get_ultima_lectura(db: Session = Depends(get_db)):
    """
    Devuelve la lectura más reciente de la base de datos.
    """
    lectura = db.query(Lectura).order_by(Lectura.timestamp.desc()).first()
    if not lectura:
        raise HTTPException(status_code=404, detail="No hay lecturas registradas en PostgreSQL")
    return lectura


# ============================================================
# 6. WEBSOCKET (Tiempo real)
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Cada navegador que abre tu página se conecta aquí.
    FastAPI mantiene el canal abierto y envía datos nuevos
    automáticamente cuando llegan del MQTT.
    """
    await manager.connect(websocket)
    print(f"🌐 WebSocket: Cliente conectado. Total activos: {len(manager.active_connections)}")
    
    # Opcional: Enviar histórico reciente al conectar
    # (para que el gráfico no esté vacío si acaba de abrir la página)
    try:
        db = SessionLocal()
        recientes = db.query(Lectura).order_by(Lectura.timestamp.desc()).limit(30).all()
        if recientes:
            await websocket.send_json({
                "type": "historico",
                "data": [
                    {
                        "id": l.id,
                        "temperatura": l.temperatura,
                        "humedad": l.humedad,
                        "device_id": l.device_id,
                        "timestamp": l.timestamp.isoformat() if l.timestamp else None
                    }
                    for l in reversed(recientes)
                ]
            })
    except Exception as e:
        print(f"⚠️ No se pudo enviar histórico al WS: {e}")
    finally:
        db.close()
    
    # Mantener conexión viva
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"🌐 WebSocket: Cliente desconectado. Total activos: {len(manager.active_connections)}")
    except Exception as e:
        print(f"⚠️ WebSocket Error: {e}")
        manager.disconnect(websocket)


# ============================================================
# 7. PUNTO DE ENTRADA
# ============================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)