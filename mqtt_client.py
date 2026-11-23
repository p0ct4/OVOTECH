
# Importamos la biblioteca Paho MQTT para conectarnos
# a un servidor MQTT y recibir mensajes de las incubadoras.
import paho.mqtt.client as mqtt

# Importamos json para convertir los mensajes recibidos
# desde MQTT en objetos de Python.
import json

# Importamos os para acceder a las variables de entorno.
import os

# Importamos time para obtener la fecha y hora actual.
import time

# Importamos random para generar números aleatorios.
import random

# Importamos Callable y Any para definir los tipos de datos
# de las funciones que recibirá nuestra clase.
from typing import Callable, Any


# ============================================================
# CONFIGURACIÓN MQTT
# ============================================================

# Dirección del servidor MQTT al que se conectará OVOTECH.
# Si no existe la variable MQTT_BROKER en el archivo de entorno,
# se utiliza broker.hivemq.com como servidor predeterminado.
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")

# Puerto utilizado para establecer la conexión MQTT.
# Por defecto se utiliza el puerto 1883.
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

# Tema o tópico MQTT al que se suscribirá el backend.
# Por este tópico las incubadoras ESP32 publican sus mediciones.
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "ovotech/sensor")


# ============================================================
# CLASE MQTT CLIENT
# ============================================================

# Creamos la clase MQTTClient, encargada de administrar
# la conexión entre el backend de OVOTECH y el servidor MQTT.
class MQTTClient:

    # Constructor de la clase.
    # Se ejecuta cuando creamos una nueva instancia de MQTTClient.
    # message_handler recibe una función que procesará
    # los mensajes enviados por las incubadoras.
    def __init__(self, message_handler: Callable[[dict], Any]):

        # Guardamos la función encargada de procesar los mensajes MQTT.
        self.message_handler = message_handler

        # Variable que indica si existe una conexión activa con el broker.
        # Inicialmente se establece en False.
        self.connected = False

        # Generamos un identificador único para el cliente MQTT.
        # random.randint genera un número aleatorio entre 1000 y 9999.
        # time.time() obtiene la fecha y hora actual en formato timestamp.
        # Esto ayuda a evitar conflictos de identificación
        # cuando Render reinicia el backend.
        client_id = f"ovotech_{random.randint(1000,9999)}_{int(time.time())}"

        # Creamos el cliente MQTT utilizando la biblioteca Paho.
        # VERSION2 establece la versión 2 de las funciones de retorno
        # (callbacks) de Paho MQTT.
        # client_id identifica de manera única a nuestro cliente.
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id
        )

        # Asignamos las funciones que se ejecutarán
        # cuando ocurran diferentes eventos de la conexión MQTT.

        # Se ejecuta cuando el cliente logra conectarse al broker.
        self.client.on_connect = self.on_connect

        # Se ejecuta cuando el cliente recibe un mensaje MQTT.
        self.client.on_message = self.on_message

        # Se ejecuta cuando el cliente pierde la conexión.
        self.client.on_disconnect = self.on_disconnect

        # Configuramos la reconexión automática.
        # min_delay=1 establece una espera inicial de 1 segundo.
        # max_delay=30 establece una espera máxima de 30 segundos.
        # La espera aumenta progresivamente cuando fallan las reconexiones.
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)


    # ============================================================
    # EVENTO DE CONEXIÓN
    # ============================================================

    # Esta función se ejecuta automáticamente cuando el cliente
    # intenta conectarse al servidor MQTT.
    def on_connect(self, client, userdata, flags, reason_code, properties):

        # Comprobamos si el código de respuesta es 0.
        # Esto significa que la conexión se realizó correctamente.
        if reason_code == 0:

            # Actualizamos el estado de conexión.
            self.connected = True

            # Mostramos un mensaje indicando que nos conectamos a HiveMQ.
            # También mostramos el identificador único del cliente.
            print(f"Conectado a HiveMQ - ClientID: {client._client_id.decode()}")

            # Nos suscribimos al tópico configurado.
            # A partir de este momento recibiremos los mensajes
            # que las incubadoras publiquen en ovotech/sensor.
            client.subscribe(MQTT_TOPIC)

            # Mostramos en la terminal el tópico al que nos suscribimos.
            print(f"Suscrito a: {MQTT_TOPIC}")

        else:

            # Si la conexión falla, indicamos que el cliente
            # no está conectado.
            self.connected = False

            # Mostramos el código de error devuelto por el broker.
            print(f"Error conexión MQTT, código: {reason_code}")


    # ============================================================
    # EVENTO DE DESCONEXIÓN
    # ============================================================

    # Esta función se ejecuta cuando el cliente MQTT pierde
    # la conexión con el servidor.
    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):

        # Actualizamos el estado para indicar que no hay conexión.
        self.connected = False

        # Mostramos un mensaje indicando que se perdió la conexión
        # y que el cliente intentará conectarse nuevamente.
        print(f"Desconectado (código: {reason_code}). Reconectando...")

        # La reconexión automática se gestiona mediante
        # loop_start() y reconnect_delay_set().


    # ============================================================
    # RECEPCIÓN DE MENSAJES MQTT
    # ============================================================

    # Esta función se ejecuta automáticamente cada vez que
    # el cliente recibe un mensaje desde el tópico al que está suscrito.
    def on_message(self, client, userdata, msg):

        try:

            # Decodificamos el contenido del mensaje recibido.
            # msg.payload contiene los datos en formato de bytes.
            # decode() los convierte en texto.
            # json.loads() transforma el texto JSON en un diccionario Python.
            payload = json.loads(msg.payload.decode())

            # Mostramos en la terminal el contenido del mensaje recibido.
            print(f"MQTT: {payload}")

            # Comprobamos que exista una función encargada
            # de procesar los mensajes recibidos.
            if self.message_handler:

                # Ejecutamos la función que recibimos en el constructor
                # y le enviamos los datos obtenidos desde MQTT.
                #
                # En OVOTECH esta función es process_mqtt_message(),
                # definida en main.py.
                self.message_handler(payload)

        # Capturamos errores cuando el mensaje recibido
        # no tiene un formato JSON válido.
        except json.JSONDecodeError:

            # Mostramos un aviso indicando que el mensaje
            # recibido no pudo convertirse a JSON.
            print("Payload no es JSON válido")

        # Capturamos cualquier otro error que pueda ocurrir
        # durante la recepción o el procesamiento del mensaje.
        except Exception as e:

            # Mostramos el error en la terminal.
            print(f"Error MQTT: {e}")


    # ============================================================
    # INICIAR CONEXIÓN MQTT
    # ============================================================

    # Esta función inicia la conexión entre OVOTECH y el broker MQTT.
    def start(self):

        # Iniciamos una conexión asíncrona con el servidor MQTT.
        # connect_async() permite intentar la conexión en segundo plano
        # sin bloquear la ejecución principal del backend.
        #
        # MQTT_BROKER: dirección del servidor.
        # MQTT_PORT: puerto de conexión.
        # keepalive=60: intervalo máximo de comunicación para
        # mantener activa la conexión MQTT.
        self.client.connect_async(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60
        )

        # Iniciamos el bucle de comunicación MQTT en un hilo separado.
        # loop_start() permite recibir mensajes, gestionar la conexión
        # y realizar reconexiones automáticas sin bloquear FastAPI.
        self.client.loop_start()

        # Mostramos un mensaje indicando que MQTT comenzó a funcionar.
        print("MQTT iniciado (conectando en segundo plano...)")


    # ============================================================
    # DETENER CONEXIÓN MQTT
    # ============================================================

    # Esta función se ejecuta cuando queremos detener
    # la comunicación entre OVOTECH y el servidor MQTT.
    def stop(self):

        # Detenemos el bucle de comunicación MQTT.
        # Esto finaliza el hilo encargado de gestionar los mensajes.
        self.client.loop_stop()

        # Cerramos la conexión con el servidor MQTT.
        self.client.disconnect()

        # Mostramos un mensaje indicando que MQTT se detuvo.
        print("MQTT detenido")
