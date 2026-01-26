// =============================================
// DATA DISPLAY LOGIC
// =============================================

// Display data on the dashboard
function displayData(data) {
    console.log('Displaying data:', data);
    
    // Load signal history from data.json
    if (data?.signalHistory) {
        console.log('Loading signalHistory:', Object.keys(data.signalHistory).map(k => `${k}: ${data.signalHistory[k]?.length || 0} points`).join(', '));
        ['news', 'social', 'flight', 'tanker', 'pentagon', 'polymarket', 'weather'].forEach(sig => {
            if (data.signalHistory[sig] && data.signalHistory[sig].length > 0) {
                state.signalHistory[sig] = data.signalHistory[sig];
            }
        }); 
    }

    // Get all pre-calculated signal values from backend
    const calculated = data.calculated_signals || {};
    
    // Display all signals using pre-calculated values (NO CALCULATIONS HERE!)
    if (calculated.news) {
        updateSignal('news', calculated.news.risk, calculated.news.detail);
    }
    
    if (calculated.flight) {
        updateSignal('flight', calculated.flight.risk, calculated.flight.detail);
    }
    
    if (calculated.tanker) {
        updateSignal('tanker', calculated.tanker.risk, calculated.tanker.detail);
    }
    
    if (calculated.weather) {
        updateSignal('weather', calculated.weather.risk, calculated.weather.detail);
    }
    
    // Polymarket signal
    if (calculated.polymarket) {
        const polymarketOdds = data.polymarket?.odds || 0;
        const isValidData = polymarketOdds > 0 && polymarketOdds <= 95;
        
        updateSignal('polymarket', calculated.polymarket.risk, calculated.polymarket.detail);
        setStatus('polymarketStatus', isValidData);
        
        // Add feed alert for high odds
        if (polymarketOdds > 30 && polymarketOdds <= 95) {
            const marketTitle = data.polymarket?.market || 'Iran strike';
            addFeed('MARKET', `📊 Polymarket: ${polymarketOdds}% odds on "${marketTitle.substring(0, 40)}"`, true, 'Alert');
        }
    }
    
    // Pentagon signal
    if (calculated.pentagon) {
        updateSignal('pentagon', calculated.pentagon.risk, calculated.pentagon.detail);
        
        // Check if pentagon data is fresh (less than 40 minutes old)
        let pentagonTimestamp = 0;
        if (data.pentagon?.timestamp) {
            pentagonTimestamp = new Date(data.pentagon.timestamp).getTime();
        } else if (data.pentagon_updated) {
            pentagonTimestamp = new Date(data.pentagon_updated).getTime();
        } else if (data.timestamp) {
            pentagonTimestamp = data.timestamp;
        }
        
        const pentagonAge = Date.now() - pentagonTimestamp;
        const isPentagonFresh = (pentagonTimestamp > 0 && pentagonAge < 40 * 60 * 1000) ||
                                (data.pentagon?.status && data.pentagon?.score !== undefined);
        
        setStatus('pentagonStatus', isPentagonFresh);
        
        // Add feed alert for high activity
        const pentagonContribution = data.pentagon?.risk_contribution || 0;
        if (pentagonContribution >= 7) {
            addFeed('PENTAGON', `🍕 High activity detected near Pentagon`, true, 'Alert');
        }
    }
    
    // Display total risk (pre-calculated)
    const total = calculated.total_risk || 0;
    
    // Add escalation alert if needed
    if (calculated.elevated_count >= 3) {
        addFeed('SYSTEM', 'Multiple elevated signals detected - escalation multiplier applied', true, 'Alert');
    }

    updateGauge(total);
    updateTimestamp(data.timestamp);

    return total;
}
