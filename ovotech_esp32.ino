/*
  OVOTECH - Firmware ESP32
  Compatible con: FastAPI + PostgreSQL (Neon) + HiveMQ + WebSocket
  Autor: OVOTECH
  Versión: 2.0
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Preferences.h>

// ============================================
// CONFIGURACIÓN DE PINES Y SENSORES
// ============================================
#define DHT_PIN 4
#define DHT_TYPE DHT22  // Cambiar a DHT11 si usás ese

DHT dht(DHT_PIN, DHT_TYPE);

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

String DEVICE_ID;           // ID único permanente (MAC address)
String wifiSSID = "";       // Guardado en flash
String wifiPassword = "";   // Guardado en flash

unsigned long lastReconnectAttempt = 0;
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 3000;  // 3 segundos entre lecturas

// ============================================
// 1. OBTENER ID PERMANENTE DESDE MAC ADDRESS
// ============================================
String getDeviceId() {
  uint8_t mac[6];
  WiFi.macAddress(mac);
  
  // Formato: ovotech-A4CF12 (últimos 3 bytes de la MAC)
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
  String apName = "OVOTECH-" + DEVICE_ID.substring(8);  // ovotech-A4CF12 → A4CF12
  
  WiFi.softAP(apName.c_str(), "12345678");  // AP sin contraseña o con pass simple
  
  IPAddress IP = WiFi.softAPIP();
  Serial.println("\n📡 Modo Configuración activado");
  Serial.print("🔗 Conectate a la red: ");
  Serial.println(apName);
  Serial.print("🌐 Abrí en tu celular: http://");
  Serial.println(IP);

  // Servidor web simple para recibir credenciales
  WiFiServer server(80);
  server.begin();

  while (true) {
    WiFiClient client = server.available();
    if (client) {
      String request = client.readStringUntil('\r');
      Serial.println("📥 " + request);

      // Parsear /config?ssid=MI_WIFI&pass=MI_PASS
      if (request.indexOf("/config?") >= 0) {
        int ssidStart = request.indexOf("ssid=") + 5;
        int ssidEnd = request.indexOf("&", ssidStart);
        int passStart = request.indexOf("pass=") + 5;
        int passEnd = request.indexOf(" ", passStart);

        String newSSID = request.substring(ssidStart, ssidEnd);
        String newPASS = request.substring(passStart, passEnd);

        // Decodificar URL básico (reemplazar + por espacio)
        newSSID.replace("+", " ");
        newPASS.replace("+", " ");

        saveCredentials(newSSID.c_str(), newPASS.c_str());

        client.println("HTTP/1.1 200 OK");
        client.println("Content-Type: text/html");
        client.println();
        client.println("<h1>✅ Configurado! Reiniciando...</h1>");
        client.stop();

        delay(1000);
        ESP.restart();  // Reiniciar y conectar al WiFi normal
      }

      // Página de configuración
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
  // Por ahora no recibimos comandos del backend
}

bool connectMQTT() {
  String clientId = "esp32-" + DEVICE_ID + "-" + String(random(0xffff), HEX);
  
  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("✅ Conectado a HiveMQ");
    mqttClient.subscribe("ovotech/comandos");  // Para futuro: recibir comandos
    return true;
  }
  return false;
}

// ============================================
// 6. LECTURA DE SENSOR Y ENVÍO
// ============================================
void readAndSend() {
  // Leer DHT
  float temperatura = dht.readTemperature();
  float humedad = dht.readHumidity();

  // Validar lectura
  if (isnan(temperatura) || isnan(humedad)) {
    Serial.println("⚠️ Error leyendo DHT");
    return;
  }

  // Crear JSON exactamente como espera el backend
  StaticJsonDocument<256> doc;
  doc["temperatura"] = round(temperatura * 10) / 10.0;  // 1 decimal
  doc["humedad"] = round(humedad * 10) / 10.0;
  doc["device_id"] = DEVICE_ID;

  char buffer[256];
  size_t n = serializeJson(doc, buffer);

  // Publicar
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
  Serial.println("║     🐣 OVOTECH v2.0      ║");
  Serial.println("║   Incubadora Inteligente   ║");
  Serial.println("╚════════════════════════════╝");

  // Inicializar sensor
  dht.begin();

  // Obtener ID permanente
  DEVICE_ID = getDeviceId();
  Serial.print("📛 Device ID: ");
  Serial.println(DEVICE_ID);
  Serial.println("   (Este ID nunca cambia. Escribilo en la web para vincular)");

  // Conectar WiFi
  if (!connectToWiFi()) return;  // Si no hay WiFi, entra en modo AP

  // Configurar MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
}

// ============================================
// 8. LOOP PRINCIPAL
// ============================================
void loop() {
  // Reconectar MQTT si se cayó
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

  // Reconectar WiFi si se cayó
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("🔌 WiFi desconectado. Reconectando...");
    WiFi.reconnect();
    delay(5000);
    return;
  }

  // Leer y enviar sensor cada 3 segundos
  unsigned long now = millis();
  if (now - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = now;
    readAndSend();
  }
}