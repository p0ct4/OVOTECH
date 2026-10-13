
// ==========================================
// OVOTECH - JavaScript simplificado
// ==========================================

// Configuración del servidor
const isLocal =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";

const API_BASE = isLocal
    ? "http://localhost:8000"
    : "https://ovotech.onrender.com";

const WS_URL = isLocal
    ? "ws://localhost:8000/ws"
    : "wss://ovotech.onrender.com/ws";


// Variables principales
const normalizarId = id => String(id || "").trim().toLowerCase();

let deviceId = normalizarId(localStorage.getItem("ovotech_device_id"));
let ws = null;
let reconnectTimer = null;
let pollTimer = null;
let ultimoId = null;


// Elementos del HTML
const pantallaVinculacion = document.getElementById("pantalla-vinculacion");
const pantallaPrincipal = document.getElementById("pantalla-principal");

const deviceIdInput = document.getElementById("deviceIdInput");
const vinculacionMsg = document.getElementById("vinculacionMsg");

const connection = document.getElementById("connection");

const tempValue = document.getElementById("tempValue");
const tempStatus = document.getElementById("tempStatus");

const humValue = document.getElementById("humValue");
const humStatus = document.getElementById("humStatus");


// ==========================================
// ESTADO DE CONEXIÓN
// ==========================================

function mostrarConexion(conectado) {
    const punto = connection.querySelector(".status-dot");
    const texto = connection.querySelector(".status-text");

    if (punto) {
        punto.classList.toggle("active", conectado);
    }

    if (texto) {
        texto.textContent = conectado ? "Conectado" : "Desconectado";
    }
}


// ==========================================
// ESTADOS DE TEMPERATURA Y HUMEDAD
// ==========================================

function estadoTemperatura(temp) {
    if (temp < 36 || temp > 39.5) {
        return { texto: "¡Peligro!", color: "#ef4444" };
    }

    if (temp < 37 || temp > 38.5) {
        return { texto: "Advertencia", color: "#f59e0b" };
    }

    return { texto: "Óptimo", color: "#22c55e" };
}


function estadoHumedad(hum) {
    if (hum < 40 || hum > 80) {
        return { texto: "¡Peligro!", color: "#ef4444" };
    }

    if (hum < 50 || hum > 70) {
        return { texto: "Advertencia", color: "#f59e0b" };
    }

    return { texto: "Óptimo", color: "#22c55e" };
}


// ==========================================
// ACTUALIZAR TEMPERATURA Y HUMEDAD
// ==========================================

function actualizarDatos(data) {
    if (!data || typeof data !== "object") return;

    // Si llega un ID de dispositivo, verificar que sea el nuestro.
    if (
        data.device_id != null &&
        normalizarId(data.device_id) !== deviceId
    ) {
        return;
    }

    // Evitar procesar dos veces la misma lectura.
    if (data.id != null) {
        const idActual = String(data.id);

        if (idActual === ultimoId) return;

        ultimoId = idActual;
    }

    const temperatura = Number(data.temperatura);
    const humedad = Number(data.humedad);

    // Verificar que los valores sean válidos.
    if (
        data.temperatura == null ||
        data.humedad == null ||
        !Number.isFinite(temperatura) ||
        !Number.isFinite(humedad)
    ) {
        console.warn("Lectura inválida:", data);
        return;
    }

    // Mostrar temperatura
    tempValue.textContent = temperatura.toFixed(1) + "°C";

    const estadoTemp = estadoTemperatura(temperatura);

    tempStatus.textContent = estadoTemp.texto;
    tempStatus.style.color = estadoTemp.color;

    // Mostrar humedad
    humValue.textContent = humedad.toFixed(1) + "%";

    const estadoHum = estadoHumedad(humedad);

    humStatus.textContent = estadoHum.texto;
    humStatus.style.color = estadoHum.color;
}


// ==========================================
// OBTENER ÚLTIMA LECTURA POR HTTP
// ==========================================

async function obtenerUltimaLectura() {
    if (!deviceId) return;

    const idConsultado = deviceId;

    try {
        const respuesta = await fetch(
            `${API_BASE}/api/lecturas/ultima/${encodeURIComponent(idConsultado)}`
        );

        if (!respuesta.ok) return;

        const datos = await respuesta.json();

        // Ignorar respuestas de una incubadora anterior.
        if (idConsultado !== deviceId) return;

        actualizarDatos(datos);

    } catch (error) {
        console.warn("No se pudo obtener la última lectura:", error);
    }
}


// ==========================================
// CONEXIÓN WEBSOCKET
// ==========================================

function conectarWebSocket() {
    if (!deviceId) return;

    clearTimeout(reconnectTimer);

    // Cerrar una conexión anterior si existe.
    if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;

        ws.close();
    }

    mostrarConexion(false);

    const socket = new WebSocket(WS_URL);
    ws = socket;

    socket.onopen = () => {
        if (socket !== ws) return;

        console.log("WebSocket conectado");
        mostrarConexion(true);

        // Actualizar datos al conectar.
        obtenerUltimaLectura();
    };

    socket.onmessage = event => {
        if (socket !== ws) return;

        if (typeof event.data !== "string") return;
        if (event.data === "pong") return;

        try {
            const mensaje = JSON.parse(event.data);

            // Nueva lectura enviada por el servidor.
            if (mensaje.type === "lectura" && mensaje.data) {
                actualizarDatos(mensaje.data);
            }

            // Si el servidor envía un histórico,
            // usar solamente la última lectura de nuestra incubadora.
            if (
                mensaje.type === "historico" &&
                Array.isArray(mensaje.data)
            ) {
                const lecturas = mensaje.data.filter(
                    lectura =>
                        normalizarId(lectura.device_id) === deviceId
                );

                if (lecturas.length > 0) {
                    actualizarDatos(lecturas[lecturas.length - 1]);
                }
            }

        } catch (error) {
            console.warn("Mensaje WebSocket no válido:", error);
        }
    };

    socket.onerror = () => {
        if (socket !== ws) return;

        mostrarConexion(false);
        console.warn("Error de conexión WebSocket");
    };

    socket.onclose = () => {
        if (socket !== ws) return;

        mostrarConexion(false);

        console.log("WebSocket desconectado. Reintentando...");

        // Intentar reconectar después de 3 segundos.
        reconnectTimer = setTimeout(conectarWebSocket, 3000);
    };
}


// ==========================================
// VINCULAR INCUBADORA
// ==========================================

async function vincularDispositivo() {
    const nuevoId = normalizarId(deviceIdInput.value);

    if (!nuevoId) {
        vinculacionMsg.textContent = "Ingresá el ID de tu incubadora.";
        vinculacionMsg.style.color = "#ef4444";
        return;
    }

    vinculacionMsg.textContent = "Conectando...";
    vinculacionMsg.style.color = "#f59e0b";

    try {
        const respuesta = await fetch(`${API_BASE}/api/vincular`, {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                device_id: nuevoId,
                nombre_usuario: null
            })
        });

        if (!respuesta.ok) {
            let mensajeError = "No se pudo vincular la incubadora.";

            try {
                const error = await respuesta.json();

                if (typeof error.detail === "string") {
                    mensajeError = error.detail;
                } else if (Array.isArray(error.detail)) {
                    mensajeError = error.detail
                        .map(item => item.msg || "Error de validación")
                        .join(", ");
                }

            } catch (e) {
                mensajeError = `Error HTTP ${respuesta.status}`;
            }

            vinculacionMsg.textContent = mensajeError;
            vinculacionMsg.style.color = "#ef4444";

            return;
        }

        // Guardar el dispositivo vinculado.
        localStorage.setItem("ovotech_device_id", nuevoId);
        deviceId = nuevoId;

        vinculacionMsg.textContent = "¡Incubadora vinculada!";
        vinculacionMsg.style.color = "#22c55e";

        // Entrar al panel sin recargar la página.
        mostrarPanel();

    } catch (error) {
        console.error("Error al vincular:", error);

        vinculacionMsg.textContent =
            "No se pudo conectar con el servidor. Intentá nuevamente.";

        vinculacionMsg.style.color = "#ef4444";
    }
}


// ==========================================
// CAMBIAR DE INCUBADORA
// ==========================================

function desvincularDispositivo() {
    const confirmar = confirm(
        "¿Querés cambiar de incubadora?"
    );

    if (!confirmar) return;

    localStorage.removeItem("ovotech_device_id");

    deviceId = "";
    ultimoId = null;

    clearTimeout(reconnectTimer);
    clearInterval(pollTimer);

    if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;

        ws.close();
        ws = null;
    }

    mostrarConexion(false);

    tempValue.textContent = "--.-°C";
    humValue.textContent = "--.-%";

    tempStatus.textContent = "Esperando datos...";
    humStatus.textContent = "Esperando datos...";

    tempStatus.style.color = "";
    humStatus.style.color = "";

    pantallaPrincipal.style.display = "none";
    pantallaVinculacion.style.display = "flex";

    deviceIdInput.value = "";
    vinculacionMsg.textContent = "";

    deviceIdInput.focus();
}


// ==========================================
// MOSTRAR PANEL PRINCIPAL
// ==========================================

function mostrarPanel() {
    pantallaVinculacion.style.display = "none";
    pantallaPrincipal.style.display = "block";

    const miDeviceId = document.getElementById("miDeviceId");
    const footerDevice = document.getElementById("footer-device");

    if (miDeviceId) {
        miDeviceId.textContent = deviceId;
    }

    if (footerDevice) {
        footerDevice.textContent = deviceId;
    }

    ultimoId = null;

    // Cargar la última lectura.
    obtenerUltimaLectura();

    // Conectar al servidor en tiempo real.
    conectarWebSocket();

    // Consulta de respaldo cada 5 segundos.
    clearInterval(pollTimer);

    pollTimer = setInterval(obtenerUltimaLectura, 5000);
}


// ==========================================
// INICIAR PÁGINA
// ==========================================

document.addEventListener("DOMContentLoaded", () => {

    if (deviceId) {
        mostrarPanel();
    } else {
        pantallaVinculacion.style.display = "flex";
        pantallaPrincipal.style.display = "none";

        deviceIdInput.focus();
    }

    // Permitir vincular presionando Enter.
    deviceIdInput.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            vincularDispositivo();
        }
    });

    // Al volver a la pestaña, actualizar los datos.
    document.addEventListener("visibilitychange", () => {
        if (document.hidden || !deviceId) return;

        obtenerUltimaLectura();

        if (!ws || ws.readyState === WebSocket.CLOSED) {
            conectarWebSocket();
        }
    });

});
