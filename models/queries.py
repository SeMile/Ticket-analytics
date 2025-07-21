import sqlite3
from models.database import get_db_connection
from datetime import datetime
import json

def get_summary_stats(filters=None):
    conn = get_db_connection()
    try:
        base_condition = "payment_status != 'Не оплачен' AND system_percent = 0 AND system_amount = 0"
        where_clause, params = build_where_clause(filters)

        if year != 'all':
            try:
                year = int(year)
                where_clause = f"WHERE year = {year}"
            except ValueError:
                return {"error": "Invalid year format"}, 400
        
        # Добавляем базовое условие исключения "Не оплачен и полный возврат"
        if "WHERE" in where_clause:
            where_clause = where_clause.replace("WHERE", f"WHERE {base_condition} AND")
        else:
            where_clause = f"WHERE {base_condition}"
            
        query = f"""
        SELECT
        SUM(order_amount) - SUM(CASE WHEN payment_status = 'Возвращен' AND refund_amount > 0 THEN refund_amount ELSE 0 END) AS total_revenue,
        SUM(CASE WHEN refund_amount != order_amount THEN agent_amount ELSE 0 END) as total_agent,
        SUM(CASE WHEN refund_amount != order_amount THEN system_amount ELSE 0 END) as total_commission,
        SUM(CASE WHEN payment_status = 'Возвращен' AND refund_amount > 0 THEN refund_amount ELSE 0 END) as total_refunds,
        AVG(CASE WHEN payment_status = 'Возвращен' AND refund_amount > 0 THEN refund_amount ELSE 0 END) as avg_refund
        FROM tickets
        {where_clause}
        """
        
        # Добавляем фильтры (например, по дате или статусу)
        where_clause, params = build_where_clause(filters)
        query += where_clause
        
        result = conn.execute(query).fetchone()
        conn.close()
        
        return {
            'total_revenue': result['total_revenue'] or 0,
            'total_agent': result['total_agent'] or 0,
            'total_commission': result['total_commission'] or 0,
            'total_orders': result['total_orders'] or 0,
            'avg_order': result['avg_order'] or 0,
            'total_refunds': result['total_refunds'] or 0,
            'avg_refund': result['avg_refund'] or 0
        }
        
    except sqlite3.Error as e:
        return {"error": f"Database error: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}, 500

def get_top_sellers(limit=20):
    conn = get_db_connection()
    
    query = '''
    SELECT 
        seller,
        SUM(agent_amount) as agent_amount,
        SUM(system_amount) as system_amount,
        COUNT(*) as orders_count
    FROM tickets
    WHERE agent_amount > 0
    GROUP BY seller
    ORDER BY agent_amount DESC
    LIMIT ?
    '''
    
    result = conn.execute(query, (limit,)).fetchall()
    conn.close()
    
    return [
        dict(row) for row in result
    ]

# Прямые продажи Организатор = Агент
def get_direct_sales():
    conn = get_db_connection()
    
    query = '''
    SELECT 
        seller,
        SUM(organizer_amount) as direct_sales,
        SUM(system_amount) as system_commission,
        SUM(tickets_count) as orders_count,
        SUM(order_amount) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) as total_revenue
    FROM tickets
    WHERE agent_amount = 0 AND agent_percent < 0 AND payment_status != 'Не оплачен' AND refund_amount != order_amount AND seller = organizer
    GROUP BY seller
    ORDER BY direct_sales DESC
    '''
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    return [
        dict(row) for row in result
    ]
    
def get_seller_events(seller_name, year=None):
    conn = get_db_connection()
    try:
        where_conditions = ["seller = :seller"]
        params = {'seller': seller_name}
        
        if year and year != 'all':
            where_conditions.append("strftime('%Y', event_date) = :year")
            params['year'] = year
        
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        
        query = f"""
        SELECT 
            event_id,
            event_name,
            event_date,
            tickets_sold,
            total_revenue
        FROM events
        {where_clause}
        ORDER BY event_date DESC
        """
        
        result = conn.execute(query, params).fetchall()
        return [dict(row) for row in result]
    finally:
        conn.close()

def create_indexes(conn):
    """Создание всех необходимых индексов"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_seller ON tickets(seller)",
        "CREATE INDEX IF NOT EXISTS idx_order_date ON tickets(order_date)",
        "CREATE INDEX IF NOT EXISTS idx_payment_status ON tickets(payment_status)",
        "CREATE INDEX IF NOT EXISTS idx_agent_amount ON tickets(agent_amount)",
        "CREATE INDEX IF NOT EXISTS idx_system_amount ON tickets(system_amount)",
        "CREATE INDEX IF NOT EXISTS idx_order_id ON tickets(order_id)",
        "CREATE INDEX IF NOT EXISTS idx_import_hash ON import_hashes(hash)"
    ]
    
    for index_sql in indexes:
        conn.execute(index_sql)
    conn.commit()

def optimize_database(conn):
    """Оптимизация базы данных"""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -10000")  # 10MB cache
    conn.execute("VACUUM")
    conn.commit()