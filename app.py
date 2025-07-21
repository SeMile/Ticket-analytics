from flask import Flask, render_template, jsonify, request
from flask_caching import Cache
from models.database import db, get_db_connection
from models.queries import (
    get_summary_stats,
    get_top_sellers,
    get_direct_sales,
)
import json

app = Flask(__name__, template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data/tickets.db'
cache = Cache(app)
db.init_app(app)

# Фильтры для Jinja2
@app.template_filter('format_currency')
def format_currency(value):
    """Форматирование числа как денежной суммы"""
    try:
        value = float(value)
        return f"{value:,.0f} ₽".replace(",", " ")
    except (ValueError, TypeError):
        return "0 ₽"

@app.template_filter('format_number')
def format_number(value):
    """Форматирование числа с разделителями тысяч"""
    try:
        return "{:,.0f}".format(float(value)).replace(",", " ")
    except (ValueError, TypeError):
        return "0"
        
# Функция построения SQL-условий WHERE
def build_where_clause(filters):
    
    conditions = []
    params = {}
    
    # Базовое условие (если нужно)
    conditions.append("payment_status != 'Не оплачен'")
    
    # Добавляем фильтр по году
    if filters.get('year'):
        conditions.append("strftime('%Y', order_date) = :year")
        params['year'] = filters['year']
    
    # Фильтр по статусу
    if filters.get('status') and filters['status'] != 'all':
        conditions.append("payment_status = :status")
        params['status'] = filters['status']
    
    # Собираем итоговый запрос
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params

# Распределение заказов или рейсов по временным сегментам дня    
def get_time_segments(column):
    try:
        conn = get_db_connection()
        
        # Утренние (6-12)
        morning = conn.execute(f'''
            SELECT COUNT(*) FROM tickets 
            WHERE {column} >= 6 AND {column} < 12
        ''').fetchone()[0]
        
        # Дневные (12-18)
        day = conn.execute(f'''
            SELECT COUNT(*) FROM tickets 
            WHERE {column} >= 12 AND {column} < 18
        ''').fetchone()[0]
        
        # Вечерние (18-6)
        evening = conn.execute(f'''
            SELECT COUNT(*) FROM tickets 
            WHERE {column} >= 18 OR {column} < 6
        ''').fetchone()[0]
        
        total = morning + day + evening
        conn.close()
        
        return jsonify({
            "segments": [
                {"name": "Утро (06:00-12:00)", "value": morning, "percent": round(morning/total*100, 1), "color": "#FFA07A"},
                {"name": "День (12:00-18:00)", "value": day, "percent": round(day/total*100, 1), "color": "#45B7D1"},
                {"name": "Вечер (18:00-00:00)", "value": evening, "percent": round(evening/total*100, 1), "color": "#9966FF"}
            ],
            "total": total
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/seller')
@cache.cached(timeout=0, query_string=True)
def seller_detail():
    seller_name = request.args.get('name')
    if not seller_name:
        return redirect(url_for('dashboard'))
        
    selected_year = request.args.get('year')
    selected_events = request.args.getlist('events')  # Для множественного выбора
    
    conn = get_db_connection()
    
    # Получаем данные для графиков
    monthly_stats = conn.execute('''
        SELECT 
            strftime('%Y-%m', order_date) as month,
            SUM(order_amount) - SUM(CASE WHEN payment_status = 'Не оплачен' THEN order_amount ELSE 0 END) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) AS revenue,
            SUM(agent_amount) as agent,
            SUM(system_amount) as commission,
            SUM(tickets_count) as orders
        FROM tickets
        WHERE seller = ? AND payment_status != 'Не оплачен' AND refund_amount != order_amount
        GROUP BY month
        ORDER BY month
    ''', (seller_name,)).fetchall()
    
    seller_stats = conn.execute('''
        SELECT 
            seller,
            SUM(order_amount) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) AS total_revenue,
            SUM(agent_amount) as total_agent,
            SUM(system_amount) as total_commission,
            SUM (tickets_count) as total_orders,
            CASE 
                WHEN COUNT(*) > 0 THEN 
                    (SUM(order_amount) - 
                     SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - 
                     SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END)) / 
                    COUNT(DISTINCT order_id)  -- Или COUNT(*) в зависимости от логики
                ELSE 0 
            END AS avg_order,
            COALESCE(SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END), 0) as total_refunds,
            AVG(
                CASE 
                    WHEN payment_status = 'Возвращен' AND refund_amount > 0 
                    THEN refund_amount 
                    ELSE NULL
                END
            ) as avg_refund
        FROM tickets
        WHERE seller = ? AND payment_status != 'Не оплачен' AND refund_amount != order_amount
        GROUP BY seller
    ''', (seller_name,)).fetchone()
    
    refund_stats = conn.execute('''
        SELECT 
            COALESCE(SUM(refund_amount), 0) as total_refunds,
            COUNT(*) as refund_count
        FROM tickets
        WHERE seller = ?
        AND refund_amount > 0
        AND payment_status IN ('Возвращен')
    ''', (seller_name,)).fetchone()
    
    monthly_trend = conn.execute('''
        SELECT 
            strftime('%Y-%m', order_date) as month,
            SUM(agent_amount) as agent_amount
        FROM tickets
        WHERE seller = ?
        GROUP BY strftime('%Y-%m', order_date)
        ORDER BY month  -- Сортировка от старых к новым
    ''', (seller_name,)).fetchall()
    
    # Получаем список всех продавцов
    all_sellers = conn.execute('''
        SELECT DISTINCT seller FROM tickets WHERE seller != ? ORDER BY seller
    ''', (seller_name,)).fetchall()
    
    # Новый запрос для таблицы событий
    seller_events = conn.execute('''
        SELECT 
            event_name,
            SUM(tickets_count) as tickets_count,
            SUM(order_amount) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) as order_amount,
            SUM(agent_amount) as agent_amount,
            SUM(system_amount) as system_amount
        FROM tickets
        WHERE seller = ? AND payment_status != 'Не оплачен' AND refund_amount != order_amount
        GROUP BY event_name
        ORDER BY agent_amount DESC  -- Сортировка по комиссии агента
    ''', (seller_name,)).fetchall()
    
    # Базовый запрос для фильтров
    base_query = '''
        SELECT 
            event_name,
            strftime('%Y', order_date) as year,
            SUM(tickets_count) as tickets_count,
            SUM(order_amount) - SUM(CASE WHEN payment_status = 'Не оплачен' THEN order_amount ELSE 0 END) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) as order_amount,
            SUM(agent_amount) as agent_amount,
            SUM(system_amount) as system_amount
        FROM tickets
        WHERE seller = ? AND payment_status != 'Не оплачен' AND refund_amount != order_amount
    '''
    
    # Формируем условия фильтрации
    conditions = []
    params = [seller_name]
    
    if selected_year and selected_year != 'all':
        conditions.append("strftime('%Y', order_date) = ?")
        params.append(selected_year)
    
    if selected_events:
        placeholders = ','.join(['?'] * len(selected_events))
        conditions.append(f"event_name IN ({placeholders})")
        params.extend(selected_events)
    
    # Запрос для получения событий (с фильтрами)
    events_query = base_query
    if conditions:
        events_query += " AND " + " AND ".join(conditions)
    events_query += " GROUP BY event_name ORDER BY agent_amount DESC"
    
    seller_events = conn.execute(events_query, params).fetchall()
    
    # Запрос для получения доступных годов
    years = conn.execute('''
        SELECT DISTINCT strftime('%Y', order_date) as year 
        FROM tickets 
        WHERE seller = ?
        ORDER BY year DESC
    ''', (seller_name,)).fetchall()
    
    # Запрос для получения доступных событий (в зависимости от выбранного года)
    events_filter_query = '''
        SELECT DISTINCT event_name 
        FROM tickets 
        WHERE seller = ?
    '''
    events_params = [seller_name]
    
    if selected_year and selected_year != 'all':
        events_filter_query += " AND strftime('%Y', order_date) = ?"
        events_params.append(selected_year)
    
    available_events = conn.execute(events_filter_query, events_params).fetchall()
    
    conn.close()
    
    if not seller_stats:
        return render_template('error.html', message='Продавец не найден'), 404
    
    # Подготовка данных для графика
    trend_labels = [row['month'] for row in monthly_trend]
    trend_data = [row['agent_amount'] or 0 for row in monthly_trend] 
    all_sellers = [row['seller'] for row in all_sellers]
    
    return render_template('seller_detail.html',
        seller_name=seller_name,
        stats=dict(seller_stats),
        total_refunds=refund_stats['total_refunds'],
        trend_labels=trend_labels,
        trend_data=trend_data,
        seller_events=[dict(row) for row in seller_events],
        available_years=[row['year'] for row in years],
        available_events=[row['event_name'] for row in available_events],
        selected_year=selected_year,
        selected_events=selected_events,        
        all_sellers=all_sellers
    )

@app.route('/seller-events-filter')
def seller_events_filter():
    seller_name = request.args.get('seller')
    year = request.args.get('year')
    
    conn = get_db_connection()
    
    query = '''
        SELECT DISTINCT event_name 
        FROM tickets 
        WHERE seller = ?
    '''
    params = [seller_name]
    
    if year and year != 'all':
        query += " AND strftime('%Y', order_date) = ?"
        params.append(year)
    
    events = conn.execute(query, params).fetchall()
    conn.close()
    
    return jsonify({
        'events': [row['event_name'] for row in events]
    })

# API

@app.route('/api/summary')
@cache.cached(timeout=60)
def summary():
    try:
        filters = {
            'year': request.args.get('year'),
            'status': request.args.get('status')
        }
        
        where_clause, params = build_where_clause(filters)
        
        query = f"""
        SELECT 
            SUM(order_amount) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) AS total_revenue,
            SUM(agent_amount) as total_agent,
            SUM(system_amount) as total_commission,
            SUM(tickets_count) 
            - SUM(CASE WHEN payment_status = 'Возвращен' THEN tickets_count ELSE 0 END)
            - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN tickets_count ELSE 0 END)
            - SUM(CASE WHEN organizer = seller AND agent_percent < 0 AND payment_status = 'Оплачен' AND agent_amount = 0 THEN tickets_count ELSE 0 END)
            AS total_orders,
            CASE 
                WHEN COUNT(*) > 0 THEN 
                    (SUM(order_amount) - 
                     SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - 
                     SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END)) / 
                    COUNT(DISTINCT order_id)  -- Или COUNT(*) в зависимости от логики
                ELSE 0 
            END AS avg_order,
            COALESCE(
                SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END)
                - SUM(CASE WHEN payment_status = 'Возвращен' AND organizer = seller AND agent_percent < 0 THEN refund_amount ELSE 0 END)
            , 0) as total_refunds,
            AVG(
                CASE 
                    WHEN payment_status = 'Возвращен' AND refund_amount > 0 
                    THEN refund_amount 
                    ELSE NULL
                END
            ) as avg_refund
        FROM tickets
        {where_clause}
        """
        
        conn = get_db_connection()
        result = conn.execute(query, params).fetchone()
        conn.close()
        
        return jsonify({
            'total_revenue': result['total_revenue'] or 0,
            'total_agent': result['total_agent'] or 0,
            'total_commission': result['total_commission'] or 0,
            'total_orders': result['total_orders'] or 0,
            'avg_order': result['avg_order'] or 0,
            'total_refunds': result['total_refunds'] or 0,
            'avg_refund': result['avg_refund'] or 0
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/top-sellers')
@cache.cached(timeout=60, query_string=True)
def top_sellers():
    try:
        filters = {
            'year': request.args.get('year'),
            'status': request.args.get('status')
        }
        
        # Базовые условия
        conditions = ["agent_amount > 0"]
        params = {}
        
        # Добавляем фильтры
        if filters.get('year') and filters['year'] != 'all':
            conditions.append("strftime('%Y', order_date) = :year")
            params['year'] = filters['year']
        
        if filters.get('status') and filters['status'] != 'all':
            conditions.append("payment_status = :status")
            params['status'] = filters['status']
        
        # Формируем WHERE-часть
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
        SELECT 
            seller as seller,
            SUM(agent_amount) as agent_amount,
            SUM(system_amount) as system_amount,
            SUM(tickets_count) as orders_count
        FROM tickets
        {where_clause}
        GROUP BY seller
        ORDER BY agent_amount DESC
        LIMIT 20
        """
        
        conn = get_db_connection()
        result = conn.execute(query, params).fetchall()
        conn.close()
        
        return jsonify([dict(row) for row in result])
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/direct-sales')
@cache.cached(timeout=60)
def direct_sales():
    data = get_direct_sales()
    return jsonify(data)

@app.route('/api/sales-trend')
@cache.cached(timeout=60)
def sales_trend():
    try:
        conn = get_db_connection()
        
        # Получаем данные по месяцам
        result = conn.execute('''
            SELECT 
                strftime('%Y-%m', order_date) as month,
                SUM(agent_amount) as agent_amount,
                SUM(system_amount) as system_amount
            FROM tickets
            GROUP BY strftime('%Y-%m', order_date)
            ORDER BY month
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            "labels": [row['month'] for row in result],
            "datasets": [
                {
                    "label": "Agent Revenue",
                    "data": [row['agent_amount'] or 0 for row in result]
                },
                {
                    "label": "System Commission", 
                    "data": [row['system_amount'] or 0 for row in result]
                }
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/all-agents')
@cache.cached(timeout=0)
def all_agents():
    try:
        conn = get_db_connection()
        result = conn.execute('''
            SELECT 
                seller as seller,
                SUM(agent_amount) as agent_amount,
                SUM(system_amount) as system_amount,
                COUNT(*) as orders_count,
                SUM(tickets_count) as tickets_count,
                SUM(order_amount) - SUM(CASE WHEN payment_status = 'Не оплачен' THEN order_amount ELSE 0 END) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) as total_revenue
            FROM tickets
            WHERE payment_status != 'Не оплачен' AND refund_amount != order_amount AND agent_amount > 0
            GROUP BY seller
            ORDER BY agent_amount DESC
        ''').fetchall()
        conn.close()
        return jsonify([dict(row) for row in result])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/booking-segments')
@cache.cached(timeout=60)
def booking_segments():
    return get_time_segments('booking_hour')

@app.route('/api/flight-segments')
@cache.cached(timeout=60)
def flight_segments():
    return get_time_segments('flight_hour')

@app.route('/api/years')
@cache.cached(timeout=3600)
def get_years():
    conn = get_db_connection()
    years = conn.execute('''
        SELECT DISTINCT strftime('%Y', order_date) as year 
        FROM tickets 
        ORDER BY year DESC
    ''').fetchall()
    conn.close()
    return jsonify([row['year'] for row in years])

@app.route('/api/statuses')
@cache.cached(timeout=3600)
def get_statuses():
    conn = get_db_connection()
    statuses = conn.execute('''
        SELECT DISTINCT payment_status as status 
        FROM tickets 
        WHERE payment_status IS NOT NULL 
          AND payment_status != ''
          AND payment_status != 'Не оплачен'
    ''').fetchall()
    conn.close()
    return jsonify([row['status'] for row in statuses if row['status']])
    
@app.route('/api/sellers')
def get_sellers_list():
    conn = get_db_connection()
    sellers = conn.execute('SELECT DISTINCT seller FROM tickets ORDER BY seller').fetchall()
    conn.close()
    return jsonify([row['seller'] for row in sellers])

@app.route('/api/compare-sellers', methods=['POST'])
def compare_sellers():
    try:
        sellers = request.json.get('sellers', [])
        if not sellers or len(sellers) > 5:
            return jsonify({"error": "Выберите от 1 до 5 продавцов"}), 400
        
        conn = get_db_connection()
        
        # Данные для сравнения
        comparison_data = []
        for seller in sellers:
            stats = conn.execute('''
                SELECT 
                    seller,
                    SUM(order_amount) - SUM(CASE WHEN payment_status = 'Не оплачен' THEN order_amount ELSE 0 END) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) as revenue,
                    SUM(agent_amount) as agent,
                    SUM(system_amount) as commission,
                    SUM(tickets_count) as orders,
                    AVG(order_amount) as avg_order
                FROM tickets
                WHERE seller = ? AND payment_status != 'Не оплачен' AND refund_amount != order_amount
                GROUP BY seller
            ''', (seller,)).fetchone()
            
            if stats:
                comparison_data.append(dict(stats))
        
        conn.close()
        return jsonify(comparison_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route('/api/seller-trend')
def seller_trend_api():
    seller_name = request.args.get('seller')
    year = request.args.get('year', 'all')
    status = request.args.get('status', 'all')
    
    if not seller_name:
        return jsonify({"error": "Seller name is required"}), 400
    
    try:
        conn = get_db_connection()
        
        # Базовые условия
        conditions = ["seller = ?"]
        params = [seller_name]
        
        # Добавляем фильтры
        if year != 'all':
            conditions.append("strftime('%Y', order_date) = ?")
            params.append(year)
        
        if status != 'all':
            conditions.append("payment_status = ?")
            params.append(status)
        
        # Формируем WHERE-часть
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
        SELECT 
            strftime('%Y-%m', order_date) as period,
            SUM(agent_amount) as agent_amount
        FROM tickets
        {where_clause}
        GROUP BY strftime('%Y-%m', order_date)
        ORDER BY period
        """
        
        result = conn.execute(query, params).fetchall()
        conn.close()
        
        return jsonify({
            'labels': [row['period'] for row in result],
            'datasets': [{
                'data': [row['agent_amount'] or 0 for row in result]
            }]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/seller-stats')
def seller_stats():
    seller_name = request.args.get('seller')
    year = request.args.get('year', 'all')
    status = request.args.get('status', 'all')
    
    if not seller_name:
        return jsonify({"error": "Seller name is required"}), 400
    
    try:
        conn = get_db_connection()
        
        # Базовые условия
        conditions = ["seller = ? AND payment_status != 'Не оплачен'"]
        params = [seller_name]
        
        # Добавляем фильтры
        if year != 'all':
            conditions.append("strftime('%Y', order_date) = ?")
            params.append(year)
        
        if status != 'all':
            conditions.append("payment_status = ?")
            params.append(status)
        
        # Формируем WHERE-часть
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
        SELECT 
            SUM(order_amount) - SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END) AS total_revenue,
            SUM(agent_amount) as total_agent,
            SUM(system_amount) as total_commission,
            SUM(tickets_count) 
            - SUM(CASE WHEN payment_status = 'Возвращен' THEN tickets_count ELSE 0 END)
            - SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN tickets_count ELSE 0 END)
            - SUM(CASE WHEN organizer = seller AND agent_percent < 0 AND payment_status = 'Оплачен' AND agent_amount = 0 THEN tickets_count ELSE 0 END)
            AS total_orders,
            CASE 
                WHEN COUNT(*) > 0 THEN 
                    (SUM(order_amount) - 
                     SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END) - 
                     SUM(CASE WHEN agent_amount = 0 AND agent_percent > 0 AND payment_status = 'Оплачен' THEN order_amount ELSE 0 END)) / 
                    COUNT(DISTINCT order_id)  -- Или COUNT(*) в зависимости от логики
                ELSE 0 
            END AS avg_order,
            COALESCE(
                SUM(CASE WHEN payment_status = 'Возвращен' THEN refund_amount ELSE 0 END)
                - SUM(CASE WHEN payment_status = 'Возвращен' AND organizer = seller AND agent_percent < 0 THEN refund_amount ELSE 0 END)
            , 0) as total_refunds
        FROM tickets
        {where_clause}
        """
        
        result = conn.execute(query, params).fetchone()
        conn.close()
        
        return jsonify(dict(result))
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)