// =============================================
// DATA DISPLAY LOGIC
// =============================================

// Display data on the dashboard
function displayData(data) {
    console.log('Displaying data:', data);
    
    // Load signal history from restructured data
    ['news', 'flight', 'tanker', 'pentagon', 'polymarket', 'weather'].forEach(sig => {
        if (data[sig] && data[sig].history && data[sig].history.length > 0) {
            state.signalHistory[sig] = data[sig].history;
        }
    });

    // Display all signals using pre-calculated values from restructured data
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
        
        // Add feed alert for high odds
        if (polymarketOdds > 30 && polymarketOdds <= 95) {
            const marketTitle = data.polymarket.raw_data?.market || 'Iran strike';
            addFeed('MARKET', `📊 Polymarket: ${polymarketOdds}% odds on "${marketTitle.substring(0, 40)}"`, true, 'Alert');
        }
    }
    
    // Pentagon signal
    if (data.pentagon) {
        updateSignal('pentagon', data.pentagon.risk, data.pentagon.detail);
        
        // Check if pentagon data is fresh (less than 40 minutes old)
        let pentagonTimestamp = 0;
        if (data.pentagon.raw_data?.timestamp) {
            pentagonTimestamp = new Date(data.pentagon.raw_data.timestamp).getTime();
        } else if (data.last_updated) {
            pentagonTimestamp = new Date(data.last_updated).getTime();
        }
        
        const pentagonAge = Date.now() - pentagonTimestamp;
        const isPentagonFresh = (pentagonTimestamp > 0 && pentagonAge < 40 * 60 * 1000) ||
                                (data.pentagon.raw_data?.status && data.pentagon.raw_data?.score !== undefined);
        
        setStatus('pentagonStatus', isPentagonFresh);
        
        // Add feed alert for high activity
        const pentagonContribution = data.pentagon.raw_data?.risk_contribution || 0;
        if (pentagonContribution >= 7) {
            addFeed('PENTAGON', `🍕 High activity detected near Pentagon`, true, 'Alert');
        }
    }
    
    // Display total risk (pre-calculated)
    const total = data.total_risk?.risk || 0;
    
    // Add escalation alert if needed
    if (data.total_risk?.elevated_count >= 3) {
        addFeed('SYSTEM', 'Multiple elevated signals detected - escalation multiplier applied', true, 'Alert');
    }

    updateGauge(total);
    updateTimestamp(new Date(data.last_updated)).getTime();

    return total;
}
