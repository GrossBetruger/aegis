// =============================================
// MAIN CONTROLLER
// =============================================

// Load and display data from data.json
async function loadData() {
    const data = await getData();
    
    if (data) {
        displayData(data, true);
        updateChartFromHistory(data.history);
    }
}

async function forceRefresh() {
    showToast('🔄 Refreshing data...');
    await loadData();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Load data and initialize
    const data = await getData();
    initChart(data?.history);
    
    startCountdown();
    await loadData();

    // Update every 5 minutes
    setInterval(loadData, 5 * 60 * 1000);

    // Online/offline handlers
    window.addEventListener('online', () => {
        showToast('✅ Connection restored');
        loadData();
    });
    window.addEventListener('offline', updateOnlineStatus);
});
