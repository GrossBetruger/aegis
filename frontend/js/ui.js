// =============================================
// UI UPDATE FUNCTIONS
// =============================================

function updateTimestamp(timestamp) {
    const el = document.getElementById('lastUpdate');
    const tz = document.getElementById('timezone');

    // Parse timestamp - if ISO string without timezone, treat as UTC (GMT)
    let timestampMs;
    if (typeof timestamp === 'string') {
        // Append 'Z' if no timezone indicator (server saves in GMT)
        const hasTimezone = timestamp.includes('Z') || /[+-]\d{2}:?\d{2}$/.test(timestamp);
        const isoString = hasTimezone ? timestamp : timestamp + 'Z';
        timestampMs = new Date(isoString).getTime();
    } else {
        timestampMs = timestamp;
    }

    const age = Math.floor((Date.now() - timestampMs) / 60000);
    el.textContent = age < 1 ? 'Just now' : `${age} min ago`;

    tz.textContent = getTimezone();
}

function startCountdown() {
    setInterval(() => {
        const nextUpdate = document.getElementById('nextUpdate');
        if (!nextUpdate) return;
        
        const now = new Date();
        const nextHalfHour = new Date(now);
        // Calculate next :00 or :30
        if (now.getMinutes() < 30) {
            nextHalfHour.setMinutes(30, 0, 0);
        } else {
            nextHalfHour.setHours(now.getHours() + 1, 0, 0, 0);
        }
        const diff = nextHalfHour - now;
        const mins = Math.floor(diff / 60000);
        const secs = Math.floor((diff % 60000) / 1000);
        nextUpdate.textContent = `Next update in ${mins}:${secs.toString().padStart(2, '0')}`;
    }, 1000);
}

function updateGauge(score) {
    score = Math.max(0, Math.min(100, Math.round(score)));
    
    // Update gauge fill (SVG arc)
    const gaugeFill = document.getElementById('gaugeFill');
    if (gaugeFill) {
        const offset = 251.2 - (score / 100 * 251.2);
        gaugeFill.style.strokeDashoffset = offset;
        gaugeFill.setAttribute('stroke', getGradient(score));
    }
    
    // Update value display
    const gaugeValue = document.getElementById('gaugeValue');
    if (gaugeValue) {
        gaugeValue.textContent = `${score}%`;
        gaugeValue.className = `gauge-value ${getColor(score)}`;
    }
    
    // Update status label
    const statusLabel = document.getElementById('statusLabel');
    if (statusLabel) {
        statusLabel.textContent = getStatusText(score);
        statusLabel.className = `status-label ${getStatusClass(score)}`;
    }
}

function updateSignal(name, value, detail) {
    const valEl = document.getElementById(`${name}Value`);
    const detailEl = document.getElementById(`${name}Detail`);

    if (name === 'weather') {
        // Good weather = favorable for attack = higher risk
        // Show "Clear" (orange) when good, "Poor" (green) when bad
        const displayText = value > 75 ? 'Clear' : value > 40 ? 'Marginal' : 'Poor';
        valEl.textContent = displayText;
        const weatherColor = value > 75 ? 'var(--orange)' : value > 40 ? 'var(--yellow)' : 'var(--green)';
        valEl.style.color = weatherColor;
        // Update sparkline for weather - Clear (good attack conditions) = high, Poor = low
        const weatherNum = value > 75 ? 100 : value > 40 ? 50 : 20;
        const sparkColor = value > 75 ? '#f97316' : value > 40 ? '#eab308' : '#22c55e';
        updateSparkline(name, weatherNum, sparkColor);
    } else {
        // Display the actual value
        let displayValue = Math.round(value) || 0;
        const colorClass = getColor(displayValue);
        valEl.textContent = `${displayValue}%`;
        valEl.style.color = `var(--${colorClass})`;
        // Update sparkline with color based on value
        const sparkColor = getSparklineColor(displayValue);
        updateSparkline(name, displayValue, sparkColor);
    }
    if (detailEl) detailEl.textContent = detail;
}

function showInfo(type) {
    const modal = document.getElementById('infoModal');
    const title = document.getElementById('infoTitle');
    const content = document.getElementById('infoBody');
    
    const info = INFO_CONTENT[type];
    if (!info) {
        content.innerHTML = 'Information not available.';
    } else if (typeof info === 'object') {
        title.textContent = info.title || 'Signal Info';
        content.innerHTML = info.content;
    } else {
        title.textContent = 'Signal Info';
        content.innerHTML = info;
    }
    
    modal.classList.add('open');
}

function closeInfo(e) { if (!e || e.target.id === 'infoModal') document.getElementById('infoModal').classList.remove('open'); }

function shareSnapshot() {
    const url = 'https://usstrikeradar.com';
    const text = `🚨 StrikeRadar Alert\n\nCurrent Risk Level: ${Math.round(state.currentRisk || 0)}%\nStatus: ${getStatusText(state.currentRisk || 0)}\n\n` +
        `🔗 https://usstrikeradar.com`;
    
    if (navigator.share) {
        navigator.share({ title: 'StrikeRadar', text, url }).catch(() => {});
    } else {
        navigator.clipboard.writeText(text);
        showToast('📋 Snapshot copied to clipboard!');
    }
}
