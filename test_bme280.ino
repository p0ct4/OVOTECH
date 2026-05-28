/*
  TEST BME280 - OVOTECH
  Lee temperatura, humedad y presión del BME280 por I2C
  y los imprime por Serial cada 2 segundos.

  Conexión ESP32:
    BME280 VCC  → 3.3V
    BME280 GND  → GND
    BME280 SDA  → GPIO 21
    BME280 SCL  → GPIO 22
*/

#include <Wire.h>
#include <Adafruit_BME280.h>

#define I2C_SDA 21
#define I2C_SCL 22
#define BME280_ADDRESS 0x76  // Cambiá a 0x77 si no detecta

Adafruit_BME280 bme;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n╔══════════════════════════╗");
  Serial.println("║   TEST BME280 - OVOTECH  ║");
  Serial.println("╚══════════════════════════╝");

  Wire.begin(I2C_SDA, I2C_SCL);

  if (bme.begin(BME280_ADDRESS, &Wire)) {
    Serial.println("✅ BME280 detectado en 0x76");
  } else if (bme.begin(0x77, &Wire)) {
    Serial.println("✅ BME280 detectado en 0x77 (cambiá BME280_ADDRESS a 0x77)");
  } else {
    Serial.println("❌ BME280 no encontrado.");
    Serial.println("   Verificá:");
    Serial.println("   - SDA → GPIO 21");
    Serial.println("   - SCL → GPIO 22");
    Serial.println("   - Dirección: 0x76 o 0x77");
    Serial.println("   - Alimentación: 3.3V");
    while (true) delay(1000);  // Se queda acá hasta que se corrija el problema
  }

  Serial.println("\n--- Lecturas cada 2 segundos ---\n");
}

void loop() {
  float temperatura = bme.readTemperature();
  float humedad     = bme.readHumidity();
  float presion     = bme.readPressure() / 100.0F;  // hPa

  Serial.println("-----------------------------");

  if (!isnan(temperatura)) {
    Serial.print("🌡️  Temperatura : ");
    Serial.print(temperatura, 1);
    Serial.println(" °C");
  } else {
    Serial.println("⚠️  Temperatura : error de lectura");
  }

  if (!isnan(humedad)) {
    Serial.print("💧 Humedad     : ");
    Serial.print(humedad, 1);
    Serial.println(" %");
  } else {
    Serial.println("⚠️  Humedad     : error de lectura");
  }

  if (!isnan(presion)) {
    Serial.print("🔵 Presión     : ");
    Serial.print(presion, 1);
    Serial.println(" hPa");
  } else {
    Serial.println("⚠️  Presión     : error de lectura");
  }

  delay(2000);
}
