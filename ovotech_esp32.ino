/*
  OVOTECH - Firmware ESP32
  Compatible con: FastAPI + PostgreSQL (Neon) + HiveMQ + WebSocket
  Sensores: DS18B20 (sonda temperatura) + BME280 (humedad por I2C)
  Autor: OVOTECH
  Versión: 2.1
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ============================================
// CONFIGURACIÓN DE PINES Y SENSORES
// ============================================
// Sonda DS18B20 (1-Wire) — cable DATA al pin indicado + resistencia 4.7k a 3.3V
#define DS18B20_PIN 4

// BME280 (I2C) — en ESP32 suele ser SDA=21, SCL=22
#define I2C_SDA 21
#define I2C_SCL 22
// Dirección I2C: 0x76 o 0x77 según el módulo (probar la otra si falla begin)
#define BME280_ADDRESS 0x76

OneWire oneWire(DS18B20_PIN);
DallasTemperature ds18b20(&oneWire);
Adafruit_BME280 bme;

// ============================================
// CONFIGURACIÓN MQTT (HiveMQ - Público)
// ============================================
const char* MQTT_BROKER = "broker.hivemq.com";
const int MQTT_PORT = 1883;
const char* MQTT_TOPIC = "ovotech/sensor";

// ============================================
// VARIABLES GLOBALES
// ============================================
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

String DEVICE_ID;
String wifiSSID = "";
String wifiPassword = "";

unsigned long lastReconnectAttempt = 0;
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 3000;

bool sensorDs18Ok = false;
bool sensorBmeOk = false;

// ============================================
// INICIALIZAR SENSORES
// ============================================
bool initSensores() {
  sensorDs18Ok = false;
  sensorBmeOk = false;

  ds18b20.begin();
  int count = ds18b20.getDeviceCount();
  if (count > 0) {
    sensorDs18Ok = true;
    Serial.print("✅ DS18B20 detectado (");
    Serial.print(count);
    Serial.println(" dispositivo(s))");
  } else {
    Serial.println("❌ No se detectó la sonda DS18B20 en el pin " + String(DS18B20_PIN));
  }

  Wire.begin(I2C_SDA, I2C_SCL);
  if (bme.begin(BME280_ADDRESS, &Wire)) {
    sensorBmeOk = true;
    // Configuración recomendada para incubadora (lecturas estables)
    bme.setSampling(Adafruit_BME280::MODE_NORMAL,
                    Adafruit_BME280::SAMPLING_X2,
                    Adafruit_BME280::SAMPLING_X16,
                    Adafruit_BME280::SAMPLING_X1,
                    Adafruit_BME280::FILTER_X16,
                    Adafruit_BME280::STANDBY_MS_500);
    Serial.println("✅ BME280 inicializado (humedad)");
  } else if (bme.begin(0x77, &Wire)) {
    sensorBmeOk = true;
    Serial.println("✅ BME280 en dirección 0x77 (cambiá BME280_ADDRESS a 0x77 en el código)");
  } else {
    Serial.println("❌ BME280 no responde (revisá SDA/SCL y dirección 0x76/0x77)");
  }

  return sensorDs18Ok && sensorBmeOk;
}

float leerTemperaturaSonda() {
  if (!sensorDs18Ok) return NAN;

  ds18b20.requestTemperatures();
  float temp = ds18b20.getTempCByIndex(0);

  if (temp == DEVICE_DISCONNECTED_C || temp == -127.0) {
    return NAN;
  }
  return temp;
}

float leerHumedadBme() {
  if (!sensorBmeOk) return NAN;

  float hum = bme.readHumidity();
  if (isnan(hum) || hum < 0.0 || hum > 100.0) {
    return NAN;
  }
  return hum;
}

// ============================================
// 1. OBTENER ID PERMANENTE DESDE MAC ADDRESS
// ============================================
String getDeviceId() {
  uint8_t mac[6];
  WiFi.macAddress(mac);

  char deviceId[20];
  sprintf(deviceId, "ovotech-%02X%02X%02X", mac[3], mac[4], mac[5]);

  return String(deviceId);
}

// ============================================
// 2. GUARDAR/CARGAR CREDENCIALES WIFI (FLASH)
// ============================================
void saveCredentials(const char* ssid, const char* pass) {
  Preferences prefs;
  prefs.begin("ovotech", false);
  prefs.putString("ssid", ssid);
  prefs.putString("pass", pass);
  prefs.end();
  Serial.println("💾 Credenciales guardadas en flash");
}

bool loadCredentials() {
  Preferences prefs;
  prefs.begin("ovotech", true);
  wifiSSID = prefs.getString("ssid", "");
  wifiPassword = prefs.getString("pass", "");
  prefs.end();

  if (wifiSSID.length() > 0) {
    Serial.println("📂 Credenciales cargadas desde flash");
    return true;
  }
  return false;
}

// ============================================
// 3. MODO AP - CONFIGURACIÓN INICIAL
// ============================================
void setupAccessPoint() {
  String apName = "OVOTECH-" + DEVICE_ID.substring(8);

  WiFi.softAP(apName.c_str(), "12345678");

  IPAddress IP = WiFi.softAPIP();
  Serial.println("\n📡 Modo Configuración activado");
  Serial.print("🔗 Conectate a la red: ");
  Serial.println(apName);
  Serial.print("🌐 Abrí en tu celular: http://");
  Serial.println(IP);

  WiFiServer server(80);
  server.begin();

  while (true) {
    WiFiClient client = server.available();
    if (client) {
      String request = client.readStringUntil('\r');
      Serial.println("📥 " + request);

      if (request.indexOf("/config?") >= 0) {
        int ssidStart = request.indexOf("ssid=") + 5;
        int ssidEnd = request.indexOf("&", ssidStart);
        int passStart = request.indexOf("pass=") + 5;
        int passEnd = request.indexOf(" ", passStart);

        String newSSID = request.substring(ssidStart, ssidEnd);
        String newPASS = request.substring(passStart, passEnd);

        newSSID.replace("+", " ");
        newPASS.replace("+", " ");

        saveCredentials(newSSID.c_str(), newPASS.c_str());

        client.println("HTTP/1.1 200 OK");
        client.println("Content-Type: text/html");
        client.println();
        client.println("<h1>✅ Configurado! Reiniciando...</h1>");
        client.stop();

        delay(1000);
        ESP.restart();
      }

      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: text/html");
      client.println();
      client.println("<!DOCTYPE html><html><head>");
      client.println("<meta charset='UTF-8'><meta name='viewport' content='width=device-width'>");
      client.println("<title>OVOTECH Config</title>");
      client.println("<style>");
      client.println("body{font-family:Arial;background:#1a1a2e;color:#fff;text-align:center;padding:20px}");
      client.println("input{padding:12px;margin:8px;width:80%;border-radius:8px;border:none;font-size:16px}");
      client.println("button{padding:12px 24px;background:#4e54c8;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer}");
      client.println("</style></head><body>");
      client.println("<h1>🐣 OVOTECH</h1>");
      client.println("<p>Configurá tu WiFi</p>");
      client.println("<form action='/config' method='GET'>");
      client.println("<input type='text' name='ssid' placeholder='Nombre de tu WiFi' required><br>");
      client.println("<input type='password' name='pass' placeholder='Contraseña' required><br>");
      client.println("<button type='submit'>Guardar y Conectar</button>");
      client.println("</form>");
      client.println("<p><small>ID de tu incubadora: <b>" + DEVICE_ID + "</b></small></p>");
      client.println("<p><small>Sensores: DS18B20 (temp) + BME280 (humedad)</small></p>");
      client.println("</body></html>");
      client.stop();
    }
    delay(10);
  }
}

// ============================================
// 4. CONEXIÓN WIFI NORMAL
// ============================================
bool connectToWiFi() {
  if (!loadCredentials()) {
    Serial.println("⚠️ No hay WiFi guardado. Entrando en modo configuración...");
    setupAccessPoint();
    return false;
  }

  WiFi.begin(wifiSSID.c_str(), wifiPassword.c_str());
  Serial.print("🔌 Conectando a WiFi: " + wifiSSID);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi conectado");
    Serial.print("📡 IP local: ");
    Serial.println(WiFi.localIP());
    return true;
  } else {
    Serial.println("\n❌ Falló la conexión WiFi. Modo configuración...");
    setupAccessPoint();
    return false;
  }
}

// ============================================
// 5. MQTT - CALLBACKS Y RECONEXIÓN
// ============================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Reservado para comandos futuros
}

bool connectMQTT() {
  String clientId = "esp32-" + DEVICE_ID + "-" + String(random(0xffff), HEX);

  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("✅ Conectado a HiveMQ");
    mqttClient.subscribe("ovotech/comandos");
    return true;
  }
  return false;
}

// ============================================
// 6. LECTURA DE SENSORES Y ENVÍO MQTT
// ============================================
void readAndSend() {
  float temperatura = leerTemperaturaSonda();
  float humedad = leerHumedadBme();

  if (isnan(temperatura)) {
    Serial.println("⚠️ Error leyendo sonda DS18B20");
    return;
  }
  if (isnan(humedad)) {
    Serial.println("⚠️ Error leyendo BME280 (humedad)");
    return;
  }

  StaticJsonDocument<256> doc;
  doc["temperatura"] = round(temperatura * 10) / 10.0;
  doc["humedad"] = round(humedad * 10) / 10.0;
  doc["device_id"] = DEVICE_ID;

  char buffer[256];
  serializeJson(doc, buffer);

  bool enviado = mqttClient.publish(MQTT_TOPIC, buffer);

  if (enviado) {
    Serial.print("📤 Enviado: ");
    Serial.println(buffer);
  } else {
    Serial.println("❌ Falló el envío MQTT");
  }
}

// ============================================
// 7. SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n╔════════════════════════════╗");
  Serial.println("║     🐣 OVOTECH v2.1      ║");
  Serial.println("║   DS18B20 + BME280         ║");
  Serial.println("╚════════════════════════════╝");

  DEVICE_ID = getDeviceId();
  Serial.print("📛 Device ID: ");
  Serial.println(DEVICE_ID);
  Serial.println("   (Este ID nunca cambia. Escribilo en la web para vincular)");

  if (!initSensores()) {
    Serial.println("⚠️ Revisá cableado antes de continuar:");
    Serial.println("   DS18B20 DATA → GPIO " + String(DS18B20_PIN) + " (+ pull-up 4.7k)");
    Serial.println("   BME280 SDA → GPIO " + String(I2C_SDA) + ", SCL → GPIO " + String(I2C_SCL));
  }

  if (!connectToWiFi()) return;

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
}

// ============================================
// 8. LOOP PRINCIPAL
// ============================================
void loop() {
  if (!mqttClient.connected()) {
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      Serial.println("🔌 Reconectando MQTT...");
      if (connectMQTT()) {
        lastReconnectAttempt = 0;
      }
    }
  } else {
    mqttClient.loop();
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("🔌 WiFi desconectado. Reconectando...");
    WiFi.reconnect();
    delay(5000);
    return;
  }

  unsigned long now = millis();
  if (now - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = now;
    readAndSend();
  }
}
