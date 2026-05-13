// ============================================
// CONFIGURACIÓN - Render / Local
// ============================================
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const RENDER_URL = 'https://ovotech.onrender.com';

const API_BASE = isLocal ? 'http://localhost:8000' : RENDER_URL;
const WS_URL   = isLocal ? 'ws://localhost:8000/ws' : 'wss://ovotech.onrender.com/ws';

// ============================================
// ESTADO GLOBAL
// ============================================
let MI_DEVICE_ID = localStorage.getItem('ovotech_device_id');
let tempChart = null;
let humChart  = null;
let ws = null;
const MAX_POINTS = 50;

// ============================================
// REFERENCIAS DOM
// ============================================
const pantallaVinculacion = document.getElementById('pantalla-vinculacion');
const pantallaPrincipal   = document.getElementById('pantalla-principal');
const deviceIdInput       = document.getElementById('deviceIdInput');
const vinculacionMsg      = document.getElementById('vinculacionMsg');
const connectionEl        = document.getElementById('connection');
const tempValueEl         = document.getElementById('tempValue');
const tempStatusEl        = document.getElementById('tempStatus');
const humValueEl          = document.getElementById('humValue');
const humStatusEl         = document.getElementById('humStatus');
const tempBar             = document.querySelector('.temp-bar');
const humBar              = document.querySelector('.hum-bar');

// ============================================
// UTILIDADES - Estados de temperatura/humedad
// ============================================
function getTempStatus(temp) {
    if (temp < 36.0 || temp > 39.5) return { text: '¡Peligro!', color: '#e74c3c', barColor: '#e74c3c' };
    if ((temp >= 36.0 && temp < 37.0) || (temp > 38.5 && temp <= 39.5)) return { text: 'Advertencia', color: '#f39c12', barColor: '#f39c12' };
    return { text: 'Óptimo', color: '#27ae60', barColor: '#4e54c8' };
}

function getHumStatus(hum) {
    if (hum < 40.0 || hum > 80.0) return { text: '¡Peligro!', color: '#e74c3c', barColor: '#e74c3c' };
    if ((hum >= 40.0 && hum < 50.0) || (hum > 70.0 && hum <= 80.0)) return { text: 'Advertencia', color: '#f39c12', barColor: '#f39c12' };
    return { text: 'Óptimo', color: '#27ae60', barColor: '#8f94fb' };
}

// ============================================
// GRÁFICOS CHART.JS
// ============================================
function initCharts() {
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 750, easing: 'easeOutQuart' },
        plugins: {
            legend: { display: false },
            tooltip: { backgroundColor: 'rgba(0,0,0,0.8)', titleColor: '#fff', bodyColor: '#fff', cornerRadius: 8, displayColors: false }
        },
        scales: { x: { display: false }, y: { beginAtZero: false } }
    };

    const ctxTemp = document.getElementById('tempChart');
    const ctxHum  = document.getElementById('humChart');

    if (!ctxTemp || !ctxHum) {
        console.error("❌ No se encontraron los canvas de los gráficos");
        return;
    }

    tempChart = new Chart(ctxTemp.getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Temp', data: [],
                borderColor: '#4e54c8', backgroundColor: 'rgba(78,84,200,0.1)',
                borderWidth: 3, tension: 0.4, fill: true, pointRadius: 0
            }]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { min: 30, max: 45 } } }
    });

    humChart = new Chart(ctxHum.getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Hum', data: [],
                borderColor: '#8f94fb', backgroundColor: 'rgba(143,148,251,0.1)',
                borderWidth: 3, tension: 0.4, fill: true, pointRadius: 0
            }]
        },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { min: 0, max: 100 } } }
    });
}

function pushChartData(temp, hum, timestamp) {
    const lbl = new Date(timestamp).toLocaleTimeString('es-ES', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

    if (tempChart.data.labels.length >= MAX_POINTS) {
        tempChart.data.labels.shift();
        tempChart.data.datasets[0].data.shift();
    }
    tempChart.data.labels.push(lbl);
    tempChart.data.datasets[0].data.push(temp);
    tempChart.update('none');

    if (humChart.data.labels.length >= MAX_POINTS) {
        humChart.data.labels.shift();
        humChart.data.datasets[0].data.shift();
    }
    humChart.data.labels.push(lbl);
    humChart.data.datasets[0].data.push(hum);
    humChart.update('none');
}

// ============================================
// ACTUALIZAR UI
// ============================================
function updateUI(data) {
    const t = parseFloat(data.temperatura);
    const h = parseFloat(data.humedad);

    tempValueEl.innerText = t.toFixed(1) + '°C';
    const st = getTempStatus(t);
    tempStatusEl.innerText = st.text;
    tempStatusEl.style.color = st.color;
    if (tempBar) { tempBar.style.width = Math.min(Math.max((t / 45) * 100, 0), 100) + '%'; tempBar.style.backgroundColor = st.barColor; }

    humValueEl.innerText = h.toFixed(1) + '%';
    const sh = getHumStatus(h);
    humStatusEl.innerText = sh.text;
    humStatusEl.style.color = sh.color;
    if (humBar) { humBar.style.width = Math.min(Math.max(h, 0), 100) + '%'; humBar.style.backgroundColor = sh.barColor; }

    pushChartData(t, h, data.timestamp || new Date().toISOString());
}

// ============================================
// CARGAR HISTÓRICO POR HTTP (filtrado por device_id)
// ============================================
async function cargarHistorico() {
    if (!MI_DEVICE_ID) return;

    try {
        const res = await fetch(`${API_BASE}/api/lecturas/${MI_DEVICE_ID}?limit=${MAX_POINTS}`);
        if (!res.ok) {
            console.warn("API no responde (status:", res.status, ")");
            return;
        }
        const json = await res.json();
        if (!json.data || json.data.length === 0) {
            console.log("ℹ️ Sin histórico para este dispositivo");
            return;
        }

        // Limpiar gráficos
        tempChart.data.labels = []; tempChart.data.datasets[0].data = [];
        humChart.data.labels = []; humChart.data.datasets[0].data = [];

        json.data.forEach(l => {
            const lbl = new Date(l.timestamp).toLocaleTimeString('es-ES', { hour12: false });
            tempChart.data.labels.push(lbl);
            tempChart.data.datasets[0].data.push(parseFloat(l.temperatura));
            humChart.data.labels.push(lbl);
            humChart.data.datasets[0].data.push(parseFloat(l.humedad));
        });

        tempChart.update();
        humChart.update();
        updateUI(json.data[json.data.length - 1]);

    } catch (e) {
        console.error("Error cargando histórico:", e);
    }
}

// ============================================
// WEBSOCKET - Conexión y filtrado por device_id
// ============================================
function connectWebSocket() {
    if (ws) { try { ws.close(); } catch (e) {} }

    console.log("🔌 Intentando WS en", WS_URL);
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log("✅ WebSocket conectado");
        connectionEl.innerHTML = '<span class="status-dot active"></span><span>Sistema Conectado</span>';
        connectionEl.classList.remove('alert');
    };

    ws.onmessage = (event) => {
        if (typeof event.data !== 'string') return;
        if (event.data === "pong") return;

        try {
            const msg = JSON.parse(event.data);

            // FILTRAR: solo procesar si es de MI incubadora
            if (msg.type === 'lectura' && msg.data) {
                if (msg.data.device_id !== MI_DEVICE_ID) return; // Ignorar otras incubadoras
                updateUI(msg.data);
            }
            else if (msg.type === 'historico' && Array.isArray(msg.data)) {
                // Filtrar el histórico por si acaso
                const filtrado = msg.data.filter(l => l.device_id === MI_DEVICE_ID);
                if (filtrado.length === 0) return;

                tempChart.data.labels = []; tempChart.data.datasets[0].data = [];
                humChart.data.labels = []; humChart.data.datasets[0].data = [];

                filtrado.forEach(l => {
                    const lbl = new Date(l.timestamp).toLocaleTimeString('es-ES', { hour12: false });
                    tempChart.data.labels.push(lbl);
                    tempChart.data.datasets[0].data.push(parseFloat(l.temperatura));
                    humChart.data.labels.push(lbl);
                    humChart.data.datasets[0].data.push(parseFloat(l.humedad));
                });

                tempChart.update(); humChart.update();
                updateUI(filtrado[filtrado.length - 1]);
            }

        } catch (e) {
            console.warn("WS mensaje no-JSON (ignorado):", event.data.substring(0, 50));
        }
    };

    ws.onerror = (err) => {
        console.error("❌ WS Error:", err);
        connectionEl.innerHTML = '<span class="status-dot"></span><span>Error de Conexión</span>';
        connectionEl.classList.add('alert');
    };

    ws.onclose = () => {
        console.warn("🔌 WS cerrado. Reintentando en 3s...");
        connectionEl.innerHTML = '<span class="status-dot"></span><span>Desconectado</span>';
        connectionEl.classList.add('alert');
        setTimeout(connectWebSocket, 3000);
    };
}

// ============================================
// VINCULACIÓN DE DISPOSITIVO
// ============================================
async function vincularDispositivo() {
    const deviceId = deviceIdInput.value.trim().toLowerCase();
    if (!deviceId) {
        vinculacionMsg.innerHTML = '<span style="color:#e74c3c;">❌ Ingresa un ID</span>';
        return;
    }

    vinculacionMsg.innerHTML = '<span style="color:#f39c12;">⏳ Vinculando...</span>';

    try {
        const res = await fetch(`${API_BASE}/api/vincular`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: deviceId, nombre_usuario: null })
        });

        if (res.ok) {
            localStorage.setItem('ovotech_device_id', deviceId);
            vinculacionMsg.innerHTML = '<span style="color:#2ecc71;">✅ ¡Vinculado! Entrando...</span>';
            setTimeout(() => location.reload(), 800);
            return;
        }

        // Si no es ok, intentar leer el error
        let errorText = '';
        try {
            const errData = await res.json();
            console.error("Error del servidor:", errData);
            
            // FastAPI devuelve {detail: "mensaje"} o {detail: [{msg: "..."}]}
            if (errData.detail) {
                if (Array.isArray(errData.detail)) {
                    errorText = errData.detail.map(e => e.msg || JSON.stringify(e)).join(', ');
                } else {
                    errorText = String(errData.detail);
                }
            } else {
                errorText = JSON.stringify(errData);
            }
        } catch {
            errorText = `HTTP ${res.status}: ${res.statusText}`;
        }

        vinculacionMsg.innerHTML = `<span style="color:#e74c3c;">❌ Error: ${errorText}</span>`;

    } catch (e) {
        console.error(e);
        vinculacionMsg.innerHTML = '<span style="color:#e74c3c;">❌ No se pudo conectar al servidor. ¿Está corriendo el backend?</span>';
    }
}

function desvincularDispositivo() {
    if (!confirm('¿Seguro que querés cambiar de incubadora?')) return;
    localStorage.removeItem('ovotech_device_id');
    location.reload();
}

// ============================================
// INICIAR DASHBOARD
// ============================================
function iniciarDashboard() {
    console.log("🚀 Dashboard iniciado para:", MI_DEVICE_ID);
    
    // Mostrar ID en algún lugar (opcional, si tenés un elemento con id="miDeviceId")
    const miDeviceEl = document.getElementById('miDeviceId');
    if (miDeviceEl) miDeviceEl.innerText = MI_DEVICE_ID;

    initCharts();
    cargarHistorico();
    connectWebSocket();
}

// ============================================
// INICIO - Decidir qué pantalla mostrar
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    if (!pantallaVinculacion || !pantallaPrincipal) {
        console.error("❌ Faltan elementos pantalla-vinculacion o pantalla-principal en el HTML");
        return;
    }

    if (MI_DEVICE_ID) {
        // Ya vinculado: mostrar dashboard
        pantallaVinculacion.style.display = 'none';
        pantallaPrincipal.style.display = 'block';
        iniciarDashboard();
    } else {
        // Sin vincular: mostrar formulario
        pantallaVinculacion.style.display = 'block';
        pantallaPrincipal.style.display = 'none';
        deviceIdInput.focus();
    }
});