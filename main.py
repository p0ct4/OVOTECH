import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import engine, Base, SessionLocal, get_db
from models import Lectura, Vinculacion
from schemas import LecturaResponse, LecturaList
from websocket_manager import manager
from mqtt_client import MQTTClient

_loop_principal = None


# ============================================================
# PROCESADOR MQTT
# ============================================================
def process_mqtt_message(payload: dict):
    db = SessionLocal()
    try:
        lectura = Lectura(
            temperatura=float(payload.get("temperatura", 0)),
            humedad=float(payload.get("humedad", 0)),
            device_id=str(payload.get("device_id", "desconocido"))
        )
        db.add(lectura)
        db.commit()
        db.refresh(lectura)
        
        print(f"💾 [{lectura.device_id}] ID={lectura.id}, Temp={lectura.temperatura}°C")

        # ROTACIÓN: 50 lecturas POR dispositivo (no global)
        total = db.query(Lectura).filter(Lectura.device_id == lectura.device_id).count()
        if total > 50:
            limite = db.query(Lectura.timestamp)\
                .filter(Lectura.device_id == lectura.device_id)\
                .order_by(Lectura.timestamp.desc())\
                .offset(50)\
                .limit(1)\
                .scalar()
            if limite:
                db.query(Lectura)\
                    .filter(Lectura.device_id == lectura.device_id, Lectura.timestamp <= limite)\
                    .delete(synchronize_session=False)
                db.commit()
                print(f"🗑️  Rotación: {lectura.device_id} limpiado")

        # Broadcast
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
        if _loop_principal is not None:
            asyncio.run_coroutine_threadsafe(manager.broadcast(msg), _loop_principal)

    except Exception as e:
        print(f"❌ Error MQTT: {e}")
        db.rollback()
    finally:
        db.close()


mqtt_client = MQTTClient(message_handler=process_mqtt_message)


# ============================================================
# LIFESPAN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop_principal
    _loop_principal = asyncio.get_running_loop()
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas listas")
    mqtt_client.start()
    print("🚀 OVOTECH en línea")
    yield
    mqtt_client.stop()


# ============================================================
# APP FASTAPI (CREAR PRIMERO)
# ============================================================
app = FastAPI(title="OVOTECH API", lifespan=lifespan)

origins = [
    "http://localhost:8000",
    "http://localhost:5500",
    "https://ovo-tech.netlify.app",  # ← SIN barra al final
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================
# SCHEMAS
# ============================================================
class VinculacionCreate(BaseModel):
    device_id: str
    nombre_usuario: str = None


# ============================================================
# ENDPOINTS (DESPUÉS de crear app)
# ============================================================

@app.get("/")
async def root():
    return {"message": "OVOTECH API", "docs": "/static/index.html"}


# --- Vinculación ---
@app.post("/api/vincular")
async def vincular_dispositivo(data: VinculacionCreate, db: Session = Depends(get_db)):
    existente = db.query(Vinculacion).filter(Vinculacion.device_id == data.device_id).first()
    if existente:
        return {"message": "Ya vinculado", "device_id": data.device_id}
    
    vinculo = Vinculacion(device_id=data.device_id, nombre_usuario=data.nombre_usuario)
    db.add(vinculo)
    db.commit()
    return {"message": "Vinculado correctamente", "device_id": data.device_id}


@app.get("/api/mis-dispositivos")
async def mis_dispositivos(db: Session = Depends(get_db)):
    dispositivos = db.query(Vinculacion).all()
    return {"dispositivos": [{"id": d.device_id, "nombre": d.nombre_usuario} for d in dispositivos]}


# --- Lecturas generales ---
@app.get("/api/lecturas", response_model=LecturaList)
async def get_lecturas(limit: int = 50, db: Session = Depends(get_db)):
    lecturas = db.query(Lectura).order_by(Lectura.timestamp.desc()).limit(limit).all()
    return {"data": list(reversed(lecturas)), "count": len(lecturas)}


# --- Lecturas FILTRADAS por incubadora ---
@app.get("/api/lecturas/{device_id}", response_model=LecturaList)
async def get_lecturas_device(device_id: str, limit: int = 50, db: Session = Depends(get_db)):
    lecturas = db.query(Lectura)\
        .filter(Lectura.device_id == device_id)\
        .order_by(Lectura.timestamp.desc())\
        .limit(limit).all()
    return {"data": list(reversed(lecturas)), "count": len(lecturas)}


@app.get("/api/lecturas/ultima/{device_id}", response_model=LecturaResponse)
async def get_ultima_lectura(device_id: str, db: Session = Depends(get_db)):
    lectura = db.query(Lectura)\
        .filter(Lectura.device_id == device_id)\
        .order_by(Lectura.timestamp.desc())\
        .first()
    if not lectura:
        raise HTTPException(status_code=404, detail="Sin lecturas para este dispositivo")
    return lectura


# --- WebSocket ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))