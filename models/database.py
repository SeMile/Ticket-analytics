import sqlite3
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def get_db_connection():
    conn = sqlite3.connect('data/tickets.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db(app):
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Создание таблицы
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            order_date TEXT,
            order_time TEXT,
            client_name TEXT,
            client_email TEXT,
            client_phone TEXT,
            event_name TEXT,
            event_date TEXT,
            event_time TEXT,
            organizer TEXT,
            seller TEXT,
            tickets_count INTEGER,
            order_amount REAL,
            discount_code TEXT,
            discount_amount REAL,
            agent_percent REAL,
            system_percent REAL,
            organizer_amount REAL,
            agent_amount REAL,
            system_amount REAL,
            discount_value REAL,
            payment_status TEXT,
            ticket_status TEXT,
            refund_date TEXT,
            refund_amount REAL,
            erb_amount REAL,
            year INTEGER,
            month INTEGER,
            booking_hour INTEGER,
            flight_hour INTEGER
        )
        ''')
        
        # Создание индексов
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_seller ON tickets(seller)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_date ON tickets(order_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_year ON tickets(year)')
        
        conn.commit()
        conn.close()