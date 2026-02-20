// =============================================
// CHART MANAGEMENT
// =============================================

let chart = null;

function initChart(historyData = null) {
    // Create chart if it doesn't exist yet
    if (!chart) {
        const ctx = document.getElementById('trendChart').getContext('2d');
        
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: state.trendLabels,
                datasets: [{
                    label: 'Risk Level',
                    data: state.trendData,
                    borderColor: '#f97316',
                    backgroundColor: 'rgba(249, 115, 22, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#f97316',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: { size: 13 },
                        bodyFont: { size: 14 },
                        callbacks: {
                            label: (context) => `Risk: ${context.parsed.y}%`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: (value) => value + '%',
                            color: 'rgba(255, 255, 255, 0.6)',
                            font: { size: 11 }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                            drawBorder: false
                        }
                    },
                    x: {
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.6)',
                            font: { size: 11 },
                            maxRotation: 0
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                            drawBorder: false
                        }
                    }
                }
            }
        });
    }

    // Update with history data if provided
    if (historyData) {
        updateChartData(historyData);
    }
}

// Update chart with real history data only
function updateChartData(history) {
    if (!chart) return;

    state.trendLabels = [];
    state.trendData = [];

    // Only use real data from history array
    if (!history || history.length === 0) {
        console.log('No history data available for chart');
        chart.data.labels = [];
        chart.data.datasets[0].data = [];
        chart.update('none');
        return;
    }

    console.log(`Rendering chart with ${history.length} real data points`);

    // Sort by timestamp
    const sortedHistory = [...history].sort((a, b) => a.timestamp - b.timestamp);

    // Build chart from real data only
    sortedHistory.forEach((point, i) => {
        const d = new Date(point.timestamp);
        const dateStr = formatDate(d);
        const hourStr = d.getHours().toString().padStart(2, '0') + ':' + 
                       d.getMinutes().toString().padStart(2, '0');

        // Label - show date for first point or when date changes
        let label;
        if (i === sortedHistory.length - 1) {
            label = 'Now';
        } else if (i === 0 || formatDate(new Date(sortedHistory[i-1].timestamp)) !== dateStr) {
            label = dateStr;
        } else {
            label = hourStr;
        }

        state.trendLabels.push(label);
        state.trendData.push(point.risk);
    });

    // Update chart
    chart.data.labels = state.trendLabels;
    chart.data.datasets[0].data = state.trendData;
    chart.update('none');
}
