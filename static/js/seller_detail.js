let sellerFilters = {
    year: 'all',
    status: 'all'
};

function initChart() {
    const ctx = document.getElementById('salesTrend');
    if (!ctx) return;
    
    // Удаляем старый график
    if (window.salesChart) {
        window.salesChart.destroy();
    }
    
    // Формируем URL с учетом фильтров
    const params = new URLSearchParams();
    if (sellerFilters.year !== 'all') params.append('year', sellerFilters.year);
    if (sellerFilters.status !== 'all') params.append('status', sellerFilters.status);
    
    const url = `/api/seller-trend?seller=${encodeURIComponent(window.sellerName)}&${params.toString()}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            window.salesChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Агентское вознаграждение',
                        data: data.datasets[0].data,
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13, 110, 253, 0.1)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: (context) => 
                                    `${context.dataset.label}: ${formatCurrency(context.raw)}`
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        },
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: (value) => formatCurrency(value)
                            }
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error loading chart data:', error);
            showError('Ошибка загрузки данных графика');
        });
}

// Добавим новую функцию для загрузки данных с фильтрами
function loadSellerData() {
    const params = new URLSearchParams();
    params.append('seller', window.sellerName);
    if (sellerFilters.year !== 'all') params.append('year', sellerFilters.year);
    if (sellerFilters.status !== 'all') params.append('status', sellerFilters.status);
    
    fetch(`/api/seller-stats?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            // Обновляем карточки с данными
            document.getElementById('seller-total-agent').textContent = formatCurrency(data.total_agent);
            document.getElementById('seller-total-commission').textContent = formatCurrency(data.total_commission);
            document.getElementById('seller-avg-order').textContent = formatCurrency(data.avg_order);
            document.getElementById('seller-total-revenue').textContent = formatCurrency(data.total_revenue);
            document.getElementById('seller-total-refunds').textContent = formatCurrency(data.total_refunds);
            document.getElementById('seller-total-orders').textContent = data.total_orders;
            
            // Обновляем график
            initChart();
        })
        .catch(error => {
            console.error('Error loading seller data:', error);
            showError('Ошибка загрузки данных продавца');
        });
}

// Добавим обработчики фильтров
function setupSellerFilters() {
    const yearFilter = document.getElementById('sellerYearFilter');
    const statusFilter = document.getElementById('sellerStatusFilter');
    const applyBtn = document.getElementById('applySellerFilters');
    
    if (!yearFilter || !statusFilter || !applyBtn) return;
    
    // Восстановим сохраненные фильтры
    const savedFilters = JSON.parse(localStorage.getItem(`sellerFilters_${window.sellerName}`) || '{}');
    if (savedFilters.year) {
        yearFilter.value = savedFilters.year;
        sellerFilters.year = savedFilters.year;
    }
    if (savedFilters.status) {
        statusFilter.value = savedFilters.status;
        sellerFilters.status = savedFilters.status;
    }
    
    applyBtn.addEventListener('click', () => {
        sellerFilters = {
            year: yearFilter.value,
            status: statusFilter.value
        };
        
        // Сохраняем фильтры
        localStorage.setItem(`sellerFilters_${window.sellerName}`, JSON.stringify(sellerFilters));
        
        // Загружаем данные с новыми фильтрами
        loadSellerData();
    });
}

function setupComparison() {
    const select = document.getElementById('compare-sellers');
    const button = document.getElementById('compare-button');
    
    if (!select || !button) return;

    button.addEventListener('click', async () => {
        const selected = Array.from(select.selectedOptions).map(opt => opt.value);
        
        if (selected.length === 0) {
            showError('Выберите минимум одного продавца');
            return;
        }
        
        try {
            const response = await fetch('/api/compare-sellers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sellers: selected })
            });
            
            if (!response.ok) throw new Error('Ошибка сервера');
            
            const data = await response.json();
            renderComparisonResults(data);
        } catch (error) {
            showError('Ошибка при сравнении: ' + error.message);
            console.error('Ошибка:', error);
        }
    });
}

function renderComparisonResults(data) {
    const container = document.getElementById('comparison-results');
    if (!container) return;

    if (!data || data.length === 0) {
        container.innerHTML = '<div class="alert alert-info">Нет данных для отображения</div>';
        return;
    }

    let html = '<div class="table-responsive"><table class="table table-bordered">';
    html += '<thead><tr><th>Метрика</th>';
    
    data.forEach(seller => {
        html += `<th>${seller.seller}</th>`;
    });
    html += '</tr></thead><tbody>';

    const metrics = [
        { key: 'revenue', label: 'Выручка' },
        { key: 'agent', label: 'Агентское вознаграждение' },
        { key: 'commission', label: 'Комиссия системы' },
        { key: 'orders', label: 'Количество заказов' },
        { key: 'avg_order', label: 'Средний чек' }
    ];

    metrics.forEach(metric => {
        html += `<tr><td>${metric.label}</td>`;
        data.forEach(seller => {
            const value = seller[metric.key] || 0;
            html += `<td>${metric.key.includes('orders') ? value : formatCurrency(value)}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

// Утилитная функция для форматирования валюты
function formatCurrency(value) {
    if (isNaN(value)) return '0 ₽';
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 0
    }).format(value).replace('₽', '₽');
}

document.addEventListener('DOMContentLoaded', function() {
    // Обработчик изменения года
    document.getElementById('yearFilter').addEventListener('change', function() {
        updateEventsFilter();
    });
    
    // Инициализация фильтров
    if (document.getElementById('eventsFilterForm')) {
        updateEventsFilter();
    }
});

function updateEventsFilter() {
    const year = document.getElementById('yearFilter').value;
    const sellerName = new URLSearchParams(window.location.search).get('name');
    
    fetch(`/seller-events-filter?seller=${encodeURIComponent(sellerName)}&year=${year}`)
        .then(response => response.json())
        .then(data => {
            const eventsSelect = document.getElementById('eventsFilter');
            eventsSelect.innerHTML = '';
            
			[...data.events]  // Создаем копию
			.sort((a, b) => a.localeCompare(b))  // Сортируем копию
			.forEach(event => {
				const option = document.createElement('option');
				option.value = event;
				option.textContent = event;
				eventsSelect.appendChild(option);
			});

        });
}

document.addEventListener('DOMContentLoaded', () => {
    // Получаем имя продавца из URL
    const urlParams = new URLSearchParams(window.location.search);
    window.sellerName = urlParams.get('name');
    
    if (!window.sellerName) {
        showError('Не указан продавец');
        return;
    }
    
    setupSellerFilters();
    initChart();
    setupComparison();
    loadSellerData();
});