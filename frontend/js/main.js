// =============================================
// MAIN CONTROLLER
// =============================================

// MASTER CALCULATION - checks cache first, only calls APIs if cache is old
async function calculate() {
    const now = Date.now();

    // Try JSONbin cache first
    let cached = await getCache();

    // If JSONbin failed, try localStorage backup
    if (!cached) {
        try {
            const local = localStorage.getItem('strikeradar_cache');
            if (local) {
                cached = JSON.parse(local);
                console.log('Using localStorage backup cache');
            }
        } catch (e) { }
    }

    // If cache exists and is less than 30 minutes old, use it
    if (cached && cached.timestamp && (now - cached.timestamp) < CACHE_DURATION) {
        console.log('Using cached data (age: ' + Math.round((now - cached.timestamp) / 60000) + ' min)');
        const total = displayData(cached, true);
        updateChartFromHistory(cached.history);
        return;
    }

    // If cache exists but is old (30-60 min), still use it but don't call APIs
    // This prevents excessive API calls - only refresh every 60 min max
    if (cached && cached.timestamp && (now - cached.timestamp) < 60 * 60 * 1000) {
        console.log('Using slightly stale cache to preserve API quota (age: ' + Math.round((now - cached.timestamp) / 60000) + ' min)');
        const total = displayData(cached, true);
        updateChartFromHistory(cached.history);
        return;
    }

    // SAFETY CHECK: Don't call APIs more than once per hour per browser
    const lastCall = localStorage.getItem('strikeradar_last_api_call');
    if (lastCall && (now - parseInt(lastCall)) < MIN_API_INTERVAL) {
        console.log('API rate limit protection - using stale cache or defaults');
        if (cached) {
            const total = displayData(cached, true);
            updateChartFromHistory(cached.history);
        } else {
            // Show default values if no cache at all (don't add to history)
            updateSignal('news', 10, 'Waiting for data...', false);
            updateSignal('social', 8, 'Waiting for data...', false);
            updateSignal('flight', 12, 'Waiting for data...', false);
            updateSignal('weather', 'Unknown', 'Waiting for data...', false);
            updateGauge(15);
        }
        return;
    }

    // Cache is very old or doesn't exist - fetch fresh data
    console.log('Loading data from data.json...');

    // Mark API call time BEFORE calling (prevents race conditions)
    localStorage.setItem('strikeradar_last_api_call', now.toString());

    const freshData = await fetchFreshData();

    // Display the data (treating as cached since we're just reading data.json)
    const total = displayData(freshData, true);

    // Update localStorage as backup
    try {
        localStorage.setItem('strikeradar_cache', JSON.stringify(freshData));
    } catch (e) { }

    // Update chart from history
    updateChartFromHistory(freshData.history);
}

async function forceRefresh() {
    localStorage.removeItem('strikeradar_last_api_call');
    localStorage.removeItem('strikeradar_cache');
    showToast('🔄 Force refreshing data...');
    await calculate();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Load history first for chart
    const cached = await getCache();
    initChart(cached?.history);

    // Start countdown and run initial calculation
    startCountdown();
    await calculate();

    // Update every 5 minutes
    setInterval(calculate, 5 * 60 * 1000);

    // Online/offline handlers
    window.addEventListener('online', () => {
        showToast('✅ Connection restored');
        calculate();
    });
    window.addEventListener('offline', updateOnlineStatus);
});
