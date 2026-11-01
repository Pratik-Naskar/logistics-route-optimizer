
from flask import Flask, render_template, request, jsonify
import math
import sqlite3
from database import (
    save_route,
    get_route_history,
    create_database,
    save_vehicle,
    get_vehicles,
    delete_vehicle,
    save_delivery,
    get_deliveries,
    update_delivery_status,
    delete_delivery,
    delete_route
)

# Create Flask application
app = Flask(__name__)
# Initialize LRO database
create_database()


# Calculate distance between two geographical locations
def calculate_distance(point1, point2):

    lat1, lon1 = point1
    lat2, lon2 = point2

    earth_radius = 6371

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    difference_lat = math.radians(lat2 - lat1)
    difference_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(difference_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(difference_lon / 2) ** 2
    )

    distance = 2 * earth_radius * math.asin(
        min(1, math.sqrt(a))
    )

    return distance


# Nearest Neighbor Route Optimization Algorithm
def optimize_route(locations):

    remaining = list(range(1, len(locations)))

    route = [0]

    current = 0

    while remaining:

        nearest = min(
            remaining,
            key=lambda index: calculate_distance(
                locations[current],
                locations[index]
            )
        )

        route.append(nearest)

        remaining.remove(nearest)

        current = nearest

    return route


# Homepage
@app.route("/")
def home():
    return render_template("welcome.html")
@app.route("/goodbye")
def goodbye():
    return render_template("goodbye.html")

@app.route("/optimizer")
def optimizer():
    return render_template("index.html")

# Route Optimization API
@app.route("/optimize", methods=["POST"])
def optimize():

    data = request.get_json(silent=True) or {}

    locations = data.get("locations", [])

    if not isinstance(locations, list) or not 2 <= len(locations) <= 21:

        return jsonify({
            "error": "Provide a warehouse and between 1 and 20 delivery stops."
        }), 400

    try:

        coordinates = []

        for point in locations:

            lat = float(point["lat"])
            lon = float(point["lon"])

            if not (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                raise ValueError()

            coordinates.append((lat, lon))

    except (KeyError, TypeError, ValueError):

        return jsonify({
            "error": "One or more location coordinates are invalid."
        }), 400

    # Calculate optimized route
    route = optimize_route(coordinates)

    return jsonify({

        "route": route,

        "method": "Nearest Neighbor",

        "stop_count": len(route) - 1

    })

# SAVE ROUTE TO DATABASE
@app.route("/save-route", methods=["POST"])
def save_route_api():

    data = request.get_json(silent=True) or {}

    try:
        route_id = save_route(
            data["warehouse"],
            int(data["stops"]),
            float(data["distance"]),
            data["time"],
            float(data["fuelUsed"]),
            float(data["fuelCost"])
        )

        return jsonify({
            "success": True,
            "route_id": route_id
        })

    except (KeyError, TypeError, ValueError):
        return jsonify({
            "error": "Invalid route information."
        }), 400


# GET ROUTE HISTORY FROM DATABASE
@app.route("/get-route-history", methods=["GET"])
def route_history_api():

    records = get_route_history()

    history = []

    for record in records:
        history.append({
            "id": record[0],
            "warehouse": record[1],
            "stops": record[2],
            "distance": record[3],
            "time": record[4],
            "fuelUsed": record[5],
            "fuelCost": record[6]
        })

    return jsonify(history)

# ADD VEHICLE TO DATABASE
@app.route("/add-vehicle", methods=["POST"])
def add_vehicle_api():

    data = request.get_json(silent=True) or {}

    try:
        number = data["number"].strip().upper()
        vehicle_type = data["type"]
        fuel = data["fuel"]
        mileage = float(data["mileage"])

        if not number or mileage <= 0 or not math.isfinite(mileage):
            raise ValueError()

        save_vehicle(number, vehicle_type, fuel, mileage)

        return jsonify({"success": True})

    except sqlite3.IntegrityError:
        return jsonify({
            "error": "This vehicle is already registered."
        }), 409

    except (KeyError, TypeError, ValueError):
        return jsonify({
            "error": "Please provide valid vehicle details."
        }), 400


# GET ALL REGISTERED VEHICLES
@app.route("/get-vehicles", methods=["GET"])
def get_vehicles_api():

    vehicles = get_vehicles()

    result = []

    for vehicle in vehicles:
        result.append({
            "id": vehicle[0],
            "number": vehicle[1],
            "type": vehicle[2],
            "fuel": vehicle[3],
            "mileage": vehicle[4],
            "availability": vehicle[5]
        })

    return jsonify(result)


# DELETE VEHICLE
@app.route("/delete-vehicle/<int:vehicle_id>", methods=["DELETE"])
def delete_vehicle_api(vehicle_id):

    delete_vehicle(vehicle_id)

    return jsonify({"success": True})

# =================================
# DELIVERY MANAGEMENT API
# =================================

# SAVE DELIVERY
@app.route("/save-delivery", methods=["POST"])
def save_delivery_api():
    data = request.get_json(silent=True) or {}

    try:
        save_delivery(
            int(data["route_id"]),
            int(data["stop_number"]),
            data["location"]
        )
        return jsonify({"success": True})

    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid delivery information."}), 400


# GET DELIVERIES FOR A ROUTE
@app.route("/get-deliveries/<int:route_id>", methods=["GET"])
def get_deliveries_api(route_id):
    records = get_deliveries(route_id)

    deliveries = []

    for record in records:
        deliveries.append({
            "id": record[0],
            "route_id": record[1],
            "stop_number": record[2],
            "location": record[3],
            "status": record[4]
        })

    return jsonify(deliveries)


# UPDATE DELIVERY STATUS
@app.route("/update-delivery/<int:delivery_id>", methods=["PUT"])
def update_delivery_api(delivery_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")

    if status not in ["Pending", "Delivered"]:
        return jsonify({"error": "Invalid delivery status."}), 400

    update_delivery_status(delivery_id, status)
    return jsonify({"success": True})

# DELETE DELIVERY
@app.route("/delete-delivery/<int:delivery_id>", methods=["DELETE"])
def delete_delivery_api(delivery_id):
    delete_delivery(delivery_id)
    return jsonify({"success": True})

# DELETE ROUTE
@app.route("/delete-route/<int:route_id>", methods=["DELETE"])
def delete_route_api(route_id):
    delete_route(route_id)
    return jsonify({"success": True})

# Run the website
if __name__ == "__main__":

    app.run(debug=True)
