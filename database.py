
import sqlite3
import os
from datetime import datetime, timedelta


DATABASE_NAME = os.environ.get(
    "DATABASE_PATH",
    "lro_database.db"
)


# =================================
# DATABASE CONNECTION
# =================================

def connect_database():

    connection = sqlite3.connect(
        DATABASE_NAME,
        timeout=30
    )

    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# =================================
# BACKUP DATABASE BEFORE MIGRATION
# =================================

def backup_database(connection):

    database_path = os.path.abspath(DATABASE_NAME)
    directory = os.path.dirname(database_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_path = os.path.join(
        directory,
        f"lro_database_before_mobile_migration_{timestamp}.db"
    )

    backup_connection = sqlite3.connect(backup_path)

    try:
        connection.backup(backup_connection)
    finally:
        backup_connection.close()

    print("Database backup created:", backup_path)


# =================================
# REMOVE UNIQUE MOBILE CONSTRAINT
# =================================

def migrate_mobile_number():

    connection = connect_database()

    try:

        cursor = connection.cursor()

        cursor.execute("PRAGMA index_list(users)")
        indexes = cursor.fetchall()

        mobile_is_unique = False

        for index in indexes:

            index_name = index[1]
            is_unique = index[2]

            if is_unique:

                cursor.execute(
                    f'PRAGMA index_info("{index_name}")'
                )

                indexed_columns = [
                    column[2]
                    for column in cursor.fetchall()
                ]

                if indexed_columns == ["mobile"]:
                    mobile_is_unique = True
                    break

        if not mobile_is_unique:

            print(
                "Mobile number uniqueness restriction "
                "is already removed."
            )
            return

        print("Old mobile uniqueness restriction detected.")

        backup_database(connection)

        cursor.execute("PRAGMA foreign_keys = OFF")

        try:

            cursor.execute("BEGIN IMMEDIATE")

            cursor.execute("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    mobile TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                INSERT INTO users_new (
                    id,
                    full_name,
                    email,
                    mobile,
                    password_hash,
                    role,
                    created_at
                )
                SELECT
                    id,
                    full_name,
                    email,
                    mobile,
                    password_hash,
                    role,
                    created_at
                FROM users
            """)

            cursor.execute("DROP TABLE users")

            cursor.execute("""
                ALTER TABLE users_new
                RENAME TO users
            """)

            connection.commit()

            print(
                "Mobile number uniqueness restriction "
                "removed successfully."
            )

        except Exception:

            connection.rollback()
            raise

        finally:

            cursor.execute("PRAGMA foreign_keys = ON")

    finally:

        connection.close()


# =================================
# CREATE DATABASE AND TABLES
# =================================

def create_database():

    connection = connect_database()

    try:

        cursor = connection.cursor()

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
                FOREIGN KEY (route_id)
                    REFERENCES route_history(id)
            )
        """)

        # USER ACCOUNTS TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                mobile TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # PASSWORD RESET TOKENS TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
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

        # ASSIGN EXISTING RECORDS TO OWNER ACCOUNT
        cursor.execute("""
            SELECT id
            FROM users
            WHERE email = ?
        """, ("pratiknaskar7002@gmail.com",))

        owner = cursor.fetchone()

        if owner:

            owner_id = owner[0]

            for table in [
                "route_history",
                "fleet_vehicles",
                "deliveries"
            ]:

                cursor.execute(
                    f"""
                    UPDATE {table}
                    SET user_id = ?
                    WHERE user_id IS NULL
                    """,
                    (owner_id,)
                )

        connection.commit()

        print("LRO Database created successfully!")

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()

    # Migrate existing databases after normal initialization
    migrate_mobile_number()


# =================================
# SAVE ROUTE
# =================================

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
            INSERT INTO route_history (
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


# =================================
# GET ROUTE HISTORY
# =================================

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


# =================================
# SAVE VEHICLE
# =================================

def save_vehicle(user_id, number, vehicle_type, fuel, mileage):

    connection = connect_database()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO fleet_vehicles (
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


# =================================
# GET VEHICLES
# =================================

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


# =================================
# DELETE VEHICLE
# =================================

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


# =================================
# SAVE DELIVERY
# =================================

def save_delivery(user_id, route_id, stop_number, location):

    connection = connect_database()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO deliveries (
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


# =================================
# GET DELIVERIES
# =================================

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


# =================================
# UPDATE DELIVERY STATUS
# =================================

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


# =================================
# DELETE DELIVERY
# =================================

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


# =================================
# DELETE ROUTE AND ITS DELIVERIES
# =================================

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


# =================================
# REGISTER USER
# =================================

def register_user(full_name, email, mobile, password_hash):

    connection = connect_database()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO users (
                full_name,
                email,
                mobile,
                password_hash
            )
            VALUES (?, ?, ?, ?)
        """, (
            full_name,
            email.strip().lower(),
            mobile,
            password_hash
        ))

        user_id = cursor.lastrowid

        connection.commit()

        return user_id

    finally:

        connection.close()


# =================================
# GET USER BY EMAIL
# =================================

def get_user_by_email(email):

    connection = connect_database()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                full_name,
                email,
                mobile,
                password_hash,
                role
            FROM users
            WHERE email = ?
        """, (email.strip().lower(),))

        return cursor.fetchone()

    finally:

        connection.close()


# =================================
# CREATE PASSWORD RESET TOKEN
# =================================

def create_password_reset_token(user_id, token_hash, expires_at):

    connection = connect_database()

    try:

        cursor = connection.cursor()

        # Invalidate previous unused reset links for this user
        cursor.execute("""
            UPDATE password_reset_tokens
            SET used_at = ?
            WHERE user_id = ?
              AND used_at IS NULL
        """, (
            datetime.utcnow().isoformat(),
            user_id
        ))

        cursor.execute("""
            INSERT INTO password_reset_tokens (
                user_id,
                token_hash,
                expires_at
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            token_hash,
            expires_at
        ))

        connection.commit()

    finally:

        connection.close()


# =================================
# GET PASSWORD RESET TOKEN
# =================================

def get_password_reset_token(token_hash):

    connection = connect_database()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                user_id,
                token_hash,
                expires_at,
                used_at
            FROM password_reset_tokens
            WHERE token_hash = ?
        """, (token_hash,))

        return cursor.fetchone()

    finally:

        connection.close()


# =================================
# REVOKE PASSWORD RESET TOKENS
# =================================

def revoke_password_reset_tokens(user_id):

    connection = connect_database()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            UPDATE password_reset_tokens
            SET used_at = ?
            WHERE user_id = ?
              AND used_at IS NULL
        """, (
            datetime.utcnow().isoformat(),
            user_id
        ))

        connection.commit()

    finally:

        connection.close()


# =================================
# RESET USER PASSWORD
# =================================

def reset_user_password(token_hash, password_hash):

    connection = connect_database()

    try:

        cursor = connection.cursor()

        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT
                id,
                user_id,
                expires_at,
                used_at
            FROM password_reset_tokens
            WHERE token_hash = ?
        """, (token_hash,))

        token = cursor.fetchone()

        if not token:
            connection.rollback()
            return False

        token_id, user_id, expires_at, used_at = token

        if used_at is not None:
            connection.rollback()
            return False

        try:
            expiry_time = datetime.fromisoformat(expires_at)
        except (TypeError, ValueError):
            connection.rollback()
            return False

        if expiry_time <= datetime.utcnow():
            connection.rollback()
            return False

        cursor.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
        """, (
            password_hash,
            user_id
        ))

        if cursor.rowcount != 1:
            connection.rollback()
            return False

        cursor.execute("""
            UPDATE password_reset_tokens
            SET used_at = ?
            WHERE id = ?
              AND used_at IS NULL
        """, (
            datetime.utcnow().isoformat(),
            token_id
        ))

        if cursor.rowcount != 1:
            connection.rollback()
            return False

        # Invalidate any other unused reset links
        cursor.execute("""
            UPDATE password_reset_tokens
            SET used_at = ?
            WHERE user_id = ?
              AND used_at IS NULL
        """, (
            datetime.utcnow().isoformat(),
            user_id
        ))

        connection.commit()

        return True

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# =================================
# RUN DATABASE
# =================================

if __name__ == "__main__":

    create_database()
