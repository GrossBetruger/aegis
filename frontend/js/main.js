// =============================================
// MAIN CONTROLLER
// =============================================

// Load and display data from data.json
async function loadData() {
    const data = await getData();
    
    if (data) {
        initChart(data.total_risk?.history); // Pass restructured history
        displayData(data);
    }
}

async function forceRefresh() {
    showToast('🔄 Refreshing data...');
    await loadData();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    startCountdown();
    await loadData(); // Single source of truth

    // Update every 5 minutes
    setInterval(loadData, 5 * 60 * 1000);

    // Online/offline handlers
    window.addEventListener('online', () => {
        showToast('✅ Connection restored');
        loadData();
    });
    window.addEventListener('offline', updateOnlineStatus);
});
