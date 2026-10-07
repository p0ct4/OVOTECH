# OVOTECH — Incubadora inteligente (IoT)

Sistema de **control y monitoreo** de temperatura y humedad para incubadoras de huevos.

El **ESP32** lee sensores, enciende o apaga calefacción y ventilación, y envía los datos por **MQTT**. El backend los guarda en **PostgreSQL** y el **dashboard web** los muestra en tiempo real.

- **Web:** [ovo-tech.netlify.app](https://ovo-tech.netlify.app)
- **API:** [ovotech.onrender.com](https://ovotech.onrender.com)

---

## Cómo funciona

```
ESP32 (sensores + relés)
        │  JSON cada ~2 s
        ▼
   HiveMQ (MQTT)  ←  también puede publicar el simulador
        │
        ▼
   FastAPI + PostgreSQL
        │
        ├── REST  →  dashboard
        └── WebSocket /ws  →  lecturas en vivo
```

Cada incubadora tiene un **ID único** (`ovotech-XXXXXX`). Se genera una sola vez, se guarda en flash y no cambia al reiniciar. Ese ID es el que se usa para vincular el equipo en la web.

---

## Hardware

| Pieza | Función | Pin ESP32 |
|--------|---------|-----------|
| **DS18B20** | Temperatura | GPIO **5** (1-Wire, pull-up 4.7 kΩ a 3.3 V) |
| **DHT22** | Humedad | GPIO **4** |
| **Relé lámpara** | Calefacción | GPIO **12** |
| **Relé cooler** | Ventilación | GPIO **13** |

Alimentar sensores y módulos a **3.3 V**. El WiFi del portal y de casa debe ser **2.4 GHz** (el ESP32 no usa 5 GHz).

### Control de temperatura

Cada 2 segundos se lee el DS18B20 y se aplica histéresis:

| Temperatura | Lámpara | Cooler |
|-------------|---------|--------|
| ≤ 37.5 °C | Encendida | Apagado |
| ≥ 39.0 °C | Apagada | Encendido |
| Entre 37.5 y 39.0 | Se mantiene el estado anterior | |

Si no hay lecturas válidas durante **5 minutos**, entra **fail-safe**: apaga lámpara y cooler.

---

## Estructura del proyecto

```
.
├── ovotech_esp32.ino       # Firmware ESP32
├── main.py                 # API FastAPI + MQTT + WebSocket
├── mqtt_client.py
├── websocket_manager.py
├── database.py
├── models.py
├── schemas.py
├── simulador_ovotech.py    # Simula una incubadora sin hardware
├── test_bdd.py
├── requirements.txt
├── .env.example
└── static/
    ├── index.html          # Landing
    ├── presentacion.html   # Dashboard
    ├── script.js
    ├── style.css
    └── presentacion.css
```

---

## Firmware ESP32

### Librerías (Arduino IDE)

- DHT sensor library (Adafruit)
- OneWire
- DallasTemperature
- PubSubClient
- ArduinoJson

`WebServer.h` y `Preferences.h` vienen con el core ESP32.

### Primer uso

1. Abrí `ovotech_esp32.ino` y flasheá el ESP32.
2. Monitor serie a **115200** baud: ahí aparece el ID (`ovotech-XXXXXX`).
3. Cada vez que prende, el ESP32 abre un punto de acceso (el WiFi de casa **no se guarda**):
   - Red: `OVOTECH-XXXXXX`
   - Clave: `12345678`
   - En el celular: [http://192.168.4.1](http://192.168.4.1)
4. Ingresá SSID y contraseña de tu WiFi 2.4 GHz.
5. Copiá el ID y vinculalo en el dashboard.

### Payload MQTT

Topic: `ovotech/sensor`

```json
{
  "temperatura": 37.5,
  "humedad": 62.3,
  "device_id": "ovotech-a4cf12",
  "lampara": 1,
  "cooler": 0,
  "failsafe": 0
}
```

La API usa `temperatura`, `humedad` y `device_id`. El resto sirve para diagnóstico.

---

## Backend (local)

Requisitos: **Python 3.10+** y **PostgreSQL** (por ejemplo [Neon](https://neon.tech)).

```bash
git clone https://github.com/p0ct4/OVOTECH.git
cd OVOTECH

python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env    # o: cp .env.example .env
```

Completá `DATABASE_URL` en `.env`.

```bash
python test_bdd.py
python main.py
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Landing: http://localhost:8000/static/index.html
- Dashboard: http://localhost:8000/static/presentacion.html

---

## Simulador (sin ESP32)

Con la API corriendo:

```bash
python simulador_ovotech.py
python simulador_ovotech.py --device-id ovotech-DEMO01 --interval 2
```

Publica al mismo broker y topic que el firmware, con la misma histéresis. Vinculá en la web el `device_id` que imprima.

La incubadora (real o simulada) tiene que haber enviado **al menos una lectura** antes de vincular; si no, la API responde 404.

---

## API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Estado de la API |
| `POST` | `/api/vincular` | Vincula un `device_id` (hace falta una lectura previa) |
| `GET` | `/api/mis-dispositivos` | Vinculaciones |
| `GET` | `/api/lecturas?limit=50` | Últimas lecturas |
| `GET` | `/api/lecturas/{device_id}` | Histórico de una incubadora |
| `GET` | `/api/lecturas/ultima/{device_id}` | Última lectura |
| `WS` | `/ws` | Tiempo real (`type: "lectura"`) |

```bash
curl -X POST http://localhost:8000/api/vincular \
  -H "Content-Type: application/json" \
  -d "{\"device_id\": \"ovotech-DEMO01\"}"
```

Se guardan temperatura, humedad, `device_id` y timestamp. Quedan **50 lecturas por dispositivo**; las más viejas se borran.

---

## Dashboard

1. Ingresás el ID de la incubadora (queda en `localStorage`).
2. Carga el histórico con `GET /api/lecturas/{device_id}`.
3. Recibe lecturas nuevas por WebSocket y filtra por ese ID.
4. Muestra rangos de temperatura y humedad (óptimo / advertencia / peligro).

En producción el frontend usa:

- API: `https://ovotech.onrender.com`
- WebSocket: `wss://ovotech.onrender.com/ws`

---

## Variables de entorno

| Variable | Obligatoria | Por defecto | Uso |
|----------|-------------|-------------|-----|
| `DATABASE_URL` | Sí | — | PostgreSQL (Neon u otro) |
| `PORT` | No | `8000` | Puerto de Uvicorn |
| `MQTT_BROKER` | No | `broker.hivemq.com` | Broker MQTT |
| `MQTT_PORT` | No | `1883` | Puerto MQTT |
| `MQTT_TOPIC` | No | `ovotech/sensor` | Topic de sensores |

Plantilla: [`.env.example`](.env.example).

---

## Producción

**Neon:** creá el proyecto y copiá `DATABASE_URL`.

**Render (API):**

- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Variable: `DATABASE_URL` (obligatoria)

Las tablas se crean al arrancar.

**Netlify (web):** publicá la carpeta `static/`. Si cambia la URL de Render, actualizá `static/script.js` y el CORS en `main.py`.

---

## Problemas frecuentes

| Problema | Qué revisar |
|----------|-------------|
| No conecta al WiFi | Red 2.4 GHz, SSID/clave, portal en `192.168.4.1` |
| Error DHT22 | Cableado GPIO 4, alimentación 3.3 V |
| Error DS18B20 | GPIO 5, pull-up 4.7 kΩ, alimentación 3.3 V |
| Relés no cambian | GPIO 12 (lámpara) y 13 (cooler); polaridad del módulo |
| Vincular da 404 | El dispositivo ya tiene que haber enviado una lectura |
| Dashboard sin datos | Mismo `device_id`, API arriba, logs MQTT en el servidor |
| Render “duerme” | En plan free puede tardar ~30 s en despertar |
| CORS | El origen del frontend tiene que estar en `origins` de `main.py` |

---

Proyecto **OVOTECH**.
