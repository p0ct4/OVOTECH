import paho.mqtt.client as mqtt
import json
import os
from typing import Callable, Any

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "ovotech/sensor")

class MQTTClient:
    def __init__(self, message_handler: Callable[[dict], Any]):
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="ovotech_fastapi_backend"
        )
        self.message_handler = message_handler
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"✅ Conectado a HiveMQ ({MQTT_BROKER})")
            client.subscribe(MQTT_TOPIC)
            print(f"📡 Suscrito al tópico: {MQTT_TOPIC}")
        else:
            print(f"❌ Error de conexión MQTT, código: {reason_code}")
    
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"📥 MQTT Recibido: {payload}")
            if self.message_handler:
                self.message_handler(payload)
        except json.JSONDecodeError:
            print("⚠️ Error: El payload no es un JSON válido")
        except Exception as e:
            print(f"⚠️ Error procesando mensaje MQTT: {e}")
    
    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"🔌 Desconectado de MQTT (código: {reason_code})")
    
    def start(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"❌ No se pudo conectar al broker MQTT: {e}")
    
    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()