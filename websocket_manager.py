
from typing import List
from fastapi import WebSocket


# ============================================================
# ADMINISTRADOR DE CONEXIONES WEBSOCKET
# ============================================================

# Creamos la clase encargada de administrar las conexiones
# WebSocket entre el backend y los clientes del frontend.
class ConnectionManager:

    # Constructor de la clase.
    def __init__(self):

        # Lista que almacena todas las conexiones WebSocket activas.
        # Cada elemento representa un cliente conectado al servidor.
        self.active_connections: List[WebSocket] = []


    # ============================================================
    # CONECTAR CLIENTE
    # ============================================================

    # Recibe una nueva conexión WebSocket desde el frontend.
    async def connect(self, websocket: WebSocket):

        # Aceptamos la conexión para establecer la comunicación
        # entre el cliente y el servidor.
        await websocket.accept()

        # Agregamos la conexión a la lista de clientes activos.
        self.active_connections.append(websocket)


    # ============================================================
    # DESCONECTAR CLIENTE
    # ============================================================

    # Elimina una conexión WebSocket cuando un cliente se desconecta.
    def disconnect(self, websocket: WebSocket):

        # Comprobamos que la conexión exista en la lista.
        if websocket in self.active_connections:

            # Eliminamos la conexión para que no siga recibiendo mensajes.
            self.active_connections.remove(websocket)


    # ============================================================
    # ENVIAR MENSAJES A TODOS LOS CLIENTES
    # ============================================================

    # Envía un mensaje a todos los clientes que están conectados.
    # Se utiliza para transmitir las nuevas lecturas de OVOTECH
    # en tiempo real al frontend.
    async def broadcast(self, message: dict):

        # Creamos una lista para guardar las conexiones
        # que presenten errores durante el envío.
        disconnected = []

        # Recorremos todas las conexiones WebSocket activas.
        for connection in self.active_connections:

            try:

                # Enviamos el mensaje en formato JSON al cliente actual.
                await connection.send_json(message)

            except Exception:

                # Si ocurre un error durante el envío,
                # guardamos la conexión para eliminarla posteriormente.
                disconnected.append(connection)

        # Recorremos las conexiones que presentaron errores.
        for conn in disconnected:

            # Eliminamos las conexiones que ya no funcionan.
            self.disconnect(conn)


# ============================================================
# INSTANCIA DEL ADMINISTRADOR
# ============================================================

# Creamos una instancia global de ConnectionManager.
# De esta manera, todo el backend puede utilizar el mismo administrador
# para conectar, desconectar y enviar mensajes a los clientes.
manager = ConnectionManager()
