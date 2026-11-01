import sqlite3

DATABASE_NAME = "lro_database.db"


def create_database():
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

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

    connection.commit()
    connection.close()

    print("LRO Database created successfully!")

def save_route(warehouse, stops, distance, estimated_time, fuel_used, fuel_cost):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO route_history
        (warehouse, stops, distance, estimated_time, fuel_used, fuel_cost)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (warehouse, stops, distance, estimated_time, fuel_used, fuel_cost))

    route_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return route_id


def get_route_history():
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM route_history ORDER BY id DESC")
    records = cursor.fetchall()

    connection.close()

    return records
# FLEET MANAGEMENT DATABASE FUNCTIONS

def save_vehicle(number, vehicle_type, fuel, mileage):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO fleet_vehicles
        (vehicle_number, vehicle_type, fuel_type, mileage)
        VALUES (?, ?, ?, ?)
    """, (number, vehicle_type, fuel, mileage))

    connection.commit()
    connection.close()


def get_vehicles():
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM fleet_vehicles ORDER BY id DESC")
    vehicles = cursor.fetchall()

    connection.close()
    return vehicles


def delete_vehicle(vehicle_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM fleet_vehicles WHERE id = ?",
        (vehicle_id,)
    )

    connection.commit()
    connection.close()
    return 
# DELIVERY MANAGEMENT DATABASE FUNCTIONS

def save_delivery(route_id, stop_number, location):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO deliveries
        (route_id, stop_number, location)
        VALUES (?, ?, ?)
    """, (route_id, stop_number, location))

    connection.commit()
    connection.close()


def get_deliveries(route_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM deliveries
        WHERE route_id = ?
        ORDER BY stop_number
    """, (route_id,))

    deliveries = cursor.fetchall()
    connection.close()

    return deliveries
def update_delivery_status(delivery_id, status):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE deliveries
        SET status = ?
        WHERE id = ?
    """, (status, delivery_id))

    connection.commit()
    connection.close()
# DELETE DELIVERY
def delete_delivery(delivery_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM deliveries WHERE id = ?",
        (delivery_id,)
    )

    connection.commit()
    connection.close()


# DELETE ROUTE AND ITS DELIVERIES
def delete_route(route_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM deliveries WHERE route_id = ?",
        (route_id,)
    )

    cursor.execute(
        "DELETE FROM route_history WHERE id = ?",
        (route_id,)
    )

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_database()