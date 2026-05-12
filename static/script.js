// ============================================
// CONFIGURACIÓN PARA PRODUCCIÓN
// ============================================
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

// URL del backend en Render
const RENDER_URL = 'https://ovotech.onrender.com/';  // ← TU URL DE RENDER

const API_BASE = isLocal ? 'http://localhost:8000' : RENDER_URL;
const WS_URL = isLocal ? 'ws://localhost:8000/ws' : 'wss://ovotech.onrender.com/ws';
const connectionEl = document.getElementById('connection');
const tempValueEl  = document.getElementById('tempValue');
const tempStatusEl = document.getElementById('tempStatus');
const humValueEl   = document.getElementById('humValue');
const humStatusEl  = document.getElementById('humStatus');
const tempBar      = document.querySelector('.temp-bar');
const humBar       = document.querySelector('.hum-bar');

const MAX_POINTS = 50;
let tempChart, humChart;
let ws = null;
let conectadoWS = false;

// ========== UTILIDADES DE ESTADO ==========
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

// ========== GRÁFICOS ==========
function initCharts() {
    const commonOptions = {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 750, easing: 'easeOutQuart' },
        plugins: {
            legend: { display: false },
            tooltip: { backgroundColor: 'rgba(0,0,0,0.8)', titleColor: '#fff', bodyColor: '#fff', cornerRadius: 8, displayColors: false }
        },
        scales: { x: { display: false }, y: { beginAtZero: false } }
    };
    
    tempChart = new Chart(document.getElementById('tempChart').getContext('2d'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Temp', data: [], borderColor: '#4e54c8', backgroundColor: 'rgba(78,84,200,0.1)', borderWidth: 3, tension: 0.4, fill: true, pointRadius: 0 }] },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { min: 30, max: 45 } } }
    });
    
    humChart = new Chart(document.getElementById('humChart').getContext('2d'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Hum', data: [], borderColor: '#8f94fb', backgroundColor: 'rgba(143,148,251,0.1)', borderWidth: 3, tension: 0.4, fill: true, pointRadius: 0 }] },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { min: 0, max: 100 } } }
    });
}

function pushChartData(temp, hum, timestamp) {
    const lbl = new Date(timestamp).toLocaleTimeString('es-ES', { hour12: false });
    
    if (tempChart.data.labels.length >= MAX_POINTS) {
        tempChart.data.labels.shift(); tempChart.data.datasets[0].data.shift();
    }
    tempChart.data.labels.push(lbl);
    tempChart.data.datasets[0].data.push(temp);
    tempChart.update('none');

    if (humChart.data.labels.length >= MAX_POINTS) {
        humChart.data.labels.shift(); humChart.data.datasets[0].data.shift();
    }
    humChart.data.labels.push(lbl);
    humChart.data.datasets[0].data.push(hum);
    humChart.update('none');
}

// ========== ACTUALIZAR UI ==========
function updateUI(data) {
    const t = parseFloat(data.temperatura);
    const h = parseFloat(data.humedad);
    
    tempValueEl.innerText = t.toFixed(1) + '°C';
    const st = getTempStatus(t);
    tempStatusEl.innerText = st.text;
    tempStatusEl.style.color = st.color;
    if (tempBar) { tempBar.style.width = Math.min(Math.max((t/45)*100, 0), 100) + '%'; tempBar.style.backgroundColor = st.barColor; }

    humValueEl.innerText = h.toFixed(1) + '%';
    const sh = getHumStatus(h);
    humStatusEl.innerText = sh.text;
    humStatusEl.style.color = sh.color;
    if (humBar) { humBar.style.width = Math.min(Math.max(h, 0), 100) + '%'; humBar.style.backgroundColor = sh.barColor; }

    pushChartData(t, h, data.timestamp || new Date().toISOString());
}

// ========== CARGA INICIAL POR HTTP ==========
async function cargarHistorico() {
    try {
        const res = await fetch(`${API_BASE}/api/lecturas?limit=${MAX_POINTS}`);
        if (!res.ok) {
            console.warn("API no responde (_status:", res.status, ")");
            return;
        }
        const json = await res.json();
        if (!json.data || json.data.length === 0) return;

        // Limpiar
        tempChart.data.labels = []; tempChart.data.datasets[0].data = [];
        humChart.data.labels = []; humChart.data.datasets[0].data = [];

        json.data.forEach(l => {
            tempChart.data.labels.push(new Date(l.timestamp).toLocaleTimeString('es-ES', { hour12: false }));
            tempChart.data.datasets[0].data.push(parseFloat(l.temperatura));
            humChart.data.labels.push(new Date(l.timestamp).toLocaleTimeString('es-ES', { hour12: false }));
            humChart.data.datasets[0].data.push(parseFloat(l.humedad));
        });
        tempChart.update(); humChart.update();
        updateUI(json.data[json.data.length - 1]);

    } catch (e) {
        console.error("Error cargando histórico:", e);
    }
}

// ========== WEBSOCKET ROBUSTO ==========
function connectWebSocket() {
    if (ws) { try { ws.close(); } catch(e) {} }

    console.log("🔌 Intentando WS en", WS_URL);
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log("✅ WebSocket conectado");
        conectadoWS = true;
        connectionEl.innerHTML = '<span class="status-dot active"></span><span>Sistema Conectado</span>';
        connectionEl.classList.remove('alert');
    };

    ws.onmessage = (event) => {
        // Protección: si no es string, ignorar
        if (typeof event.data !== 'string') return;
        
        // Si es "pong", ignorar
        if (event.data === "pong") return;

        try {
            const msg = JSON.parse(event.data);
            
            // Mensaje individual en tiempo real
            if (msg.type === 'lectura' && msg.data) {
                updateUI(msg.data);
            }
            
            // Histórico enviado al conectar
            else if (msg.type === 'historico' && Array.isArray(msg.data)) {
                if (msg.data.length === 0) return;
                tempChart.data.labels = []; tempChart.data.datasets[0].data = [];
                humChart.data.labels = []; humChart.data.datasets[0].data = [];
                msg.data.forEach(l => {
                    tempChart.data.labels.push(new Date(l.timestamp).toLocaleTimeString('es-ES', { hour12: false }));
                    tempChart.data.datasets[0].data.push(parseFloat(l.temperatura));
                    humChart.data.labels.push(new Date(l.timestamp).toLocaleTimeString('es-ES', { hour12: false }));
                    humChart.data.datasets[0].data.push(parseFloat(l.humedad));
                });
                tempChart.update(); humChart.update();
                updateUI(msg.data[msg.data.length - 1]);
            }
            
        } catch (e) {
            // Ignoramos silenciosamente los mensajes que no sean JSON válido
            console.warn("WS mensaje no-JSON recibido (ignorado):", event.data.substring(0, 50));
        }
    };

    ws.onerror = (err) => {
        console.error("❌ WS Error:", err);
        conectadoWS = false;
        connectionEl.innerHTML = '<span class="status-dot"></span><span>Error de Conexión</span>';
        connectionEl.classList.add('alert');
    };

    ws.onclose = () => {
        console.warn("🔌 WS cerrado. Reintentando en 3s...");
        conectadoWS = false;
        connectionEl.innerHTML = '<span class="status-dot"></span><span>Desconectado</span>';
        connectionEl.classList.add('alert');
        setTimeout(connectWebSocket, 3000);
    };
}
// Detecta si estás en local o en Render
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

const API_BASE = isLocal 
    ? 'http://localhost:8000' 
    : window.location.origin;  // En Render, usa el mismo dominio

const WS_URL = isLocal 
    ? 'ws://localhost:8000/ws' 
    : 'wss://' + window.location.host + '/ws';  // wss:// en producción HTTPS

// ... resto de tu script.js igual ...
// ========== INICIO ==========
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    cargarHistorico();
    connectWebSocket();
});