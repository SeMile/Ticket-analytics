import csv
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
import os

def parse_number(value):
    """Конвертация строковых чисел в float с улучшенной обработкой ошибок"""
    try:
        if value in (None, '', ' ', '-'):
            return 0.0
        return float(str(value).replace(',', '.').replace(' ', ''))
    except ValueError:
        return 0.0

def process_row(row):
    """Обработка и преобразование данных строки с улучшенной валидацией"""
    try:
        # Проверка обязательных полей
        if not row.get('ID заказа'):
            raise ValueError("Отсутствует ID заказа")

        # Обработка даты и времени
        order_date = datetime.strptime(row['Дата оформления'], '%Y-%m-%d')
        
        # Обработка времени (с защитой от ошибок)
        order_time = row.get('Время оформления (часы:минуты)', '00:00')
        event_time = row.get('Время', '00:00')
        
        booking_hour = int(order_time.split(':')[0]) if ':' in order_time else 0
        flight_hour = int(event_time.split(':')[0]) if ':' in event_time else 0

        return (
            row['ID заказа'],
            row['Дата оформления'],
            order_time,
            row.get('ФИО клиента', ''),
            row.get('Емаил клиента', ''),
            row.get('Тел клиента', ''),
            row.get('Название события', ''),
            row.get('Дата', ''),
            event_time,
            row.get('Компания-организатор (название)', ''),
            row.get('Компания-продавец (название)', ''),
            int(parse_number(row.get('Кол-во билетов', 0))),
            parse_number(row.get('Сумма заказа', 0)),
            row.get('Промокод', ''),
            parse_number(row.get('Процент/сумма скидки', 0)),
            parse_number(row.get('Процент агентского вознаграждения', 0)),
            parse_number(row.get('Процент комиссии системы', 0)),
            parse_number(row.get('Сумма вознаграждения организатора', 0)),
            parse_number(row.get('Сумма агентского вознаграждения', 0)),
            parse_number(row.get('Сумма комиссии системы', 0)),
            parse_number(row.get('Сумма скидки', 0)),
            row.get('Статус оплаты', ''),
            row.get('Статус билета', ''),
            row.get('Дата возврата', ''),
            parse_number(row.get('Сумма возврата', 0)),
            parse_number(row.get('ЕРБ', 0)),
            order_date.year,
            order_date.month,
            booking_hour,
            flight_hour
        )
    except Exception as e:
        print(f"Ошибка обработки строки: {e}")
        return None

def insert_batch(conn, batch):
    """Пакетная вставка данных с обработкой ошибок"""
    try:
        cursor = conn.cursor()
        
        # Вставляем данные о заказах
        cursor.executemany('''
        INSERT OR IGNORE INTO tickets VALUES (
            NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ''', [row for row in batch if row is not None])
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при пакетной вставке: {e}")
        raise

def import_csv_to_sqlite(csv_path=None, db_path=None, batch_size=1000):
    """Основная функция импорта с улучшенной обработкой ошибок"""
    conn = None
    try:
        # Установка путей по умолчанию
        base_dir = Path(__file__).parent.parent
        if csv_path is None:
            csv_path = base_dir / 'data' / '2024-orders-export.csv'
        if db_path is None:
            db_path = base_dir / 'data' / 'tickets.db'
        
        # Проверка существования файлов
        if not Path(csv_path).exists():
            raise FileNotFoundError(f"CSV файл не найден: {csv_path}")
        
        # Создание папки для БД, если не существует
        os.makedirs(Path(db_path).parent, exist_ok=True)
        
        # Подключение к БД
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        
        # Создание таблицы
        conn.execute('''
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
        
        # Чтение CSV файла
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';', quotechar='"')
            rows = list(reader)  # Читаем все строки для точного прогресс-бара
            
            with tqdm(total=len(rows), desc="Импорт данных") as pbar:
                batch = []
                
                for row in rows:
                    try:
                        processed = process_row(row)
                        if processed:
                            batch.append(processed)
                            
                            if len(batch) >= batch_size:
                                insert_batch(conn, batch)
                                batch = []
                                
                    except Exception as e:
                        print(f"\nОшибка обработки строки: {e}")
                    
                    pbar.update(1)
                
                # Вставка оставшихся данных
                if batch:
                    insert_batch(conn, batch)
        
        print("\nИмпорт успешно завершен")
        
    except Exception as e:
        print(f"\nОшибка при импорте: {e}")
        raise
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    try:
        # Запрос пути к CSV файлу, если не указан
        csv_input = input("Введите путь к CSV файлу (или оставьте пустым для файла по умолчанию): ").strip()
        csv_path = Path(csv_input) if csv_input else None
        
        import_csv_to_sqlite(csv_path)
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        input("Нажмите Enter для выхода...")