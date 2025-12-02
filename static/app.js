const map = L.map('map').setView([50.4501, 30.5234], 11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

let depotMarker = null;
let orderMarkers = {};
let routeLayers = [];

map.on('click', (e) => {
    document.getElementById('depot-lat').value = e.latlng.lat;
    document.getElementById('depot-lon').value = e.latlng.lng;
});

async function updateHealth() {
    const res = await fetch('/api/health');
    const data = await res.json();
    const el = document.getElementById('health');
    el.textContent = data.graph_loaded ? 'Граф Киева загружен' : 'Граф не загружен';
}

async function loadDepot() {
    const res = await fetch('/api/depot');
    const data = await res.json();
    if (!data) return;
    setDepotMarker([data.latitude, data.longitude]);
    document.getElementById('depot-lat').value = data.latitude;
    document.getElementById('depot-lon').value = data.longitude;
    document.getElementById('depot-address').value = data.address || '';
}

function setDepotMarker(coords) {
    if (depotMarker) depotMarker.remove();
    depotMarker = L.marker(coords, { draggable: true, icon: L.icon({
        iconUrl: 'https://cdn-icons-png.flaticon.com/512/684/684908.png',
        iconSize: [32, 32],
    })}).addTo(map).bindPopup('Депо');
    depotMarker.on('dragend', (e) => {
        const { lat, lng } = e.target.getLatLng();
        document.getElementById('depot-lat').value = lat;
        document.getElementById('depot-lon').value = lng;
    });
}

async function saveDepot() {
    const lat = parseFloat(document.getElementById('depot-lat').value);
    const lon = parseFloat(document.getElementById('depot-lon').value);
    const address = document.getElementById('depot-address').value;
    const res = await fetch('/api/depot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: lat, longitude: lon, address })
    });
    const data = await res.json();
    if (!data.error) {
        setDepotMarker([data.latitude, data.longitude]);
    }
}

async function addVehicle() {
    const name = document.getElementById('veh-name').value;
    const capacity = parseFloat(document.getElementById('veh-capacity').value);
    await fetch('/api/vehicles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, capacity })
    });
    document.getElementById('veh-name').value = '';
    document.getElementById('veh-capacity').value = '';
    loadVehicles();
}

async function loadVehicles() {
    const res = await fetch('/api/vehicles');
    const data = await res.json();
    const container = document.getElementById('vehicle-list');
    container.innerHTML = '';
    data.forEach(v => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<div><strong>${v.name}</strong> · ${v.capacity} м³</div>
        <label class="checkbox"><input type="checkbox" data-vehicle="${v.id}" ${v.active ? 'checked' : ''}> Готов</label>`;
        container.appendChild(card);
    });
}

async function addOrder() {
    const payload = {
        external_id: document.getElementById('order-id').value,
        address: document.getElementById('order-address').value,
        latitude: document.getElementById('order-lat').value || null,
        longitude: document.getElementById('order-lon').value || null,
        volume: parseFloat(document.getElementById('order-volume').value || '0'),
        window_start: document.getElementById('order-window-start').value || null,
        window_end: document.getElementById('order-window-end').value || null,
    };
    await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    clearOrderForm();
    loadOrders();
}

function clearOrderForm() {
    ['order-id','order-address','order-lat','order-lon','order-volume','order-window-start','order-window-end']
        .forEach(id => document.getElementById(id).value = '');
}

async function loadOrders() {
    const res = await fetch('/api/orders');
    const data = await res.json();
    const container = document.getElementById('order-list');
    container.innerHTML = '';
    Object.values(orderMarkers).forEach(m => m.remove());
    orderMarkers = {};
    data.forEach(o => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<div><strong>${o.external_id}</strong> · ${o.volume} м³</div>
        <div class="muted">${o.address || ''}</div>
        <div class="order-actions">
            <button data-del="${o.id}">Удалить</button>
        </div>`;
        container.appendChild(card);
        const marker = L.marker([o.latitude, o.longitude]).addTo(map).bindPopup(`Заказ ${o.external_id}`);
        orderMarkers[o.id] = marker;
    });
    container.querySelectorAll('button[data-del]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.getAttribute('data-del');
            await fetch(`/api/orders/${id}`, { method: 'DELETE' });
            loadOrders();
        });
    });
}

async function importFile() {
    const input = document.getElementById('file-input');
    if (!input.files.length) return;
    const form = new FormData();
    form.append('file', input.files[0]);
    await fetch('/api/orders/import', { method: 'POST', body: form });
    input.value = '';
    loadOrders();
}

function readActiveVehicles() {
    const boxes = document.querySelectorAll('input[data-vehicle]');
    return Array.from(boxes).filter(b => b.checked).map(b => parseInt(b.getAttribute('data-vehicle')));
}

async function solve() {
    const forceAll = document.getElementById('force-all').checked;
    const vehicles = readActiveVehicles();
    const res = await fetch('/api/solve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force_all: forceAll, vehicles })
    });
    const data = await res.json();
    if (data.error) {
        alert(data.error);
        return;
    }
    drawRoutes(data.routes);
}

function drawRoutes(routes) {
    routeLayers.forEach(layer => layer.remove());
    routeLayers = [];
    const container = document.getElementById('routes');
    container.innerHTML = '';
    const colors = ['#10b981','#3b82f6','#f59e0b','#ef4444','#8b5cf6'];
    routes.forEach((route, idx) => {
        const color = colors[idx % colors.length];
        const group = L.layerGroup();
        route.geometry.forEach(segment => {
            const polyline = L.polyline(segment, { color, weight: 5, opacity: 0.8 });
            polyline.addTo(group);
        });
        group.addTo(map);
        routeLayers.push(group);
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<div class="route-label">${route.vehicle.name}</div>
        <div>${route.distance_km.toFixed(2)} км · ${route.travel_time_min.toFixed(1)} мин</div>
        <div>Остановки: ${route.stops.join(', ')}</div>`;
        container.appendChild(card);
    });
}

document.getElementById('save-depot').addEventListener('click', saveDepot);
document.getElementById('add-vehicle').addEventListener('click', addVehicle);
document.getElementById('add-order').addEventListener('click', addOrder);
document.getElementById('import-file').addEventListener('click', importFile);
document.getElementById('run-solve').addEventListener('click', solve);

updateHealth();
loadDepot();
loadVehicles();
loadOrders();
