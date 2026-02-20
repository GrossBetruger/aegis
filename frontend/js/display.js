// =============================================
// DATA DISPLAY LOGIC
// =============================================

// Parse ISO timestamp as UTC (server saves in GMT without 'Z' suffix)
function parseUtcTimestamp(timestamp) {
    if (!timestamp) return 0;
    if (typeof timestamp === 'number') return timestamp;
    // Append 'Z' if no timezone indicator to treat as UTC
    const hasTimezone = timestamp.includes('Z') || /[+-]\d{2}:?\d{2}$/.test(timestamp);
    return new Date(hasTimezone ? timestamp : timestamp + 'Z').getTime();
}

// Display data on the dashboard
function displayData(data) {
    console.log('Displaying data:', data);
    
    // Load signal history from restructured data
    ['news', 'flight', 'tanker', 'pentagon', 'polymarket', 'weather', 'oil', 'trends', 'buildup'].forEach(sig => {
        if (data[sig] && data[sig].history && data[sig].history.length > 0) {
            state.signalHistory[sig] = data[sig].history;
        }
    });

    // Display all signals using pre-calculated values from restructured data
    if (data.buildup) {
        updateSignal('buildup', data.buildup.risk, data.buildup.detail);
        const hasBuildupData = data.buildup.raw_data?.risk !== undefined;
        setStatus('buildupStatus', hasBuildupData);
    }

    if (data.news) {
        updateSignal('news', data.news.risk, data.news.detail);
    }
    
    if (data.flight) {
        updateSignal('flight', data.flight.risk, data.flight.detail);
    }
    
    if (data.tanker) {
        updateSignal('tanker', data.tanker.risk, data.tanker.detail);
    }
    
    if (data.weather) {
        updateSignal('weather', data.weather.risk, data.weather.detail);
    }
    
    // Polymarket signal
    if (data.polymarket) {
        const polymarketOdds = data.polymarket.raw_data?.odds || 0;
        const isValidData = polymarketOdds > 0 && polymarketOdds <= 95;
        
        updateSignal('polymarket', data.polymarket.risk, data.polymarket.detail);
        setStatus('polymarketStatus', isValidData);
    }
    
    // Pentagon signal
    if (data.pentagon) {
        updateSignal('pentagon', data.pentagon.risk, data.pentagon.detail);
        
        // Check if pentagon data is fresh (less than 40 minutes old)
        let pentagonTimestamp = 0;
        if (data.pentagon.raw_data?.timestamp) {
            pentagonTimestamp = parseUtcTimestamp(data.pentagon.raw_data.timestamp);
        } else if (data.last_updated) {
            pentagonTimestamp = parseUtcTimestamp(data.last_updated);
        }
        
        const pentagonAge = Date.now() - pentagonTimestamp;
        const isPentagonFresh = (pentagonTimestamp > 0 && pentagonAge < 40 * 60 * 1000) ||
                                (data.pentagon.raw_data?.status && data.pentagon.raw_data?.score !== undefined);
        
        setStatus('pentagonStatus', isPentagonFresh);
    }
    
    // Oil prices signal
    if (data.oil) {
        updateSignal('oil', data.oil.risk, data.oil.detail);
        const hasOilData = data.oil.raw_data?.current_price > 0;
        setStatus('oilStatus', hasOilData);
    }
    
    
    // Google Trends signal
    if (data.trends) {
        updateSignal('trends', data.trends.risk, data.trends.detail);
        const hasTrendsData = data.trends.raw_data?.current_interest >= 0;
        setStatus('trendsStatus', hasTrendsData);
    }
    
    // Display total risk (pre-calculated)
    const total = data.total_risk?.risk || 0;

    updateGauge(total);
    updateTimestamp(data.last_updated ? parseUtcTimestamp(data.last_updated) : Date.now());

    return total;
}
