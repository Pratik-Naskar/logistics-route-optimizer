
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from email.message import EmailMessage
from datetime import datetime, timedelta
import os
import math
import sqlite3
import secrets
import hashlib
import smtplib

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
    get_user_by_email,
    create_password_reset_token,
    get_password_reset_token,
    reset_user_password
)


# =================================
# CREATE FLASK APPLICATION
# =================================

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RENDER", "").lower() == "true",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 7
)

# Initialize database
create_database()


# =================================
# LOGIN REQUIRED DECORATOR
# =================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# =================================
# SEND PASSWORD RESET EMAIL
# =================================

def send_password_reset_email(recipient_email, reset_link):

    mail_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    mail_port = int(os.environ.get("MAIL_PORT", "587"))
    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD", "").replace(" ", "")
    use_tls = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"

    if not mail_username or not mail_password:
        raise RuntimeError("Email service is not configured.")

    message = EmailMessage()

    message["Subject"] = "LRO - Password Reset Request"
    message["From"] = mail_username
    message["To"] = recipient_email

    message.set_content(f"""
Hello,

We received a request to reset your Logistics Route Optimizer account password.

Use the link below to create a new password:

{reset_link}

This link expires in 30 minutes and can only be used once.

If you did not request a password reset, you can safely ignore this email.

Regards,
LRO Support Team
Logistics Route Optimizer
""")

    with smtplib.SMTP(mail_server, mail_port, timeout=20) as server:

        if use_tls:
            server.starttls()

        server.login(mail_username, mail_password)
        server.send_message(message)


# =================================
# PASSWORD RESET LINK VALIDATION
# =================================

def validate_reset_token(token):

    if not token:
        return None

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    reset_record = get_password_reset_token(token_hash)

    if not reset_record:
        return None

    token_id, user_id, stored_hash, expires_at, used_at = reset_record

    if used_at is not None:
        return None

    try:
        expiry_time = datetime.fromisoformat(expires_at)
    except (TypeError, ValueError):
        return None

    if expiry_time <= datetime.utcnow():
        return None

    return token_hash


# =================================
# DISTANCE CALCULATION
# =================================

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


# =================================
# NEAREST NEIGHBOR ALGORITHM
# =================================

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

        if not all([full_name, email, mobile, password, confirm_password]):
            return render_template(
                "register.html",
                error="Please fill in all the fields."
            )

        if "@" not in email or "." not in email:
            return render_template(
                "register.html",
                error="Please enter a valid email address."
            )

        if not mobile.isdigit() or len(mobile) != 10:
            return render_template(
                "register.html",
                error="Enter a valid 10-digit mobile number."
            )

        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must contain at least 8 characters."
            )

        if password != confirm_password:
            return render_template(
                "register.html",
                error="Passwords do not match."
            )

        password_hash = generate_password_hash(password)

        try:

            user_id = register_user(
                full_name,
                email,
                mobile,
                password_hash
            )

            session.clear()

            session["user_id"] = user_id
            session["user_name"] = full_name
            session["user_role"] = "user"

            session.permanent = True

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

        if user:

            try:
                password_matches = check_password_hash(
                    user[4],
                    password
                )
            except (TypeError, ValueError):
                password_matches = False

            if password_matches:

                session.clear()

                session["user_id"] = user[0]
                session["user_name"] = user[1]
                session["user_role"] = user[5]

                session.permanent = True

                return redirect(url_for("optimizer"))

        return render_template(
            "login.html",
            error="Invalid email address or password."
        )

    return render_template("login.html")


# =================================
# FORGOT PASSWORD
# =================================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        if not email or "@" not in email or "." not in email:
            return render_template(
                "forgot_password.html",
                error="Please enter a valid email address."
            )

        user = get_user_by_email(email)

        if user:

            try:

                # Generate a secure random token
                reset_token = secrets.token_urlsafe(32)

                # Store only the SHA-256 hash in the database
                token_hash = hashlib.sha256(
                    reset_token.encode("utf-8")
                ).hexdigest()

                # Token expires after 30 minutes
                expires_at = (
                    datetime.utcnow() + timedelta(minutes=30)
                ).isoformat()

                create_password_reset_token(
                    user[0],
                    token_hash,
                    expires_at
                )

                # Use configured base URL when available
                base_url = os.environ.get("BASE_URL", "").rstrip("/")

                if not base_url:
                    base_url = request.host_url.rstrip("/")

                # Render uses HTTPS
                if os.environ.get("RENDER", "").lower() == "true":
                    base_url = base_url.replace("http://", "https://", 1)

                reset_link = (
                    f"{base_url}/reset-password/{reset_token}"
                )

                send_password_reset_email(
                    user[2],
                    reset_link
                )

            except Exception:
                # Never log the reset token, reset URL or email password
                app.logger.error(
                    "Password reset email could not be processed."
                )

        # Same response whether the account exists or not
        return render_template(
            "forgot_password.html",
            message=(
                "If an account exists with that email address, "
                "a password reset link will be sent."
            )
        )

    return render_template("forgot_password.html")


# =================================
# RESET PASSWORD
# =================================

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    token_hash = validate_reset_token(token)

    if not token_hash:

        return render_template(
            "reset_password.html",
            error="This password reset link is invalid or has expired.",
            invalid_token=True
        )

    if request.method == "POST":

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password or not confirm_password:

            return render_template(
                "reset_password.html",
                error="Please fill in both password fields."
            )

        if len(password) < 8:

            return render_template(
                "reset_password.html",
                error="Password must contain at least 8 characters."
            )

        if password != confirm_password:

            return render_template(
                "reset_password.html",
                error="Passwords do not match."
            )

        password_hash = generate_password_hash(password)

        try:

            success = reset_user_password(
                token_hash,
                password_hash
            )

            if not success:

                return render_template(
                    "reset_password.html",
                    error="This reset link is invalid, expired or already used.",
                    invalid_token=True
                )

            return render_template(
                "reset_password.html",
                message="Your password has been reset successfully. You can now log in.",
                success=True
            )

        except Exception:

            app.logger.error("Password reset could not be completed.")

            return render_template(
                "reset_password.html",
                error="Something went wrong. Please request a new reset link."
            )

    return render_template("reset_password.html")


# =================================
# HOMEPAGE
# =================================

@app.route("/")
def home():

    return render_template("welcome.html")


# =================================
# GOODBYE PAGE
# =================================

@app.route("/goodbye")
def goodbye():

    return render_template("goodbye.html")


# =================================
# USER LOGOUT
# =================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# =================================
# OPTIMIZER DASHBOARD
# =================================

@app.route("/optimizer")
@login_required
def optimizer():

    return render_template("index.html")


# =================================
# ROUTE OPTIMIZATION API
# =================================

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

    route = optimize_route(coordinates)

    return jsonify({
        "route": route,
        "method": "Nearest Neighbor",
        "stop_count": len(route) - 1
    })


# =================================
# SAVE ROUTE
# =================================

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


# =================================
# GET ROUTE HISTORY
# =================================

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


# =================================
# ADD VEHICLE
# =================================

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

        save_vehicle(
            session["user_id"],
            number,
            vehicle_type,
            fuel,
            mileage
        )

        return jsonify({"success": True})

    except sqlite3.IntegrityError:

        return jsonify({
            "error": "This vehicle is already registered."
        }), 409

    except (KeyError, TypeError, ValueError, AttributeError):

        return jsonify({
            "error": "Please provide valid vehicle details."
        }), 400


# =================================
# GET VEHICLES
# =================================

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


# =================================
# DELETE VEHICLE
# =================================

@app.route("/delete-vehicle/<int:vehicle_id>", methods=["DELETE"])
@login_required
def delete_vehicle_api(vehicle_id):

    delete_vehicle(session["user_id"], vehicle_id)

    return jsonify({"success": True})


# =================================
# DELIVERY MANAGEMENT
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

            return jsonify({
                "error": "Route not found."
            }), 404

        return jsonify({"success": True})

    except (KeyError, TypeError, ValueError):

        return jsonify({
            "error": "Invalid delivery information."
        }), 400


# GET DELIVERIES
@app.route("/get-deliveries/<int:route_id>", methods=["GET"])
@login_required
def get_deliveries_api(route_id):

    records = get_deliveries(
        session["user_id"],
        route_id
    )

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

        return jsonify({
            "error": "Invalid delivery status."
        }), 400

    success = update_delivery_status(
        session["user_id"],
        delivery_id,
        status
    )

    if not success:

        return jsonify({
            "error": "Delivery not found."
        }), 404

    return jsonify({"success": True})


# DELETE DELIVERY
@app.route("/delete-delivery/<int:delivery_id>", methods=["DELETE"])
@login_required
def delete_delivery_api(delivery_id):

    success = delete_delivery(
        session["user_id"],
        delivery_id
    )

    if not success:

        return jsonify({
            "error": "Delivery not found."
        }), 404

    return jsonify({"success": True})


# DELETE ROUTE
@app.route("/delete-route/<int:route_id>", methods=["DELETE"])
@login_required
def delete_route_api(route_id):

    success = delete_route(
        session["user_id"],
        route_id
    )

    if not success:

        return jsonify({
            "error": "Route not found."
        }), 404

    return jsonify({"success": True})


# =================================
# RUN WEBSITE
# =================================

if __name__ == "__main__":

    app.run(debug=True)
