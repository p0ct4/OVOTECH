import paho.mqtt.client as mqtt
import json
import time
import random

BROKER = "broker.hivemq.com"
TOPIC = "ovotech/sensor"

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

print("🔌 Conectando al broker...")
client.connect(BROKER, 1883, 60)
print("✅ Conectado. Enviando datos cada 3 segundos...")
print("Presiona CTRL+C para detener.\n")

try:
    while True:
        # Simulación realista de incubadora
        temp = round(random.uniform(36.0, 39.0), 1)
        hum = round(random.uniform(50.0, 65.0), 1)
        
        payload = {
            "temperatura": temp,
            "humedad": hum,
            "device_id": "esp32_01"
        }
        
        client.publish(TOPIC, json.dumps(payload))
        print(f"📤 Enviado -> Temp: {temp}°C | Hum: {hum}%")
        time.sleep(3)

except KeyboardInterrupt:
    print("\n🛑 Simulador detenido.")
    client.disconnect()