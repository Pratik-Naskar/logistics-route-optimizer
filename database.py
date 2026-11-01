
import sqlite3

DATABASE_NAME = "lro_database.db"


# DATABASE CONNECTION
def connect_database():
    connection = sqlite3.connect(
        DATABASE_NAME,
        timeout=30
    )

    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# CREATE DATABASE AND TABLES
def create_database():

    connection = connect_database()
    cursor = connection.cursor()

    try:
        # Enable WAL mode for better concurrent access
        cursor.execute("PRAGMA journal_mode = WAL")

        # ROUTE HISTORY TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS route_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse TEXT NOT NULL,
                stops INTEGER,
                distance REAL,
                estimated_time TEXT,
                fuel_used REAL,
                fuel_cost REAL
            )
        """)

        # FLEET MANAGEMENT TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fleet_vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_number TEXT UNIQUE NOT NULL,
                vehicle_type TEXT,
                fuel_type TEXT,
                mileage REAL,
                availability TEXT DEFAULT 'Available'
            )
        """)

        # DELIVERY MANAGEMENT TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id INTEGER,
                stop_number INTEGER,
                location TEXT,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (route_id) REFERENCES route_history(id)
            )
        """)

        # USER ACCOUNTS TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                mobile TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ADD USER OWNERSHIP TO EXISTING TABLES
        tables = [
            "route_history",
            "fleet_vehicles",
            "deliveries"
        ]

        for table in tables:

            cursor.execute(f"PRAGMA table_info({table})")

            columns = [
                column[1]
                for column in cursor.fetchall()
            ]

            if "user_id" not in columns:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"
                )

        # ASSIGN EXISTING RECORDS TO OWNER
        cursor.execute(
            "SELECT id FROM users WHERE email = ?",
            ("pratiknaskar7002@gmail.com",)
        )

        owner = cursor.fetchone()

        if owner:

            owner_id = owner[0]

            cursor.execute("""
                UPDATE route_history
                SET user_id = ?
                WHERE user_id IS NULL
            """, (owner_id,))

            cursor.execute("""
                UPDATE fleet_vehicles
                SET user_id = ?
                WHERE user_id IS NULL
            """, (owner_id,))

            cursor.execute("""
                UPDATE deliveries
                SET user_id = ?
                WHERE user_id IS NULL
            """, (owner_id,))

        connection.commit()

        print("LRO Database created successfully!")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# SAVE ROUTE
def save_route(
    user_id,
    warehouse,
    stops,
    distance,
    estimated_time,
    fuel_used,
    fuel_cost
):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO route_history
            (
                user_id,
                warehouse,
                stops,
                distance,
                estimated_time,
                fuel_used,
                fuel_cost
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            warehouse,
            stops,
            distance,
            estimated_time,
            fuel_used,
            fuel_cost
        ))

        route_id = cursor.lastrowid

        connection.commit()

        return route_id

    finally:
        connection.close()


# GET ROUTE HISTORY
def get_route_history(user_id):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM route_history
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,))

        return cursor.fetchall()

    finally:
        connection.close()


# SAVE VEHICLE
def save_vehicle(user_id, number, vehicle_type, fuel, mileage):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO fleet_vehicles
            (
                user_id,
                vehicle_number,
                vehicle_type,
                fuel_type,
                mileage
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            number,
            vehicle_type,
            fuel,
            mileage
        ))

        connection.commit()

    finally:
        connection.close()


# GET VEHICLES
def get_vehicles(user_id):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM fleet_vehicles
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,))

        return cursor.fetchall()

    finally:
        connection.close()


# DELETE VEHICLE
def delete_vehicle(user_id, vehicle_id):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fleet_vehicles
            WHERE id = ? AND user_id = ?
        """, (vehicle_id, user_id))

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


# SAVE DELIVERY
def save_delivery(user_id, route_id, stop_number, location):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO deliveries
            (
                user_id,
                route_id,
                stop_number,
                location
            )
            SELECT ?, id, ?, ?
            FROM route_history
            WHERE id = ? AND user_id = ?
        """, (
            user_id,
            stop_number,
            location,
            route_id,
            user_id
        ))

        success = cursor.rowcount > 0

        connection.commit()

        return success

    finally:
        connection.close()


# GET DELIVERIES
def get_deliveries(user_id, route_id):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT deliveries.*
            FROM deliveries
            JOIN route_history
            ON deliveries.route_id = route_history.id
            WHERE deliveries.user_id = ?
            AND route_history.user_id = ?
            AND deliveries.route_id = ?
            ORDER BY deliveries.stop_number
        """, (user_id, user_id, route_id))

        return cursor.fetchall()

    finally:
        connection.close()


# UPDATE DELIVERY STATUS
def update_delivery_status(user_id, delivery_id, status):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE deliveries
            SET status = ?
            WHERE id = ? AND user_id = ?
        """, (status, delivery_id, user_id))

        success = cursor.rowcount > 0

        connection.commit()

        return success

    finally:
        connection.close()


# DELETE DELIVERY
def delete_delivery(user_id, delivery_id):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM deliveries
            WHERE id = ? AND user_id = ?
        """, (delivery_id, user_id))

        success = cursor.rowcount > 0

        connection.commit()

        return success

    finally:
        connection.close()


# DELETE ROUTE AND ITS DELIVERIES
def delete_route(user_id, route_id):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM deliveries
            WHERE route_id = ? AND user_id = ?
        """, (route_id, user_id))

        cursor.execute("""
            DELETE FROM route_history
            WHERE id = ? AND user_id = ?
        """, (route_id, user_id))

        success = cursor.rowcount > 0

        connection.commit()

        return success

    finally:
        connection.close()


# REGISTER USER
def register_user(full_name, email, mobile, password_hash):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO users
            (
                full_name,
                email,
                mobile,
                password_hash
            )
            VALUES (?, ?, ?, ?)
        """, (
            full_name,
            email,
            mobile,
            password_hash
        ))

        user_id = cursor.lastrowid

        connection.commit()

        return user_id

    finally:
        connection.close()


# GET USER BY EMAIL
def get_user_by_email(email):

    connection = connect_database()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (email,))

        return cursor.fetchone()

    finally:
        connection.close()


# RUN DATABASE
if __name__ == "__main__":
    create_database()
