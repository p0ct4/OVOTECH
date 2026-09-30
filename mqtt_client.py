import paho.mqtt.client as mqtt
import json
import os
import time
import random
from typing import Callable, Any

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "ovotech/sensor")


class MQTTClient:
    def __init__(self, message_handler: Callable[[dict], Any]):
        self.message_handler = message_handler
        self.connected = False

        # Client ID único cada vez que Render reinicia (evita conflictos)
        client_id = f"ovotech_{random.randint(1000,9999)}_{int(time.time())}"

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id
        )

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        # Reconexión automática con espera progresiva
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.connected = True
            print(f"✅ Conectado a HiveMQ - ClientID: {client._client_id.decode()}")
            # Se resuscribe en CADA (re)conexión
            client.subscribe(MQTT_TOPIC)
            print(f"📡 Suscrito a: {MQTT_TOPIC}")
        else:
            self.connected = False
            print(f"❌ Error conexión MQTT, código: {reason_code}")

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self.connected = False
        print(f"🔌 Desconectado (código: {reason_code}). Reconectando...")
        # loop_start reconecta solo con reconnect_delay_set

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"📥 MQTT: {payload}")
            if self.message_handler:
                self.message_handler(payload)
        except json.JSONDecodeError:
            print("⚠️ Payload no es JSON válido")
        except Exception as e:
            print(f"⚠️ Error MQTT: {e}")

    def start(self):
        # connect_async + loop_start: si el primer intento falla (DNS, broker
        # caído, red de Render recién levantada), el loop sigue reintentando
        # solo. Con connect() bloqueante, un fallo inicial dejaba el MQTT muerto.
        self.client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        print("🚀 MQTT iniciado (conectando en segundo plano...)")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
        print("🛑 MQTT detenido")
