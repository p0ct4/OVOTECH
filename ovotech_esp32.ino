/*
  OVOTECH - Firmware ESP32 (Fusión - Mejorado)
  Compatible con: FastAPI + PostgreSQL (Neon) + HiveMQ + WebSocket
  Sensores: DHT22 (humedad) + DS18B20 (temperatura)
  Actuadores: Relé Lámpara (calefacción) + Relé Cooler (ventilación)

  CAMBIOS:
  - Corregido el typo MQTT_sER -> MQTT_BROKER (no compilaba).
  - DEVICE_ID aleatorio pero PERSISTENTE: se genera una sola vez y se guarda
    en flash (Preferences). Así la web sigue recibiendo datos del mismo ID
    aunque el equipo se reinicie.
  - El portal de configuración WiFi se muestra SIEMPRE al prender el equipo
    (las credenciales WiFi NO se guardan).
  - El AP y el ID se re-imprimen cada 5 s mientras se espera la config.
  - Se mantiene el diagnóstico detallado de errores MQTT.
*/

#include <WiFi.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_system.h>   // esp_random()
#include <Preferences.h>  // ID persistente
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ============================================
// SENSORES
// ============================================
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

#define ONE_WIRE_BUS 5
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature ds18b20(&oneWire);

// ============================================
// RELÉS
// ============================================
#define RELE_LAMPARA 12
#define RELE_COOLER   13
bool estadoLampara = false;
bool estadoCooler = false;

unsigned long previoMillisSensores = 0;
const long intervaloSensores = 2000;

// ============================================
// FAIL-SAFE TÉRMICO
// ============================================
unsigned long ultimaLecturaValida = 0;
const unsigned long FAILSAFE_TIMEOUT = 5UL * 60UL * 1000UL; // 5 minutos sin lectura válida
bool failsafeActivo = false;

// ============================================
// CONFIGURACIÓN MQTT
// ============================================
const char* MQTT_BROKER = "broker.hivemq.com";   // <- corregido (antes MQTT_sER)
const int MQTT_PORT = 1883;
const char* MQTT_TOPIC = "ovotech/sensor";
// Dejar vacíos si el broker no requiere autenticación
const char* MQTT_USER = "";
const char* MQTT_PASS = "";

// ============================================
// VARIABLES GLOBALES DE CONECTIVIDAD
// ============================================
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
WebServer configServer(80);

String DEVICE_ID;
bool wifiConfigurado = false; // se pone en true cuando el portal logra conectar

unsigned long lastMqttAttempt = 0;
unsigned long mqttBackoff = 5000;
const unsigned long MQTT_BACKOFF_MAX = 60000;

// ============================================
// ID ALEATORIO, GENERADO UNA SOLA VEZ Y PERSISTIDO
// Llamar DESPUÉS de WiFi.mode(...) para que esp_random() sea aleatorio real.
// Para volver a "ID nuevo en cada arranque": borrá el bloque de Preferences
// y devolvé siempre el ID recién generado.
// ============================================
String getDeviceId() {
  Preferences prefs;
  prefs.begin("ovotech", false);
  String id = prefs.getString("id", "");
  if (id == "") {
    uint32_t r = esp_random() & 0xFFFFFF;
    char buf[20];
    sprintf(buf, "ovotech-%06x", r);
    id = String(buf);
    prefs.putString("id", id);
  }
  prefs.end();
  return id;
}

// ============================================
// PORTAL DE CONFIGURACIÓN (se muestra SIEMPRE al arrancar)
// ============================================
void handleRoot() {
  String html = "<!DOCTYPE html><html><head>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>OVOTECH Config</title><style>";
  html += "body{font-family:Arial,sans-serif;background:#1a1a2e;color:#fff;text-align:center;padding:20px}";
  html += ".box{background:#161625;padding:20px;border-radius:12px;margin:15px auto;max-width:400px;box-shadow:0 4px 10px rgba(0,0,0,0.3)}";
  html += ".id-badge{background:#4e54c8;padding:10px;font-size:22px;font-weight:bold;border-radius:8px;margin:15px 0;letter-spacing:1px;display:inline-block;padding-left:20px;padding-right:20px;}";
  html += "input{padding:12px;margin:10px 0;width:90%;border-radius:8px;border:none;font-size:16px}";
  html += "button{padding:12px 24px;background:#e94560;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer;width:95%;font-weight:bold}";
  html += "</style></head><body><h1>OVOTECH</h1>";
  html += "<div class='box'><p style='margin:0;color:#b2bec3;'>ID DE TU INCUBADORA:</p>";
  html += "<div class='id-badge'>" + DEVICE_ID + "</div>";
  html += "<p style='font-size:12px;color:#a4b0be;margin:0;'>Copia este ID exacto para vincularlo en la pagina web.</p></div>";
  html += "<div class='box'><p><b>Configurar Conexion WiFi</b></p>";
  html += "<form action='/config' method='POST'>";
  html += "<input type='text' name='ssid' placeholder='Nombre de tu WiFi (SSID)' required><br>";
  html += "<input type='password' name='pass' placeholder='Contrasena' required><br><br>";
  html += "<button type='submit'>Guardar y Conectar</button></form></div>";
  html += "<p><small>Sensores: DHT22 (Humedad) + DS18B20 (Temperatura)</small></p>";
  html += "</body></html>";
  configServer.send(200, "text/html; charset=UTF-8", html);
}

void handleConfigSubmit() {
  if (!configServer.hasArg("ssid") || !configServer.hasArg("pass")) {
    configServer.send(400, "text/plain", "Faltan parametros");
    return;
  }

  String newSSID = configServer.arg("ssid");
  String newPASS = configServer.arg("pass");

  configServer.send(200, "text/html", "<h1>Conectando... revisa el Monitor Serie del ESP32.</h1>");

  Serial.println("Intentando conectar con las credenciales ingresadas: " + newSSID);
  WiFi.disconnect();          // limpia un intento previo fallido (sin apagar el STA)
  WiFi.begin(newSSID.c_str(), newPASS.c_str());

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi conectado exitosamente!");
    Serial.print("IP asignada: ");
    Serial.println(WiFi.localIP());
    wifiConfigurado = true; // esto corta el while(!wifiConfigurado) de abajo
  } else {
    Serial.println("\nError: no se pudo conectar (recordá: solo WiFi de 2.4 GHz). Volvé a cargar el SSID/contraseña desde el portal.");
    // se queda en modo AP esperando que reintentes desde el formulario
  }
}

void setupAccessPoint() {
  String apName = "OVOTECH-" + DEVICE_ID.substring(8);
  WiFi.softAP(apName.c_str(), "12345678");

  IPAddress IP = WiFi.softAPIP();
  configServer.on("/", HTTP_GET, handleRoot);
  configServer.on("/config", HTTP_POST, handleConfigSubmit);
  configServer.begin();

  unsigned long ultimoAviso = 0;
  while (!wifiConfigurado) {
    configServer.handleClient();

    // Re-imprime los datos del AP cada 5 s por si abriste el monitor tarde
    if (ultimoAviso == 0 || millis() - ultimoAviso > 5000) {
      ultimoAviso = millis();
      Serial.println("\n--- Ingresá el WiFi para esta sesión ---");
      Serial.print("Red WiFi (AP): ");
      Serial.println(apName);
      Serial.print("ID: ");
      Serial.println(DEVICE_ID);
      Serial.print("Abrí en tu navegador: http://");
      Serial.println(IP);
    }
    delay(10);
  }

  configServer.stop();
  WiFi.softAPdisconnect(true); // apaga el punto de acceso, ya no hace falta
  WiFi.mode(WIFI_STA);
}

// ============================================
// MQTT - CALLBACKS Y RECONEXIÓN
// ============================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Reservado para comandos futuros
}

bool connectMQTT() {
  String clientId = "esp32-" + DEVICE_ID + "-" + String(random(0xffff), HEX);

  Serial.print("Intentando MQTT como: ");
  Serial.println(clientId);

  bool conectado;

  if (strlen(MQTT_USER) > 0) {
    conectado = mqttClient.connect(clientId.c_str(), MQTT_USER, MQTT_PASS);
  } else {
    conectado = mqttClient.connect(clientId.c_str());
  }

  if (conectado) {
    Serial.println("=================================");
    Serial.println("MQTT CONECTADO CORRECTAMENTE");
    Serial.print("Broker: ");
    Serial.println(MQTT_BROKER);
    Serial.print("Puerto: ");
    Serial.println(MQTT_PORT);
    Serial.println("=================================");

    mqttClient.subscribe("ovotech/comandos");

  } else {
    int estado = mqttClient.state();
    Serial.print("ERROR MQTT. Codigo: ");
    Serial.println(estado);

    switch (estado) {
      case -4: Serial.println("MQTT_CONNECTION_TIMEOUT"); break;
      case -3: Serial.println("MQTT_CONNECTION_LOST"); break;
      case -2: Serial.println("MQTT_CONNECT_FAILED (red/puerto 1883 bloqueado o broker inalcanzable)"); break;
      case -1: Serial.println("MQTT_DISCONNECTED"); break;
      case 1:  Serial.println("MQTT_BAD_PROTOCOL"); break;
      case 2:  Serial.println("MQTT_BAD_CLIENT_ID"); break;
      case 3:  Serial.println("MQTT_UNAVAILABLE"); break;
      case 4:  Serial.println("MQTT_BAD_CREDENTIALS"); break;
      case 5:  Serial.println("MQTT_UNAUTHORIZED"); break;
      default: Serial.println("Codigo MQTT desconocido"); break;
    }
  }

  return conectado;
}

// ============================================
// PUBLICAR DATOS POR MQTT
// ============================================
void publicarDatosMQTT(float temperatura, float humedad) {
  StaticJsonDocument<256> doc;
  doc["temperatura"] = round(temperatura * 10) / 10.0;
  doc["humedad"] = round(humedad * 10) / 10.0;
  doc["device_id"] = DEVICE_ID;
  doc["lampara"] = estadoLampara ? 1 : 0;
  doc["cooler"] = estadoCooler ? 1 : 0;
  doc["failsafe"] = failsafeActivo ? 1 : 0;

  char buffer[256];
  serializeJson(doc, buffer);

  bool enviado = mqttClient.publish(MQTT_TOPIC, buffer);
  if (enviado) {
    Serial.print("Datos enviados por MQTT: ");
    Serial.println(buffer);
  } else {
    Serial.println("Fallo el envio por MQTT");
  }
}

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  Serial.println("Control de Incubadora/Temperatura Termostatico");

  dht.begin();
  ds18b20.begin();

  pinMode(RELE_LAMPARA, OUTPUT);
  pinMode(RELE_COOLER, OUTPUT);
  digitalWrite(RELE_LAMPARA, estadoLampara ? HIGH : LOW);
  digitalWrite(RELE_COOLER, estadoCooler ? HIGH : LOW);

  // WiFi primero: así esp_random() es aleatorio real y AP+STA quedan activos
  WiFi.persistent(false);       // no guardar credenciales WiFi en flash
  WiFi.mode(WIFI_AP_STA);

  DEVICE_ID = getDeviceId();
  Serial.println("---------------------------------------");
  Serial.print("TU ID DE INCUBADORA ES: ");
  Serial.println(DEVICE_ID);
  Serial.println("---------------------------------------");

  setupAccessPoint(); // SIEMPRE pide WiFi al arrancar

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  ultimaLecturaValida = millis();
}

// ============================================
// MANTENIMIENTO DE CONECTIVIDAD (no bloqueante, con backoff)
// Nota: esto solo reconecta el WiFi si se corta DURANTE la sesión.
// ============================================
void mantenerWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.reconnect();
  delay(500);
}

void mantenerMQTT() {
  if (mqttClient.connected()) {
    mqttBackoff = 5000;
    mqttClient.loop();
    return;
  }

  unsigned long ahora = millis();
  if (ahora - lastMqttAttempt >= mqttBackoff) {
    lastMqttAttempt = ahora;
    Serial.println("Conectando a MQTT...");
    if (connectMQTT()) {
      mqttBackoff = 5000;
    } else {
      mqttBackoff = min(mqttBackoff * 2, MQTT_BACKOFF_MAX);
    }
  }
}

// ============================================
// LOOP PRINCIPAL
// ============================================
void loop() {
  mantenerWiFi();
  if (WiFi.status() == WL_CONNECTED) {
    mantenerMQTT();
  }

  unsigned long actualMillis = millis();

  // ===================================================
  // LECTURA DE SENSORES Y CONTROL (Cada 2 segundos)
  // ===================================================
  if (actualMillis - previoMillisSensores >= intervaloSensores) {
    previoMillisSensores = actualMillis;

    float h = dht.readHumidity();
    ds18b20.requestTemperatures();
    float t = ds18b20.getTempCByIndex(0);

    bool lecturaValida = !isnan(h) && (t != DEVICE_DISCONNECTED_C);

    if (!lecturaValida) {
      Serial.println("Error leyendo sensores (DHT22 y/o DS18B20)");

      // FAIL-SAFE TÉRMICO: si pasa mucho tiempo sin lectura válida,
      // apagamos todo por seguridad en vez de mantener el último estado.
      if (actualMillis - ultimaLecturaValida >= FAILSAFE_TIMEOUT) {
        if (!failsafeActivo) {
          Serial.println("FAIL-SAFE: sin lecturas válidas hace demasiado tiempo. Apagando lampara por seguridad.");
          failsafeActivo = true;
        }
        estadoLampara = false;
        estadoCooler = false;
        digitalWrite(RELE_LAMPARA, LOW);
        digitalWrite(RELE_COOLER, LOW);
      }
      return;
    }

    // Lectura válida: resetea el contador de fail-safe
    ultimaLecturaValida = actualMillis;
    if (failsafeActivo) {
      Serial.println("Lecturas restablecidas. Fail-safe desactivado.");
      failsafeActivo = false;
    }

    // Lógica de control de temperatura (Lámpara y Cooler)
    if (t <= 37.5) {
      estadoLampara = true;
      estadoCooler = false;
    }
    else if (t >= 39.0) {
      estadoLampara = false;
      estadoCooler = true;
    }
    // Entre 37.5 y 39.0 mantiene el estado actual (histéresis)

    digitalWrite(RELE_LAMPARA, estadoLampara ? HIGH : LOW);
    digitalWrite(RELE_COOLER, estadoCooler ? HIGH : LOW);

    // Reporte en monitor serie
    float hic = dht.computeHeatIndex(t, h, false);
    Serial.print("Humedad: ");
    Serial.print(h);
    Serial.print("% | Temp: ");
    Serial.print(t);
    Serial.print(" °C | S.Termica: ");
    Serial.print(hic);
    Serial.println(" °C");
    Serial.print("[ACTUADORES] -> Lampara: ");
    Serial.print(estadoLampara ? "ENCENDIDA" : "APAGADA");
    Serial.print(" | Cooler: ");
    Serial.println(estadoCooler ? "ENCENDIDO" : "APAGADO");
    Serial.println("-----------------------------------------------------");

    // Envío por MQTT (solo si está conectado, para no bloquear)
    if (mqttClient.connected()) {
      publicarDatosMQTT(t, h);
    }
  }
}