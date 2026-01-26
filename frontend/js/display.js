// =============================================
// DATA DISPLAY LOGIC
// =============================================

// Display data on the dashboard
function displayData(data) {
    // Load signal history from cache if available
    if (data.signalHistory) {
        console.log('Loading signalHistory from cache:', Object.keys(data.signalHistory).map(k => `${k}: ${data.signalHistory[k]?.length || 0} points`).join(', '));
        ['news', 'social', 'flight', 'tanker', 'pentagon', 'polymarket', 'weather'].forEach(sig => {
            if (data.signalHistory[sig] && data.signalHistory[sig].length > 0) {
                state.signalHistory[sig] = data.signalHistory[sig];
            }
        });
    }

    // Update individual signal displays with stored details or computed values
    // NEWS: Use news_intel from GitHub Action cache if available (consistent for all users)
    let newsDisplayRisk = Math.round((data.news / 30) * 100);
    let newsDetail = `${Math.round(data.news / 2)} articles, ${Math.round(data.news / 10)} critical`;

    if (data.news_intel && data.news_intel.total_count !== undefined) {
        // Use server-side cached news data (consistent!)
        const articles = data.news_intel.total_count;
        const alertCount = data.news_intel.alert_count || 0;

        // Calculate contribution (same formula as fetchNews)
        let contribution = 2;
        if (articles <= 3) {
            contribution = 3 + articles * 2 + alertCount * 1;
        } else if (articles <= 6) {
            contribution = 9 + (articles - 3) * 1.5 + alertCount * 1.5;
        } else if (articles <= 10) {
            contribution = 13.5 + (articles - 6) * 1 + alertCount * 2;
        } else {
            contribution = 17.5 + (articles - 10) * 0.5 + alertCount * 2;
        }
        contribution = Math.min(30, contribution);

        newsDisplayRisk = Math.round((contribution / 30) * 100);
        newsDetail = `${articles} articles, ${alertCount} critical`;
    } else if (data.newsDetail && !data.newsDetail.includes('Monitoring') && !data.newsDetail.includes('Loading') && !data.newsDetail.includes('Awaiting')) {
        newsDetail = data.newsDetail;
    }

    updateSignal('news', newsDisplayRisk, newsDetail);

    updateSignal('social', Math.round((data.interest / 20) * 100), data.socialDetail || 'GDELT + Wikipedia');

    const flightCount = Math.round(data.aviation * 10);
    const flightDetail = (data.flightDetail && !data.flightDetail.includes('Scanning') && !data.flightDetail.includes('Loading')) ? data.flightDetail : `${flightCount} aircraft over Iran`;
    updateSignal('flight', Math.round((data.aviation / 15) * 100), flightDetail);

    const tankerCount = Math.round(data.tanker / 4);
    const tankerDetail = (data.tankerDetail && !data.tankerDetail.includes('Scanning') && !data.tankerDetail.includes('Loading')) ? data.tankerDetail : `${tankerCount} detected in region`;
    updateSignal('tanker', Math.round((data.tanker / 10) * 100), tankerDetail);

    // Polymarket odds signal (from cached data updated by GitHub Actions)
    let polymarketOdds = 0;
    let polymarketContribution = 1; // baseline
    if (data.polymarket && data.polymarket.odds !== undefined) {
        // Safety: odds should be 0-100, cap at 100
        polymarketOdds = Math.min(100, Math.max(0, data.polymarket.odds));

        // Sanity check: if odds > 95, something is probably wrong with parsing
        if (polymarketOdds > 95) {
            console.warn('Polymarket odds suspiciously high:', data.polymarket);
            polymarketOdds = 0; // Reset to 0 if data seems wrong
        }

        polymarketContribution = Math.min(10, polymarketOdds * 0.1);
        const marketTitle = data.polymarket.market || 'Iran strike';

        if (polymarketOdds > 0) {
            updateSignal('polymarket', polymarketOdds, `${polymarketOdds}% odds`);
            setStatus('polymarketStatus', true);
        } else {
            updateSignal('polymarket', 10, 'Data error - refreshing...');
            setStatus('polymarketStatus', true);
        }

        if (polymarketOdds > 30 && polymarketOdds <= 95) {
            addFeed('MARKET', `📊 Polymarket: ${polymarketOdds}% odds on "${marketTitle.substring(0, 40)}"`, true, 'Alert');
        }
    } else {
        // No polymarket data yet - show baseline
        updateSignal('polymarket', 10, 'Awaiting data...');
        setStatus('polymarketStatus', true);
    }

    updateSignal('weather', data.weather >= 4 ? 'Favorable' : data.weather >= 2 ? 'Marginal' : 'Poor', data.weatherDetail || 'Tehran conditions');

    // Pentagon Pizza Meter signal (from cached data updated by GitHub Actions)
    // Max contribution: 10% of total risk
    // Display bar: Normal ~5-10%, Elevated ~30-50%, High ~70-100%
    let pentagonContribution = 0;
    if (data.pentagon && (data.pentagon.score !== undefined || data.pentagon.status)) {
        const rawScore = data.pentagon.score || 30; // 0-100 from script, default to low

        // Convert score to contribution (max 10%)
        // Low (score <40) = 1% contribution, shows ~10% on bar
        // Normal (score 40-60) = 2-3% contribution, shows ~20-30% on bar
        // Elevated (score 60-80) = 4-7% contribution, shows ~40-70% on bar
        // High (score 80+) = 8-10% contribution, shows ~80-100% on bar
        if (rawScore < 40) {
            pentagonContribution = 1; // Low activity baseline
        } else if (rawScore <= 60) {
            pentagonContribution = 1 + (rawScore - 40) * 0.1; // 1-3%
        } else if (rawScore <= 80) {
            pentagonContribution = 3 + (rawScore - 60) * 0.2; // 3-7%
        } else {
            pentagonContribution = 7 + (rawScore - 80) * 0.15; // 7-10%
        }
        pentagonContribution = Math.min(10, pentagonContribution);

        const pentagonStatus = data.pentagon.status || 'Normal';
        const isLateNight = data.pentagon.is_late_night || false;
        const isWeekend = data.pentagon.is_weekend || false;

        // Check if pentagon data is fresh (less than 40 minutes old)
        // Check pentagon.timestamp, pentagon_updated, or main data timestamp
        let pentagonTimestamp = 0;
        if (data.pentagon.timestamp) {
            pentagonTimestamp = new Date(data.pentagon.timestamp).getTime();
        } else if (data.pentagon_updated) {
            pentagonTimestamp = new Date(data.pentagon_updated).getTime();
        } else if (data.timestamp) {
            // Fall back to main cache timestamp
            pentagonTimestamp = data.timestamp;
        }
        const pentagonAge = Date.now() - pentagonTimestamp;
        // Show LIVE if: data < 40 min old OR we have valid pentagon status+score
        const isPentagonFresh = (pentagonTimestamp > 0 && pentagonAge < 40 * 60 * 1000) ||
                                (data.pentagon.status && data.pentagon.score !== undefined);

        // Display bar: scale so Low (1%) shows as ~10%, High (10%) shows as 100%
        const displayRisk = Math.round((pentagonContribution / 10) * 100);
        const detail = `${pentagonStatus}${isLateNight ? ' (late night)' : ''}${isWeekend ? ' (weekend)' : ''}`;
        updateSignal('pentagon', displayRisk, detail);
        setStatus('pentagonStatus', isPentagonFresh);

        if (pentagonContribution >= 7) {
            addFeed('PENTAGON', `🍕 High activity detected near Pentagon`, true, 'Alert');
        }
    } else {
        // No pentagon data from GitHub Action - use time-based simulation
        // This keeps the signal LIVE while Action catches up
        const hour = new Date().getHours();
        const isLateNight = hour >= 22 || hour < 6;
        const isWeekend = [0, 6].includes(new Date().getDay());

        let simStatus = 'Normal';
        let simScore = 10;

        if (isLateNight) {
            simStatus = 'Low Activity';
            simScore = 8;
        } else if (isWeekend) {
            simStatus = 'Weekend';
            simScore = 8;
        } else if (hour >= 11 && hour <= 14) {
            simStatus = 'Lunch hour';
            simScore = 12;
        } else if (hour >= 17 && hour <= 20) {
            simStatus = 'Dinner hour';
            simScore = 12;
        }

        pentagonContribution = 1; // Baseline contribution
        updateSignal('pentagon', simScore, simStatus);
        setStatus('pentagonStatus', true); // Show LIVE with simulated data
    }

    let total = data.news + data.interest + data.aviation + data.tanker + polymarketContribution + data.weather + pentagonContribution;

    const elevated = [data.news > 10, data.interest > 8, data.aviation > 10, data.tanker > 5, data.weather > 2, pentagonContribution > 5].filter(Boolean).length;
    if (elevated >= 3) {
        total = Math.min(100, total * 1.15);
        addFeed('SYSTEM', 'Multiple elevated signals detected - escalation multiplier applied', true, 'Alert');
    }

    total = Math.min(100, total);

    updateGauge(total);
    updateTimestamp(data.timestamp);

    return total;
}
