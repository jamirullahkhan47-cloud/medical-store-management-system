"""Database access and schema setup for the medical store application."""

from contextlib import contextmanager
import os

import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "jamirullah_app"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "jamirullah_medical_store"),
    "charset": "utf8mb4",
    "use_unicode": True,
}


def get_connection():
    """Connect only to the configured application database."""
    if not DB_CONFIG["password"] or DB_CONFIG["password"].startswith("<"):
        raise RuntimeError("Set a real DB_PASSWORD in the .env file.")
    return mysql.connector.connect(**DB_CONFIG)


@contextmanager
def database_cursor(commit=False, dictionary=True):
    connection = get_connection()
    cursor = connection.cursor(dictionary=dictionary)
    try:
        yield connection, cursor
        if commit:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def setup_database():
    """Create/upgrade tables inside the pre-created, app-specific database."""
    with database_cursor(commit=True, dictionary=False) as (_, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                must_change_password BOOLEAN NOT NULL DEFAULT FALSE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                category VARCHAR(100) NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                stock INT NOT NULL DEFAULT 0,
                expiry DATE NOT NULL,
                INDEX idx_medicines_name (name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                contact VARCHAR(30) NOT NULL,
                address VARCHAR(255) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NULL,
                medicine_name VARCHAR(150) NOT NULL,
                quantity INT NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                total DECIMAL(10,2) NOT NULL,
                sale_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_sales_date (sale_date),
                CONSTRAINT fk_sales_medicine FOREIGN KEY (medicine_id)
                    REFERENCES medicines(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Upgrade tables created by the earlier standalone setup script.
        cursor.execute("SHOW COLUMNS FROM users LIKE 'must_change_password'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE")
        cursor.execute("SHOW COLUMNS FROM sales LIKE 'medicine_name'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE sales ADD COLUMN medicine_name VARCHAR(150) NOT NULL DEFAULT ''")
            cursor.execute("""
                UPDATE sales s JOIN medicines m ON m.id = s.medicine_id
                SET s.medicine_name = m.name WHERE s.medicine_name = ''
            """)
        cursor.execute("SHOW COLUMNS FROM sales LIKE 'sale_date'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE sales ADD COLUMN sale_date DATETIME NULL")
            cursor.execute("UPDATE sales SET sale_date = CURRENT_TIMESTAMP WHERE sale_date IS NULL")

        cursor.execute("SELECT id FROM users WHERE username = %s", ("admin",))
        if not cursor.fetchone():
            initial_password = os.getenv("ADMIN_INITIAL_PASSWORD", "admin123")
            cursor.execute("""
                INSERT INTO users (username, password, must_change_password)
                VALUES (%s, %s, TRUE)
            """, ("admin", generate_password_hash(initial_password)))


if __name__ == "__main__":
    setup_database()
    print("Medical Store tables are ready in the configured database.")
