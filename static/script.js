
// ============================================================
// CONFIGURACIÓN DEL SERVIDOR
// ============================================================

// Comprobamos si la página se está ejecutando localmente.
const isLocal =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";

// Definimos la dirección de la API según el entorno.
// Si estamos trabajando localmente, utilizamos localhost.
// Si está publicado, utilizamos el servidor de OVOTECH en Render.
const API_BASE = isLocal
    ? "http://localhost:8000"
    : "https://ovotech.onrender.com";

// Definimos la dirección del WebSocket.
// ws:// se utiliza para conexiones locales.
// wss:// se utiliza para conexiones seguras en producción.
const WS_URL = isLocal
    ? "ws://localhost:8000/ws"
    : "wss://ovotech.onrender.com/ws";


// ============================================================
// VARIABLES PRINCIPALES
// ============================================================

// Función que normaliza el identificador de una incubadora.
// Convierte el ID a texto, elimina espacios al principio y al final
// y transforma todas las letras a minúsculas.
const normalizarId = id => String(id || "").trim().toLowerCase();

// Recuperamos el identificador de la incubadora guardado
// anteriormente en el almacenamiento local del navegador.
let deviceId = normalizarId(localStorage.getItem("ovotech_device_id"));

// Variable que almacena la conexión WebSocket actual.
let ws = null;

// Almacena el temporizador utilizado para intentar reconectar el WebSocket.
let reconnectTimer = null;

// Almacena el temporizador de las consultas periódicas a la API.
let pollTimer = null;

// Guarda el ID de la última lectura procesada para evitar duplicados.
let ultimoId = null;


// ============================================================
// ELEMENTOS DEL HTML
// ============================================================

// Obtenemos los elementos HTML que se utilizarán
// para mostrar las diferentes pantallas de la aplicación.
const pantallaVinculacion = document.getElementById("pantalla-vinculacion");
const pantallaPrincipal = document.getElementById("pantalla-principal");

// Campo donde el usuario introduce el identificador de su incubadora
// y elemento donde se muestran los mensajes de vinculación.
const deviceIdInput = document.getElementById("deviceIdInput");
const vinculacionMsg = document.getElementById("vinculacionMsg");

// Elemento que muestra el estado de conexión con el servidor.
const connection = document.getElementById("connection");

// Elementos donde se muestra la temperatura y su estado.
const tempValue = document.getElementById("tempValue");
const tempStatus = document.getElementById("tempStatus");

// Elementos donde se muestra la humedad y su estado.
const humValue = document.getElementById("humValue");
const humStatus = document.getElementById("humStatus");


// ============================================================
// ESTADO DE CONEXIÓN
// ============================================================

// Actualiza visualmente el estado de conexión del sistema.
// Recibe true si está conectado y false si está desconectado.
function mostrarConexion(conectado) {

    // Buscamos dentro del elemento de conexión
    // el punto visual que representa el estado.
    const punto = connection.querySelector(".status-dot");

    // Buscamos el texto que muestra el estado de conexión.
    const texto = connection.querySelector(".status-text");

    // Agregamos o quitamos la clase active según la conexión.
    if (punto) {
        punto.classList.toggle("active", conectado);
    }

    // Actualizamos el texto mostrado en pantalla.
    if (texto) {
        texto.textContent = conectado ? "Conectado" : "Desconectado";
    }
}


// ============================================================
// ESTADOS DE TEMPERATURA Y HUMEDAD
// ============================================================

// Evalúa la temperatura recibida y determina si se encuentra
// en un estado óptimo, de advertencia o de peligro.
function estadoTemperatura(temp) {

    // Si la temperatura es menor a 36 °C o mayor a 39.5 °C,
    // se considera que está en estado de peligro.
    if (temp < 36 || temp > 39.5) {
        return { texto: "¡Peligro!", color: "#ef4444" };
    }

    // Si está fuera del rango óptimo, pero dentro del rango
    // de advertencia, se muestra una advertencia.
    if (temp < 37 || temp > 38.5) {
        return { texto: "Advertencia", color: "#f59e0b" };
    }

    // Si no se cumple ninguna condición anterior,
    // la temperatura se encuentra en estado óptimo.
    return { texto: "Óptimo", color: "#22c55e" };
}


// Evalúa la humedad recibida y determina su estado.
function estadoHumedad(hum) {

    // Si la humedad es menor a 40 % o mayor a 80 %,
    // se considera que está en estado de peligro.
    if (hum < 40 || hum > 80) {
        return { texto: "¡Peligro!", color: "#ef4444" };
    }

    // Si está fuera del rango óptimo, se muestra una advertencia.
    if (hum < 50 || hum > 70) {
        return { texto: "Advertencia", color: "#f59e0b" };
    }

    // Si se encuentra dentro del rango óptimo,
    // devolvemos el estado correspondiente.
    return { texto: "Óptimo", color: "#22c55e" };
}


// ============================================================
// ACTUALIZAR TEMPERATURA Y HUMEDAD
// ============================================================

// Recibe los datos de una lectura y actualiza los valores
// mostrados en el panel principal de OVOTECH.
function actualizarDatos(data) {

    // Comprobamos que los datos existan y sean un objeto válido.
    if (!data || typeof data !== "object") return;

    // Si el mensaje contiene un identificador de dispositivo,
    // comprobamos que corresponda a la incubadora seleccionada.
    // Si pertenece a otra incubadora, ignoramos el mensaje.
    if (
        data.device_id != null &&
        normalizarId(data.device_id) !== deviceId
    ) {
        return;
    }

    // Evitamos procesar dos veces una misma lectura.
    if (data.id != null) {

        // Convertimos el ID a texto para poder compararlo.
        const idActual = String(data.id);

        // Si el ID coincide con la última lectura procesada,
        // no necesitamos actualizar nuevamente la pantalla.
        if (idActual === ultimoId) return;

        // Guardamos el ID de la lectura actual.
        ultimoId = idActual;
    }

    // Convertimos los valores recibidos a números.
    const temperatura = Number(data.temperatura);
    const humedad = Number(data.humedad);

    // Comprobamos que ambos valores existan y sean números válidos.
    if (
        data.temperatura == null ||
        data.humedad == null ||
        !Number.isFinite(temperatura) ||
        !Number.isFinite(humedad)
    ) {
        console.warn("Lectura inválida:", data);
        return;
    }

    // Mostramos la temperatura con un decimal y su unidad correspondiente.
    tempValue.textContent = temperatura.toFixed(1) + "°C";

    // Obtenemos el estado de la temperatura.
    const estadoTemp = estadoTemperatura(temperatura);

    // Actualizamos el texto y el color según el estado obtenido.
    tempStatus.textContent = estadoTemp.texto;
    tempStatus.style.color = estadoTemp.color;

    // Mostramos la humedad con un decimal y el símbolo de porcentaje.
    humValue.textContent = humedad.toFixed(1) + "%";

    // Obtenemos el estado de la humedad.
    const estadoHum = estadoHumedad(humedad);

    // Actualizamos el texto y el color según el estado obtenido.
    humStatus.textContent = estadoHum.texto;
    humStatus.style.color = estadoHum.color;
}


// ============================================================
// OBTENER ÚLTIMA LECTURA POR HTTP
// ============================================================

// Consulta al backend para obtener la última lectura
// registrada de la incubadora seleccionada.
async function obtenerUltimaLectura() {

    // Si no hay una incubadora seleccionada, no realizamos la consulta.
    if (!deviceId) return;

    // Guardamos el ID consultado para comprobar que no haya cambiado
    // mientras esperamos la respuesta del servidor.
    const idConsultado = deviceId;

    try {

        // Realizamos una solicitud HTTP GET al endpoint de FastAPI.
        // encodeURIComponent permite enviar correctamente el identificador
        // dentro de la dirección de la solicitud.
        const respuesta = await fetch(
            `${API_BASE}/api/lecturas/ultima/${encodeURIComponent(idConsultado)}`
        );

        // Si la respuesta no fue exitosa, detenemos la ejecución.
        if (!respuesta.ok) return;

        // Convertimos la respuesta JSON del servidor en un objeto JavaScript.
        const datos = await respuesta.json();

        // Comprobamos que el usuario siga consultando la misma incubadora.
        // Así evitamos mostrar datos de un dispositivo anterior.
        if (idConsultado !== deviceId) return;

        // Enviamos los datos recibidos a la función que actualiza el panel.
        actualizarDatos(datos);

    } catch (error) {

        // Mostramos un aviso si no se pudo obtener la información.
        console.warn("No se pudo obtener la última lectura:", error);
    }
}


// ============================================================
// CONEXIÓN WEBSOCKET
// ============================================================

// Establece una conexión WebSocket con el backend
// para recibir las nuevas lecturas en tiempo real.
function conectarWebSocket() {

    // Si no hay una incubadora seleccionada, no conectamos.
    if (!deviceId) return;

    // Cancelamos cualquier intento de reconexión pendiente.
    clearTimeout(reconnectTimer);

    // Si ya existe una conexión anterior, la cerramos.
    if (ws) {

        // Eliminamos los eventos asociados a la conexión anterior
        // para evitar que ejecuten acciones después de cerrarla.
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;

        // Cerramos la conexión WebSocket anterior.
        ws.close();
    }

    // Mostramos que todavía no existe una conexión activa.
    mostrarConexion(false);

    // Creamos una nueva conexión WebSocket con el servidor.
    const socket = new WebSocket(WS_URL);

    // Guardamos la nueva conexión en la variable global.
    ws = socket;


    // ------------------------------------------------------------
    // EVENTO: CONEXIÓN ESTABLECIDA
    // ------------------------------------------------------------

    // Se ejecuta cuando el WebSocket logra conectarse correctamente.
    socket.onopen = () => {

        // Comprobamos que esta siga siendo la conexión actual.
        if (socket !== ws) return;

        // Mostramos en la consola que la conexión fue establecida.
        console.log("WebSocket conectado");

        // Actualizamos el indicador visual de conexión.
        mostrarConexion(true);

        // Consultamos la última lectura para actualizar los datos
        // inmediatamente después de establecer la conexión.
        obtenerUltimaLectura();
    };


    // ------------------------------------------------------------
    // EVENTO: RECEPCIÓN DE MENSAJES
    // ------------------------------------------------------------

    // Se ejecuta cada vez que el backend envía un mensaje WebSocket.
    socket.onmessage = event => {

        // Ignoramos los mensajes de conexiones anteriores.
        if (socket !== ws) return;

        // Comprobamos que el mensaje recibido sea texto.
        if (typeof event.data !== "string") return;

        // Ignoramos el mensaje pong utilizado para comprobar la conexión.
        if (event.data === "pong") return;

        try {

            // Convertimos el mensaje JSON recibido en un objeto JavaScript.
            const mensaje = JSON.parse(event.data);

            // Comprobamos si el mensaje contiene una nueva lectura.
            if (mensaje.type === "lectura" && mensaje.data) {

                // Actualizamos los valores de temperatura y humedad.
                actualizarDatos(mensaje.data);
            }

            // Comprobamos si el servidor envió un conjunto de lecturas
            // correspondientes al historial.
            if (
                mensaje.type === "historico" &&
                Array.isArray(mensaje.data)
            ) {

                // Filtramos las lecturas para conservar solamente
                // las que pertenecen a la incubadora seleccionada.
                const lecturas = mensaje.data.filter(
                    lectura =>
                        normalizarId(lectura.device_id) === deviceId
                );

                // Si encontramos lecturas, utilizamos la última
                // para actualizar los valores del panel.
                if (lecturas.length > 0) {
                    actualizarDatos(lecturas[lecturas.length - 1]);
                }
            }

        } catch (error) {

            // Si el mensaje no tiene un formato JSON válido,
            // mostramos el error en la consola.
            console.warn("Mensaje WebSocket no válido:", error);
        }
    };


    // ------------------------------------------------------------
    // EVENTO: ERROR DE CONEXIÓN
    // ------------------------------------------------------------

    // Se ejecuta cuando ocurre un error en la conexión WebSocket.
    socket.onerror = () => {

        // Ignoramos los errores de conexiones anteriores.
        if (socket !== ws) return;

        // Actualizamos el indicador de conexión.
        mostrarConexion(false);

        // Mostramos el error en la consola.
        console.warn("Error de conexión WebSocket");
    };


    // ------------------------------------------------------------
    // EVENTO: CONEXIÓN CERRADA
    // ------------------------------------------------------------

    // Se ejecuta cuando la conexión WebSocket se cierra.
    socket.onclose = () => {

        // Comprobamos que siga siendo la conexión actual.
        if (socket !== ws) return;

        // Mostramos que el servidor está desconectado.
        mostrarConexion(false);

        // Informamos que se realizará un nuevo intento de conexión.
        console.log("WebSocket desconectado. Reintentando...");

        // Programamos un nuevo intento de conexión después de 3 segundos.
        reconnectTimer = setTimeout(conectarWebSocket, 3000);
    };
}


// ============================================================
// VINCULAR INCUBADORA
// ============================================================

// Envía al backend una solicitud para vincular una incubadora
// con el sistema OVOTECH.
async function vincularDispositivo() {

    // Obtenemos el ID introducido por el usuario y lo normalizamos.
    const nuevoId = normalizarId(deviceIdInput.value);

    // Comprobamos que el usuario haya ingresado un identificador.
    if (!nuevoId) {

        // Mostramos un mensaje indicando que debe ingresar el ID.
        vinculacionMsg.textContent = "Ingresá el ID de tu incubadora.";
        vinculacionMsg.style.color = "#ef4444";

        // Detenemos la función.
        return;
    }

    // Mostramos un mensaje mientras se realiza la vinculación.
    vinculacionMsg.textContent = "Conectando...";
    vinculacionMsg.style.color = "#f59e0b";

    try {

        // Enviamos una solicitud POST al endpoint de vinculación.
        const respuesta = await fetch(`${API_BASE}/api/vincular`, {

            // Indicamos que el método HTTP utilizado será POST.
            method: "POST",

            // Indicamos que el contenido enviado estará en formato JSON.
            headers: {
                "Content-Type": "application/json"
            },

            // Convertimos los datos del dispositivo a formato JSON.
            // JSON.stringify transforma el objeto JavaScript en texto JSON.
            body: JSON.stringify({
                device_id: nuevoId,
                nombre_usuario: null
            })
        });

        // Comprobamos si el servidor respondió con un error.
        if (!respuesta.ok) {

            // Definimos un mensaje de error predeterminado.
            let mensajeError = "No se pudo vincular la incubadora.";

            try {

                // Intentamos obtener los detalles del error enviado por FastAPI.
                const error = await respuesta.json();

                // Si el detalle es un texto, lo utilizamos directamente.
                if (typeof error.detail === "string") {
                    mensajeError = error.detail;

                // Si el detalle es una lista de errores de validación,
                // obtenemos los mensajes y los unimos en un solo texto.
                } else if (Array.isArray(error.detail)) {
                    mensajeError = error.detail
                        .map(item => item.msg || "Error de validación")
                        .join(", ");
                }

            } catch (e) {

                // Si no podemos obtener el detalle del error,
                // mostramos el código HTTP recibido.
                mensajeError = `Error HTTP ${respuesta.status}`;
            }

            // Mostramos el mensaje de error en pantalla.
            vinculacionMsg.textContent = mensajeError;
            vinculacionMsg.style.color = "#ef4444";

            // Detenemos la función porque la vinculación falló.
            return;
        }

        // Guardamos el ID de la incubadora en localStorage.
        // Esto permite recordar el dispositivo cuando el usuario
        // vuelva a ingresar a la página.
        localStorage.setItem("ovotech_device_id", nuevoId);

        // Actualizamos la variable global con el nuevo identificador.
        deviceId = nuevoId;

        // Mostramos un mensaje indicando que la vinculación fue exitosa.
        vinculacionMsg.textContent = "¡Incubadora vinculada!";
        vinculacionMsg.style.color = "#22c55e";

        // Mostramos el panel principal sin necesidad de recargar la página.
        mostrarPanel();

    } catch (error) {

        // Capturamos errores de conexión o solicitudes fallidas.
        console.error("Error al vincular:", error);

        // Informamos al usuario que no fue posible conectar con el servidor.
        vinculacionMsg.textContent =
            "No se pudo conectar con el servidor. Intentá nuevamente.";

        vinculacionMsg.style.color = "#ef4444";
    }
}


// ============================================================
// CAMBIAR DE INCUBADORA
// ============================================================

// Permite al usuario desvincular la incubadora actual
// del navegador y seleccionar otra.
function desvincularDispositivo() {

    // Mostramos una ventana de confirmación antes de cambiar de dispositivo.
    const confirmar = confirm(
        "¿Querés cambiar de incubadora?"
    );

    // Si el usuario cancela, detenemos la función.
    if (!confirmar) return;

    // Eliminamos el identificador guardado en localStorage.
    localStorage.removeItem("ovotech_device_id");

    // Limpiamos el identificador de la incubadora seleccionada.
    deviceId = "";

    // Reiniciamos el ID de la última lectura procesada.
    ultimoId = null;

    // Cancelamos los temporizadores de reconexión y consultas periódicas.
    clearTimeout(reconnectTimer);
    clearInterval(pollTimer);

    // Si existe una conexión WebSocket, procedemos a cerrarla.
    if (ws) {

        // Eliminamos los eventos de la conexión anterior.
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;

        // Cerramos la conexión y limpiamos la variable.
        ws.close();
        ws = null;
    }

    // Actualizamos el estado visual de conexión.
    mostrarConexion(false);

    // Reiniciamos los valores de temperatura y humedad.
    tempValue.textContent = "--.-°C";
    humValue.textContent = "--.-%";

    // Mostramos los mensajes iniciales de espera de datos.
    tempStatus.textContent = "Esperando datos...";
    humStatus.textContent = "Esperando datos...";

    // Eliminamos los colores anteriores de los estados.
    tempStatus.style.color = "";
    humStatus.style.color = "";

    // Ocultamos el panel principal.
    pantallaPrincipal.style.display = "none";

    // Volvemos a mostrar la pantalla de vinculación.
    pantallaVinculacion.style.display = "flex";

    // Limpiamos el campo donde se ingresa el identificador.
    deviceIdInput.value = "";

    // Eliminamos cualquier mensaje anterior de vinculación.
    vinculacionMsg.textContent = "";

    // Colocamos el cursor en el campo para ingresar un nuevo ID.
    deviceIdInput.focus();
}


// ============================================================
// MOSTRAR PANEL PRINCIPAL
// ============================================================

// Se encarga de mostrar el panel principal de OVOTECH
// una vez que el usuario tiene una incubadora vinculada.
function mostrarPanel() {

    // Ocultamos la pantalla de vinculación.
    pantallaVinculacion.style.display = "none";

    // Mostramos el panel principal.
    pantallaPrincipal.style.display = "block";

    // Obtenemos los elementos HTML donde se muestra
    // el identificador de la incubadora.
    const miDeviceId = document.getElementById("miDeviceId");
    const footerDevice = document.getElementById("footer-device");

    // Mostramos el ID en la sección principal, si el elemento existe.
    if (miDeviceId) {
        miDeviceId.textContent = deviceId;
    }

    // Mostramos el ID también en el pie de página.
    if (footerDevice) {
        footerDevice.textContent = deviceId;
    }

    // Reiniciamos el identificador de la última lectura procesada.
    ultimoId = null;

    // Consultamos la última lectura almacenada en el backend.
    obtenerUltimaLectura();

    // Establecemos la conexión WebSocket para recibir
    // las nuevas mediciones en tiempo real.
    conectarWebSocket();

    // Configuramos una consulta de respaldo cada 5 segundos.
    // Esto permite actualizar los datos mediante HTTP
    // aunque WebSocket no esté funcionando.
    clearInterval(pollTimer);

    pollTimer = setInterval(obtenerUltimaLectura, 5000);
}


// ============================================================
// INICIAR PÁGINA
// ============================================================

// Esperamos a que el documento HTML esté completamente cargado
// antes de ejecutar las funciones que utilizan sus elementos.
document.addEventListener("DOMContentLoaded", () => {

    // Comprobamos si existe un ID de incubadora guardado.
    if (deviceId) {

        // Si existe, mostramos directamente el panel principal.
        mostrarPanel();

    } else {

        // Si no hay una incubadora vinculada,
        // mostramos la pantalla de vinculación.
        pantallaVinculacion.style.display = "flex";
        pantallaPrincipal.style.display = "none";

        // Colocamos el cursor en el campo de ingreso del ID.
        deviceIdInput.focus();
    }


    // ============================================================
    // EVENTO: TECLA ENTER
    // ============================================================

    // Permitimos que el usuario pueda vincular la incubadora
    // presionando Enter en lugar de hacer clic en el botón.
    deviceIdInput.addEventListener("keydown", event => {

        // Comprobamos si la tecla presionada fue Enter.
        if (event.key === "Enter") {

            // Ejecutamos la función de vinculación.
            vincularDispositivo();
        }
    });


    // ============================================================
    // EVENTO: VOLVER A LA PESTAÑA
    // ============================================================

    // Detectamos cuando el usuario cambia de pestaña
    // o vuelve a la página de OVOTECH.
    document.addEventListener("visibilitychange", () => {

        // Si la pestaña está oculta o no hay una incubadora seleccionada,
        // no realizamos ninguna operación.
        if (document.hidden || !deviceId) return;

        // Al volver a la página, consultamos la última lectura
        // para actualizar los valores mostrados.
        obtenerUltimaLectura();

        // Comprobamos si el WebSocket está cerrado o no existe.
        if (!ws || ws.readyState === WebSocket.CLOSED) {

            // Si no hay conexión activa, intentamos conectarnos nuevamente.
            conectarWebSocket();
        }
    });

});
