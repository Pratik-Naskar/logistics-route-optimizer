
// Fuel estimation settings
const FUEL_EFFICIENCY = 15; // Assumed mileage in km per litre

const FUEL_PRICES = {
    petrol: 109.89,
    diesel: 100.00
};
const map = L.map('map', {
    zoomControl: false
}).setView([12.9716, 77.5946], 11);

L.control.zoom({ position: 'bottomright' }).addTo(map);

// Premium Dark Map
const darkMap = L.tileLayer(
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }
);

// Satellite Map
const satelliteMap = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    {
        attribution: 'Tiles &copy; Esri',
        maxZoom: 19
    }
);

// Default map
darkMap.addTo(map);

// Map switching
const mapStyles = {
    dark: darkMap,
    satellite: satelliteMap
};

function switchMapStyle(style) {
    Object.values(mapStyles).forEach(layer => {
        if (map.hasLayer(layer)) {
            map.removeLayer(layer);
        }
    });

    mapStyles[style].addTo(map);

    const mapElement = document.getElementById('map');

    if (style === 'dark') {
        mapElement.classList.add('dark-map-mode');
    } else {
        mapElement.classList.remove('dark-map-mode');
    }
}
    
// Map layers
let markersLayer = L.layerGroup().addTo(map);
let routeLayer = L.layerGroup().addTo(map);

// Custom glowing markers
function createMarker(color, label) {
    return L.divIcon({
        className: 'custom-marker',
        html: `<div style="
            width:18px;
            height:18px;
            background:${color};
            border:3px solid white;
            border-radius:50%;
            box-shadow:0 0 12px ${color}, 0 0 25px ${color};
        " title="${label}"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9]
    });
}

function clearMap() {
    markersLayer.clearLayers();
    routeLayer.clearLayers();
}

function updateStats(count, distance = '--', time = '--') {
    document.getElementById('locationCount').textContent = count;
    document.getElementById('distanceStat').textContent = distance;
    document.getElementById('timeStat').textContent = time;
}
// DELIVERY MANAGEMENT

function updateDeliveryTable(deliveries) {
    const tableBody = document.getElementById('deliveryTableBody');
    tableBody.innerHTML = '';

    deliveries.forEach(delivery => {
        const row = document.createElement('tr');

        const stopCell = document.createElement('td');
        stopCell.textContent = delivery.stop_number;

        const locationCell = document.createElement('td');
        locationCell.textContent = delivery.location;

        const statusCell = document.createElement('td');
        const statusBadge = document.createElement('span');

        statusBadge.className = 'delivery-status';

        if (delivery.status === 'Delivered') {
            statusBadge.classList.add('delivered');
        }

        statusBadge.textContent = delivery.status;
        statusCell.appendChild(statusBadge);

        const actionCell = document.createElement('td');
        const actionButton = document.createElement('button');

        actionButton.className = 'delivery-action';
        actionButton.textContent =
            delivery.status === 'Delivered' ? 'Completed' : 'Mark Delivered';

        actionButton.disabled = delivery.status === 'Delivered';

        actionButton.addEventListener('click', async function () {
            try {
                const response = await fetch(
                    `/update-delivery/${delivery.id}`,
                    {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            status: 'Delivered'
                        })
                    }
                );

                if (!response.ok) {
                    alert('Unable to update delivery status.');
                    return;
                }

                loadDeliveries(delivery.route_id);

            } catch (error) {
                console.error(error);
                alert('Could not connect to the database.');
            }
        });

        actionCell.appendChild(actionButton);
        const deleteButton = document.createElement('button');
deleteButton.className = 'delivery-action';
deleteButton.textContent = 'Delete';
deleteButton.style.marginLeft = '8px';
deleteButton.style.background = '#dc2626';

deleteButton.addEventListener('click', async function () {
    if (!confirm('Permanently delete this delivery record?')) return;

    try {
        const response = await fetch(
            `/delete-delivery/${delivery.id}`,
            { method: 'DELETE' }
        );

        if (!response.ok) {
            alert('Unable to delete delivery.');
            return;
        }

        loadDeliveries(delivery.route_id);

    } catch (error) {
        console.error(error);
        alert('Could not connect to the database.');
    }
});

actionCell.appendChild(deleteButton);
        row.appendChild(stopCell);
        row.appendChild(locationCell);
        row.appendChild(statusCell);
        row.appendChild(actionCell);

        tableBody.appendChild(row);
    });
}


// LOAD DELIVERIES FROM DATABASE

async function loadDeliveries(routeId) {
    try {
        const response = await fetch(`/get-deliveries/${routeId}`);

        if (!response.ok) {
            throw new Error('Unable to load deliveries.');
        }

        const deliveries = await response.json();
        updateDeliveryTable(deliveries);

    } catch (error) {
        console.error(error);
    }
}
document.getElementById('optimizeBtn').addEventListener('click', async function () {
    const warehouse = document.getElementById('warehouse').value.trim();
    const stopsText = document.getElementById('stops').value.trim();
    const status = document.getElementById('status');
    const summary = document.getElementById('summary');
    const routeList = document.getElementById('routeList');
    const button = this;

    if (!warehouse || !stopsText) {
        status.textContent = 'Please enter a warehouse and at least one delivery location.';
        return;
    }

    const addresses = [
        warehouse,
        ...stopsText.split('\n').map(x => x.trim()).filter(Boolean)
    ];

    if (addresses.length > 21) {
        status.textContent = 'Maximum limit is 20 delivery stops.';
        return;
    }

    button.disabled = true;
    button.textContent = 'OPTIMIZING ROUTE...';
    status.textContent = 'Finding locations and calculating the best route...';
    summary.textContent = '';
    routeList.innerHTML = '';
    clearMap();

    try {
        // Geocode addresses using Nominatim
        const locations = [];

        for (const address of addresses) {
            const response = await fetch(
                `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(address)}`
            );

            const results = await response.json();

            if (!results.length) {
                throw new Error(`Location not found: ${address}`);
            }

            locations.push({
                lat: Number(results[0].lat),
                lon: Number(results[0].lon),
                name: address
            });
        }

        // Send coordinates to Flask
        const response = await fetch('/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                locations: locations.map(x => ({
                    lat: x.lat,
                    lon: x.lon
                }))
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Route optimization failed.');
        }

        const ordered = data.route.map(index => locations[index]);
        // DISPLAY SELECTED VEHICLE ON MAP
if (vehicleMarker) {
    map.removeLayer(vehicleMarker);
    vehicleMarker = null;
}

if (selectedVehicle) {
    const vehicleIcons = {
        Truck: '🚚',
        Van: '🚐',
        'Mini Truck': '🚛',
        Bike: '🏍️'
    };

    const vehicleSymbol = vehicleIcons[selectedVehicle.type] || '🚚';

    const vehicleIcon = L.divIcon({
        className: 'vehicle-map-icon',
        html: `<div style="
            font-size:30px;
            background:#111827;
            border:2px solid #38bdf8;
            border-radius:12px;
            padding:7px;
            box-shadow:0 0 18px #38bdf8;
        ">${vehicleSymbol}</div>`,
        iconSize: [48, 48],
        iconAnchor: [24, 24]
    });

    vehicleMarker = L.marker(
        [ordered[0].lat, ordered[0].lon],
        { icon: vehicleIcon }
    )
    .bindPopup(
        `<b>Selected Vehicle</b><br>
        ${selectedVehicle.number}<br>
        ${selectedVehicle.type}`
    )
    .addTo(map);
}

        // Add glowing markers
        ordered.forEach((point, index) => {
            const isWarehouse = index === 0;

            L.marker([point.lat, point.lon], {
                icon: createMarker(
                    isWarehouse ? '#ff8738' : '#21c8e8',
                    point.name
                )
            })
            .bindPopup(
                `<b>${isWarehouse ? 'Warehouse' : 'Stop ' + index}</b><br>${point.name}`
            )
            .addTo(markersLayer);

            const item = document.createElement('li');
            item.textContent = (isWarehouse ? 'Warehouse: ' : 'Stop ' + index + ': ') + point.name;
            routeList.appendChild(item);
        });

        // Get actual road route from OSRM
        const coordinates = ordered
            .map(point => `${point.lon},${point.lat}`)
            .join(';');

        const roadResponse = await fetch(
            `https://router.project-osrm.org/route/v1/driving/${coordinates}?overview=full&geometries=geojson`
        );

        const roadData = await roadResponse.json();

        if (roadData.code !== 'Ok' || !roadData.routes.length) {
            throw new Error('Road route could not be calculated for these locations.');
        }

        const road = roadData.routes[0];
        const roadCoordinates = road.geometry.coordinates.map(
            point => [point[1], point[0]]
        );

        // Outer glow
        L.polyline(roadCoordinates, {
            color: '#ff8738',
            weight: 12,
            opacity: 0.20
        }).addTo(routeLayer);

        // Main glowing route
        L.polyline(roadCoordinates, {
            color: '#ff8738',
            weight: 4,
            opacity: 1
        }).addTo(routeLayer);

        // Fit map around route
        const bounds = L.latLngBounds(roadCoordinates);
        map.fitBounds(bounds, { padding: [45, 45] });

        const distance = (road.distance / 1000).toFixed(2);
        // Calculate fuel consumption and estimated cost
const fuelType = document.getElementById('fuelType').value;
const fuelPrice = FUEL_PRICES[fuelType];

const distanceKm = Number(distance);
const fuelUsed = distanceKm / FUEL_EFFICIENCY;
const fuelCost = fuelUsed * fuelPrice;


document.getElementById('fuelStat').textContent =
    `${fuelUsed.toFixed(2)} L`;

document.getElementById('fuelCostStat').textContent =
    `₹ ${fuelCost.toFixed(2)}`;
        const duration = Math.round(road.duration / 60);
        const time = duration >= 60
            ? `${Math.floor(duration / 60)}h ${duration % 60}m`
            : `${duration} min`;
// SAVE ROUTE AND DELIVERY STOPS TO SQLITE DATABASE

try {
    const routeResponse = await fetch('/save-route', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            warehouse: locations[0].name,
            stops: ordered.length - 1,
            distance: distance,
            time: time,
            fuelUsed: fuelUsed.toFixed(2),
            fuelCost: fuelCost.toFixed(2)
        })
    });

    const routeResult = await routeResponse.json();

    if (!routeResponse.ok || !routeResult.success) {
        throw new Error('Unable to save route to database.');
    }

    const routeId = routeResult.route_id;

    // SAVE EACH DELIVERY STOP

    for (let i = 1; i < ordered.length; i++) {
        const deliveryResponse = await fetch('/save-delivery', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                route_id: routeId,
                stop_number: i,
                location: ordered[i].name
            })
        });

        if (!deliveryResponse.ok) {
            throw new Error('Unable to save delivery stops.');
        }
    }

    // UPDATE ROUTE HISTORY

    routeHistory.unshift({
        id: routeId,
        warehouse: locations[0].name,
        stops: ordered.length - 1,
        distance: distance,
        time: time,
        fuelUsed: fuelUsed.toFixed(2),
        fuelCost: fuelCost.toFixed(2)
    });

    displayRouteHistory();
    updateAnalyticsCharts();

    // LOAD SAVED DELIVERY STOPS

    await loadDeliveries(routeId);

} catch (error) {
    console.error('Database error:', error);
    alert(error.message);
}
        updateStats(ordered.length, `${distance} km`, time);

        document.getElementById('routeStatus').textContent = 'OPTIMIZED';
        summary.textContent =
            `Total distance: ${distance} km | Estimated driving time: ${time}`;

        status.textContent = 'Route successfully optimized!';
    }
    catch (error) {
        status.textContent = error.message;
        document.getElementById('routeStatus').textContent = 'ERROR';
        updateStats(0);
    }
    finally {
        button.disabled = false;
        button.textContent = '✦  OPTIMIZE DELIVERY ROUTE';
    }
});
// =================================
// FLEET MANAGEMENT
// =================================

// =================================
// ROUTE HISTORY
// =================================

let fleetVehicles = [];
let selectedVehicle = null;
let vehicleMarker = null;
let routeHistory = [];


function displayRouteHistory() {
    const tableBody = document.getElementById('historyTableBody');
    tableBody.innerHTML = '';

    routeHistory.forEach((route, index) => {
        const row = document.createElement('tr');

        const values = [
            index + 1,
            route.warehouse,
            route.stops,
            route.distance + ' km',
            route.time,
            route.fuelUsed + ' L',
            '₹ ' + route.fuelCost
        ];

        values.forEach(value => {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        });

        // ACTION CELL
        const actionCell = document.createElement('td');

        const deleteButton = document.createElement('button');
        deleteButton.textContent = 'Delete';
        deleteButton.className = 'delete-btn';

        deleteButton.addEventListener('click', async function () {
            if (!confirm('Are you sure you want to delete this route?')) {
                return;
            }

            if (!route.id) {
                alert('Route ID is missing. Please refresh the page and try again.');
                return;
            }

            try {
                const response = await fetch(`/delete-route/${route.id}`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    throw new Error('Failed to delete route');
                }

                routeHistory = routeHistory.filter(
                    item => item.id !== route.id
                );

                displayRouteHistory();
                updateAnalytics();

                alert('Route deleted successfully!');
            } catch (error) {
                console.error(error);
                alert('Unable to delete route. Please try again.');
            }
        });

        actionCell.appendChild(deleteButton);
        row.appendChild(actionCell);

        tableBody.appendChild(row);
    });
}



// =================================
// FLEET MANAGEMENT
// =================================

document.getElementById('addVehicleBtn').addEventListener('click', async function () {

    const number = document.getElementById('vehicleNumber').value.trim().toUpperCase();
    const type = document.getElementById('vehicleType').value;
    const fuel = document.getElementById('vehicleFuel').value;
    const mileage = document.getElementById('vehicleMileage').value;

    if (!number || !type || !fuel || !mileage) {
        alert('Please fill in all vehicle details.');
        return;
    }

    if (Number(mileage) <= 0) {
        alert('Please enter a valid mileage.');
        return;
    }

    try {
        const response = await fetch('/add-vehicle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                number: number,
                type: type,
                fuel: fuel,
                mileage: mileage
            })
        });

        const result = await response.json();

        if (!response.ok) {
            alert(result.error || 'Unable to add vehicle.');
            return;
        }

        document.getElementById('vehicleNumber').value = '';
        document.getElementById('vehicleType').value = '';
        document.getElementById('vehicleFuel').value = '';
        document.getElementById('vehicleMileage').value = '';

        loadFleetVehicles();

        alert('Vehicle added successfully!');

    } catch (error) {
        console.error(error);
        alert('Could not connect to the database.');
    }
});


// LOAD VEHICLES FROM DATABASE
async function loadFleetVehicles() {

    try {
        const response = await fetch('/get-vehicles');
        fleetVehicles = await response.json();
        displayFleetVehicles();

    } catch (error) {
        console.error('Unable to load vehicles:', error);
    }
}


// DISPLAY VEHICLES
function displayFleetVehicles() {

    const tableBody = document.getElementById('fleetTableBody');
    tableBody.innerHTML = '';

    fleetVehicles.forEach(vehicle => {

        const row = document.createElement('tr');

        const values = [
            vehicle.number,
            vehicle.type,
            vehicle.fuel,
            vehicle.mileage + ' km/L',
            vehicle.availability
        ];

        values.forEach(value => {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        });

        const actionCell = document.createElement('td');
        actionCell.style.display = 'flex';
        actionCell.style.alignItems = 'center';
        actionCell.style.gap = '10px';
        actionCell.style.flexWrap = 'wrap';
        const selectButton = document.createElement('button');
selectButton.className = 'delivery-action';
selectButton.textContent = 'Select';

selectButton.addEventListener('click', function () {
    selectedVehicle = vehicle;
    alert(vehicle.number + ' selected successfully!');
});

        const removeButton = document.createElement('button');
        removeButton.className = 'delivery-action';
        removeButton.textContent = 'Remove';

        removeButton.addEventListener('click', async function () {

            if (!confirm('Are you sure you want to remove this vehicle?')) {
                return;
            }

            try {
                const response = await fetch(
                    `/delete-vehicle/${vehicle.id}`,
                    { method: 'DELETE' }
                );

                if (!response.ok) {
                    alert('Unable to remove vehicle.');
                    return;
                }

                loadFleetVehicles();

            } catch (error) {
                console.error(error);
                alert('Could not connect to the database.');
            }
        });

        actionCell.appendChild(removeButton);
        actionCell.appendChild(selectButton);
        row.appendChild(actionCell);
        tableBody.appendChild(row);
    });
}


// LOAD VEHICLES WHEN PAGE OPENS
loadFleetVehicles();
// =================================
// ADVANCED ANALYTICS
// =================================

let distanceChart;
let fuelChart;

function updateAnalyticsCharts() {

    const labels = routeHistory.map(
        (route, index) => `Route ${routeHistory.length - index}`
    );

    const distances = routeHistory.map(
        route => Number(route.distance)
    );

    const fuelCosts = routeHistory.map(
        route => Number(route.fuelCost)
    );

    // ROUTE DISTANCE CHART
    if (distanceChart) {
        distanceChart.destroy();
    }

    distanceChart = new Chart(
        document.getElementById('distanceChart'),
        {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Distance (km)',
                    data: distances,
                    backgroundColor: '#f97316',
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: { color: '#ffffff' }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#ffffff' },
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#ffffff' },
                        grid: {
                            color: 'rgba(255,255,255,0.08)'
                        }
                    }
                }
            }
        }
    );

    // FUEL COST CHART
    if (fuelChart) {
        fuelChart.destroy();
    }

    fuelChart = new Chart(
        document.getElementById('fuelChart'),
        {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Fuel Cost (₹)',
                    data: fuelCosts,
                    backgroundColor: '#22c55e',
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: { color: '#ffffff' }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#ffffff' },
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#ffffff' },
                        grid: {
                            color: 'rgba(255,255,255,0.08)'
                        }
                    }
                }
            }
        }
    );
}
// LOAD SAVED ROUTES FROM DATABASE
fetch('/get-route-history')
    .then(response => response.json())
    .then(data => {
        routeHistory = data.map(route => ({
    id: route.id,
    warehouse: route.warehouse,
            stops: route.stops,
            distance: route.distance,
            time: route.time,
            fuelUsed: route.fuelUsed,
            fuelCost: route.fuelCost
        }));

        displayRouteHistory();
        updateAnalyticsCharts();
        if (data.length > 0) {
    loadDeliveries(data[0].id);
}
    })
    .catch(error => {
        console.error('Unable to load route history:', error);
    });
