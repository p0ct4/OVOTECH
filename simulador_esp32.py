import paho.mqtt.client as mqtt
import json
import time
import random
import sys

# El device_id se pasa por argumento o usa uno por defecto
DEVICE_ID = sys.argv[1] if len(sys.argv) > 1 else "incubadora_demo"

print(f"🐣 Simulador ESP32 iniciado")
print(f"📛 Device ID: {DEVICE_ID}")
print(f"📡 Publicando a: ovotech/sensor")

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.connect("broker.hivemq.com", 1883, 60)

try:
    while True:
        payload = {
            "temperatura": round(random.uniform(36.5, 38.5), 1),
            "humedad": round(random.uniform(50, 70), 1),
            "device_id": DEVICE_ID
        }
        client.publish("ovotech/sensor", json.dumps(payload))
        print(f"📤 Enviado: {payload}")
        time.sleep(3)
except KeyboardInterrupt:
    print("\n🛑 Simulador detenido")