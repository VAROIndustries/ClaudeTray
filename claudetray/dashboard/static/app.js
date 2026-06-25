document.addEventListener('DOMContentLoaded', function() {
    // Gauge charts on index page
    if (document.getElementById('chart-5h')) {
        initGauges();
        initHistoryChart();
        initResetTimers();
        setInterval(refreshState, 10000);
    }

    // Settings form
    const form = document.getElementById('settings-form');
    if (form) {
        form.addEventListener('submit', saveSettings);
    }
});

function pctColor(pct) {
    if (pct >= 80) return '#ef4444';
    if (pct >= 60) return '#eab308';
    return '#22c55e';
}

function initGauges() {
    createGauge('chart-5h', state.five_hour_pct || 0);
    createGauge('chart-7d', state.seven_day_pct || 0);
}

function createGauge(canvasId, pct) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [pct, 100 - pct],
                backgroundColor: [pctColor(pct), '#2a2a4a'],
                borderWidth: 0,
            }]
        },
        options: {
            cutout: '75%',
            responsive: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            rotation: -90,
            circumference: 360,
        }
    });
}

function initHistoryChart() {
    const ctx = document.getElementById('history-chart');
    if (!ctx || !snapshots || snapshots.length === 0) return;

    const labels = snapshots.map(s => {
        const d = new Date(s.timestamp);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    });

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '5-Hour',
                    data: snapshots.map(s => s.five_hour_pct),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59,130,246,0.1)',
                    fill: true,
                    tension: 0.3,
                },
                {
                    label: '7-Day',
                    data: snapshots.map(s => s.seven_day_pct),
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139,92,246,0.1)',
                    fill: true,
                    tension: 0.3,
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: { min: 0, max: 100, grid: { color: '#2a2a4a' }, ticks: { color: '#888' } },
                x: { grid: { color: '#2a2a4a' }, ticks: { color: '#888', maxTicksLimit: 12 } },
            },
            plugins: {
                legend: { labels: { color: '#e0e0e0' } },
            },
        }
    });
}

function initResetTimers() {
    updateResetTimer('reset-5h', state.five_hour_resets_at);
    updateResetTimer('reset-7d', state.seven_day_resets_at);
    setInterval(function() {
        updateResetTimer('reset-5h', state.five_hour_resets_at);
        updateResetTimer('reset-7d', state.seven_day_resets_at);
    }, 1000);
}

function updateResetTimer(elementId, resetEpoch) {
    const el = document.getElementById(elementId);
    if (!el || !resetEpoch) { if (el) el.textContent = ''; return; }
    const now = Math.floor(Date.now() / 1000);
    const diff = resetEpoch - now;
    if (diff <= 0) { el.textContent = 'Resetting...'; return; }
    const h = Math.floor(diff / 3600);
    const m = Math.floor((diff % 3600) / 60);
    el.textContent = 'Resets in ' + h + 'h ' + m + 'm';
}

function refreshState() {
    fetch('/api/state')
        .then(r => r.json())
        .then(data => {
            document.getElementById('val-5h').textContent = Math.round(data.five_hour_pct) + '%';
            document.getElementById('val-7d').textContent = Math.round(data.seven_day_pct) + '%';
            state.five_hour_resets_at = data.five_hour_resets_at;
            state.seven_day_resets_at = data.seven_day_resets_at;
        })
        .catch(() => {});
}

function saveSettings(e) {
    e.preventDefault();
    const data = {
        run_on_startup: document.getElementById('run_on_startup').checked,
        refresh_interval_active: parseInt(document.getElementById('refresh_interval_active').value),
        refresh_interval_idle: parseInt(document.getElementById('refresh_interval_idle').value),
        api_key: document.getElementById('api_key').value || null,
        dashboard_port: parseInt(document.getElementById('dashboard_port').value),
        theme: document.getElementById('theme').value,
        data_retention_days: parseInt(document.getElementById('data_retention_days').value),
    };
    fetch('/api/settings', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
    })
    .then(r => r.json())
    .then(() => {
        document.getElementById('save-status').textContent = 'Settings saved!';
        setTimeout(() => document.getElementById('save-status').textContent = '', 3000);
    });
}
