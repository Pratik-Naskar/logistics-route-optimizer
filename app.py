
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
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
    delete_route,
    register_user,
    get_user_by_email
)

# Create Flask application
app = Flask(__name__)

# Secure session configuration
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Enable secure cookies on HTTPS hosting
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("RENDER") == "true"

# Initialize LRO database
create_database()
# LOGIN REQUIRED DECORATOR

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


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


# =================================
# USER REGISTRATION
# =================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Check empty fields
        if not all([full_name, email, mobile, password, confirm_password]):
            return render_template(
                "register.html",
                error="Please fill in all the fields."
            )

        # Check email format
        if "@" not in email or "." not in email:
            return render_template(
                "register.html",
                error="Please enter a valid email address."
            )

        # Check mobile number
        if not mobile.isdigit() or len(mobile) != 10:
            return render_template(
                "register.html",
                error="Enter a valid 10-digit mobile number."
            )

        # Check password length
        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must contain at least 8 characters."
            )

        # Check password confirmation
        if password != confirm_password:
            return render_template(
                "register.html",
                error="Passwords do not match."
            )

        # Securely hash password
        password_hash = generate_password_hash(password)

        try:
            user_id = register_user(
                full_name,
                email,
                mobile,
                password_hash
            )

            # Log in the newly registered user
            session.clear()
            session["user_id"] = user_id
            session["user_name"] = full_name
            session["user_role"] = "user"

            return redirect(url_for("optimizer"))

        except sqlite3.IntegrityError:
            return render_template(
                "register.html",
                error="Email or mobile number is already registered."
            )

    return render_template("register.html")


# =================================
# USER LOGIN
# =================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)

        if user and check_password_hash(user[4], password):

            session.clear()

            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_role"] = user[5]

            return redirect(url_for("optimizer"))

        return render_template(
            "login.html",
            error="Invalid email address or password."
        )

    return render_template("login.html")

# Homepage
@app.route("/")
def home():
    return render_template("welcome.html")
@app.route("/goodbye")
def goodbye():
    return render_template("goodbye.html")
# USER LOGOUT

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))
@app.route("/optimizer")
@login_required
def optimizer():
    return render_template("index.html")

# Route Optimization API
@app.route("/optimize", methods=["POST"])
@login_required
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
@login_required
def save_route_api():

    data = request.get_json(silent=True) or {}

    try:
        route_id = save_route(
    session["user_id"],
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
@login_required
def route_history_api():

    records = get_route_history(session["user_id"])

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
@login_required
def add_vehicle_api():

    data = request.get_json(silent=True) or {}

    try:
        number = data["number"].strip().upper()
        vehicle_type = data["type"]
        fuel = data["fuel"]
        mileage = float(data["mileage"])

        if not number or mileage <= 0 or not math.isfinite(mileage):
            raise ValueError()

        save_vehicle(session["user_id"], number, vehicle_type, fuel, mileage)

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
@login_required
def get_vehicles_api():

    vehicles = get_vehicles(session["user_id"])

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
@login_required
def delete_vehicle_api(vehicle_id):

    delete_vehicle(session["user_id"], vehicle_id)

    return jsonify({"success": True})

# =================================
# DELIVERY MANAGEMENT API
# =================================

# SAVE DELIVERY
@app.route("/save-delivery", methods=["POST"])
@login_required
def save_delivery_api():
    data = request.get_json(silent=True) or {}

    try:
        success = save_delivery(
            session["user_id"],
            int(data["route_id"]),
            int(data["stop_number"]),
            data["location"]
        )

        if not success:
            return jsonify({"error": "Route not found."}), 404

        return jsonify({"success": True})

    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid delivery information."}), 400


# GET DELIVERIES FOR A ROUTE
@app.route("/get-deliveries/<int:route_id>", methods=["GET"])
@login_required
def get_deliveries_api(route_id):
    records = get_deliveries(session["user_id"], route_id)

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
@login_required
def update_delivery_api(delivery_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")

    if status not in ["Pending", "Delivered"]:
        return jsonify({"error": "Invalid delivery status."}), 400

    success = update_delivery_status(
        session["user_id"], delivery_id, status
    )

    if not success:
        return jsonify({"error": "Delivery not found."}), 404

    return jsonify({"success": True})


# DELETE DELIVERY
@app.route("/delete-delivery/<int:delivery_id>", methods=["DELETE"])
@login_required
def delete_delivery_api(delivery_id):
    success = delete_delivery(session["user_id"], delivery_id)

    if not success:
        return jsonify({"error": "Delivery not found."}), 404

    return jsonify({"success": True})


# DELETE ROUTE
@app.route("/delete-route/<int:route_id>", methods=["DELETE"])
@login_required
def delete_route_api(route_id):
    success = delete_route(session["user_id"], route_id)

    if not success:
        return jsonify({"error": "Route not found."}), 404

    return jsonify({"success": True})


# Run the website
if __name__ == "__main__":

    app.run(debug=True)
