document.addEventListener('DOMContentLoaded', () => {
    // Инициализация темы
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            themeToggle.innerHTML = newTheme === 'dark' 
                ? '<i class="bi bi-sun-fill"></i>' 
                : '<i class="bi bi-moon-fill"></i>';
        });

        // Восстановление темы
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-bs-theme', savedTheme);
        themeToggle.innerHTML = savedTheme === 'dark' 
            ? '<i class="bi bi-sun-fill"></i>' 
            : '<i class="bi bi-moon-fill"></i>';
    }
});

// Обновляем showError для Bootstrap
function showError(message) {
    const toastHtml = `
        <div class="toast show align-items-center text-white bg-danger border-0 position-fixed top-0 end-0 m-3" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', toastHtml);
    setTimeout(() => document.querySelector('.toast').remove(), 5000);
}

// Основные функции обновления интерфейса

function updateSummaryCards(data) {
    if (!data || data.error) {
        console.error('Invalid summary data:', data);
        return;
    }

    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    };

    setValue('total-commission', formatCurrency(data.total_commission || 0));
    setValue('total-agent', formatCurrency(data.total_agent || 0));
    setValue('avg-order', formatCurrency(data.avg_order || 0));
    setValue('total-revenue', formatCurrency(data.total_revenue || 0));
    setValue('total-refunds', formatCurrency(data.total_refunds || 0));
    setValue('avg-refund', formatCurrency(data.avg_refund || 0));
}

function updateTopSellersTable(data) {
    const tbody = document.querySelector('#topSellersTable tbody');
    if (!tbody || !data || data.error) return;
    
    const totalAgent = data.reduce((sum, seller) => sum + seller.agent_amount, 0);
    
    tbody.innerHTML = data.map((seller, index) => {
        const share = totalAgent > 0 ? (seller.agent_amount / totalAgent * 100) : 0;
        return `
            <tr>
                <td>${index + 1}</td>
                <td title="${seller.seller}"><a href="/seller?name=${encodeURIComponent(seller.seller)}" class="seller-link">${truncateText(seller.seller, 30)}</a></td>
                <td>${formatCurrency(seller.agent_amount)}</td>
                <td>${formatCurrency(seller.system_amount)}</td>
                <td>
                    <div>${share.toFixed(1)}%</div>
                    <div class="percentage-bar-container">
                        <div class="percentage-bar" style="width: ${share}%"></div>
                    </div>
                </td>
                <td>${seller.orders_count}</td>
            </tr>
        `;
    }).join('');
}

function updateDirectSalesTable(data) {
    const tbody = document.querySelector('#directSalesTable tbody');
    if (!tbody || !data || data.error) return;
    
    const totalSales = data.reduce((sum, seller) => sum + seller.direct_sales, 0);
    
    tbody.innerHTML = data.map((seller, index) => {
        const share = totalSales > 0 ? (seller.direct_sales / totalSales * 100) : 0;
        return `
            <tr>
                <td>${index + 1}</td>
                <td title="${seller.seller}">${truncateText(seller.seller, 30)}</td>
                <td>${formatCurrency(seller.direct_sales)}</td>
                <td>${formatCurrency(seller.system_commission)}</td>
                <td>
                    <div>${share.toFixed(1)}%</div>
                    <div class="percentage-bar-container">
                        <div class="percentage-bar" style="width: ${share}%"></div>
                    </div>
                </td>
                <td>${seller.orders_count}</td>
                <td>${formatCurrency(seller.total_revenue)}</td>
            </tr>
        `;
    }).join('');
}

function updateAllAgentsTable(data) {
    const tbody = document.querySelector('#allAgentsTable tbody');
    if (!tbody || !data || data.error) return;
    
    tbody.innerHTML = data.map((agent, index) => {
        const segmentClass = getSegmentClass(agent.agent_amount);
        const segmentColor = getSegmentColor(agent.agent_amount);
        
        return `
            <tr class="${segmentClass}">
                <td>${index + 1}</td>
                <td title="${agent.seller}">
                    <span class="segment-indicator" style="background-color: ${segmentColor}"></span>
                    <a href="/seller?name=${encodeURIComponent(agent.seller)}" class="seller-link">${truncateText(agent.seller, 30)}</a>
                </td>
                <td>${formatCurrency(agent.agent_amount)}</td>
                <td>${formatCurrency(agent.system_amount)}</td>
                <td>${agent.orders_count}</td>
                <td>${agent.tickets_count}</td>
                <td>${formatCurrency(agent.total_revenue)}</td>
            </tr>
        `;
    }).join('');
}

function updateTimeSegments(type, data) {
    const container = document.getElementById(`${type}-segments-container`);
    if (!container || !data || data.error) return;
    
    container.innerHTML = data.segments.map(segment => `
        <div class="time-segment-card" style="--time-segment-color: ${segment.color}">
            <div class="time-segment-title">${segment.name}</div>
            <div class="time-segment-value">${segment.value} ${type === 'booking' ? 'заказов' : 'рейсов'}</div>
            <div class="time-segment-bar-container">
                <div>Доля: ${segment.percent}%</div>
                <div class="time-segment-bar">
                    <div class="time-segment-fill" style="width: ${segment.percent}%"></div>
                </div>
            </div>
        </div>
    `).join('');
}

// Вспомогательные функции

function formatCurrency(value) {
    if (isNaN(value)) return '0 ₽';
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 0
    }).format(value).replace('₽', '₽');
}

function truncateText(text, maxLength) {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

function getSegmentClass(amount) {
    if (!window.globalSegmentBounds) return '';
    if (amount < window.globalSegmentBounds[1]) return 'segment-low';
    if (amount < window.globalSegmentBounds[2]) return 'segment-medium';
    if (amount < window.globalSegmentBounds[3]) return 'segment-high';
    return 'segment-premium';
}

function getSegmentColor(amount) {
    if (!window.globalSegmentBounds) return '#ccc';
    if (amount < window.globalSegmentBounds[1]) return '#FF6384';
    if (amount < window.globalSegmentBounds[2]) return '#36A2EB';
    if (amount < window.globalSegmentBounds[3]) return '#FFCE56';
    return '#4BC0C0';
}

function showLoader() {
    const loader = document.getElementById('loader');
    if (loader) loader.style.display = 'flex';
    const dashboard = document.getElementById('dashboard');
    if (dashboard) dashboard.style.display = 'none';
}

function hideLoader() {
    const loader = document.getElementById('loader');
    if (loader) loader.style.display = 'none';
    const dashboard = document.getElementById('dashboard');
    if (dashboard) dashboard.style.display = 'block';
}

function showError(message) {
    console.error(message);
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    document.body.prepend(errorDiv);
    setTimeout(() => errorDiv.remove(), 5000);
}

// Основная функция загрузки данных

async function loadDashboardData() {
    try {
        showLoader();
        
        const queryParams = new URLSearchParams();
        if (currentFilters.year !== 'all') queryParams.append('year', currentFilters.year);
        if (currentFilters.status !== 'all') queryParams.append('status', currentFilters.status);
        
        const urls = [
            `/api/summary?${queryParams}`,
            `/api/top-sellers?${queryParams}`,
            `/api/direct-sales?${queryParams}`,
            `/api/sales-trend?${queryParams}`,
            `/api/all-agents?${queryParams}`,
            `/api/booking-segments?${queryParams}`,
            `/api/flight-segments?${queryParams}`
        ];
        
        const results = await Promise.all(
            urls.map(url => fetch(url).then(res => res.json()))
        );
        
        // Сохраняем границы сегментов для подсветки
        if (results[4] && !results[4].error) {
            const amounts = results[4].map(a => a.agent_amount).sort((a, b) => a - b);
            window.globalSegmentBounds = [
                0,
                amounts[Math.floor(amounts.length * 0.25)],
                amounts[Math.floor(amounts.length * 0.5)],
                amounts[Math.floor(amounts.length * 0.75)],
                Infinity
            ];
        }
        
        updateSummaryCards(results[0]);
        updateTopSellersTable(results[1]);
        updateDirectSalesTable(results[2]);
        initCharts(results[3]);
        updateAllAgentsTable(results[4]);
        updateTimeSegments('booking', results[5]);
        updateTimeSegments('flight', results[6]);
        
    } catch (error) {
        showError('Ошибка загрузки данных: ' + error.message);
        console.error('Error details:', error);
    } finally {
        hideLoader();
    }
}

// Инициализация графиков
function initCharts(data) {
    if (!data || data.error) {
        console.error('Invalid chart data:', data);
        return;
    }

    // График агентского вознаграждения
    renderChart('agentTrend', {
        labels: data.labels,
        datasets: [{
            label: 'Агентское вознаграждение',
            data: data.datasets[0].data,
            backgroundColor: 'rgba(54, 162, 235, 0.7)',
            borderColor: 'rgba(54, 162, 235, 1)',
            fill: true,
            tension: 0.3
        }]
    }, 'Динамика агентского вознаграждения по месяцам');

    // График комиссии системы
    renderChart('commissionTrend', {
        labels: data.labels,
        datasets: [{
            label: 'Комиссия системы',
            data: data.datasets[1].data,
            backgroundColor: 'rgba(255, 99, 132, 0.7)',
            borderColor: 'rgba(255, 99, 132, 1)',
            fill: true,
            tension: 0.3
        }]
    }, 'Динамика комиссии системы по месяцам');
}

// Универсальная функция для рендеринга графиков
function renderChart(canvasId, chartData, title) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // Удаляем старый график, если существует
    if (window[canvasId + 'Chart']) {
        window[canvasId + 'Chart'].destroy();
    }

    window[canvasId + 'Chart'] = new Chart(ctx, {
        type: 'bar',
        data: chartData,
        options: {
            responsive: true,
			maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: title,
                    font: {
                        size: 14,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${formatCurrency(context.raw)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            }
        }
    });
}

// Глобальные переменные для фильтров
let currentFilters = {
    year: 'all',
    status: 'all'
};

// Функция загрузки фильтров
async function loadFilters() {
    try {
        // Загрузка доступных годов
        const yearsResponse = await fetch('/api/years');
        if (!yearsResponse.ok) throw new Error('Ошибка загрузки годов');
        const years = await yearsResponse.json();
        
        const yearSelect = document.getElementById('year');
        if (yearSelect) {
            years.forEach(year => {
                const option = document.createElement('option');
                option.value = year;
                option.textContent = year;
                yearSelect.appendChild(option);
            });
        }

        // Загрузка доступных статусов
        const statusesResponse = await fetch('/api/statuses');
        if (!statusesResponse.ok) throw new Error('Ошибка загрузки статусов');
        const statuses = await statusesResponse.json();
        
        const statusSelect = document.getElementById('status');
        if (statusSelect) {
            statuses.forEach(status => {
                const option = document.createElement('option');
                option.value = status;
                option.textContent = status;
                statusSelect.appendChild(option);
            });
        }

        // Обработчик применения фильтров
        const applyBtn = document.getElementById('apply-filters');
        if (applyBtn) {
            applyBtn.addEventListener('click', applyFilters);
        }
    } catch (error) {
        console.error('Error loading filters:', error);
        showError('Ошибка загрузки фильтров');
    }
}

// Функция применения фильтров
function applyFilters() {
    currentFilters = {
        year: document.getElementById('year').value,
        status: document.getElementById('status').value
    };
    
    loadDashboardData();
}

// Инициализация при загрузке страницы

document.addEventListener('DOMContentLoaded', () => {
    loadFilters().then(loadDashboardData);
	// Проверяем, что все необходимые элементы существуют
    if (document.getElementById('dashboard')) {
        loadDashboardData();
    }
});