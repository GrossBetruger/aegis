// =============================================
// UI UPDATE FUNCTIONS
// =============================================

function updateTimestamp(cacheTimestamp = null) {
    const el = document.getElementById('lastUpdate');
    const tz = document.getElementById('timezone');
    
    if (cacheTimestamp) {
        const age = Math.floor((Date.now() - cacheTimestamp) / 60000);
        el.textContent = age < 1 ? 'Just now' : `${age} min ago`;
    } else {
        el.textContent = formatTime();
    }
    
    tz.textContent = getTimezone();
}

function startCountdown() {
    setInterval(() => {
        const now = new Date();
        const nextHour = new Date(now);
        nextHour.setHours(now.getHours() + 1, 0, 0, 0);
        const diff = nextHour - now;
        const mins = Math.floor(diff / 60000);
        const secs = Math.floor((diff % 60000) / 1000);
        document.getElementById('countdown').textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
    }, 1000);
}

function updateGauge(score) {
    const needle = document.querySelector('.gauge-needle');
    const value = document.querySelector('.gauge-value');
    const statusText = document.getElementById('statusText');
    const container = document.querySelector('.gauge-container');
    
    const degrees = -90 + (score / 100) * 180;
    needle.style.transform = `translateX(-50%) rotate(${degrees}deg)`;
    value.textContent = Math.round(score);
    statusText.textContent = getStatusText(score);
    container.className = `gauge-container ${getStatusClass(score)}`;
}

function updateSignal(name, value, detail, addToHistory = false) {
    const valEl = document.getElementById(`${name}Value`);
    const detailEl = document.getElementById(`${name}Detail`);

    if (name === 'weather') {
        // Good weather = favorable for attack = higher risk
        // Show "Clear" (orange) when good, "Poor" (green) when bad
        const displayText = value === 'Favorable' ? 'Clear' : value === 'Marginal' ? 'Marginal' : 'Poor';
        valEl.textContent = displayText;
        const weatherColor = value === 'Favorable' ? 'var(--orange)' : value === 'Marginal' ? 'var(--yellow)' : 'var(--green)';
        valEl.style.color = weatherColor;
        // Update sparkline for weather - Clear (good attack conditions) = high, Poor = low
        const weatherNum = value === 'Favorable' ? 100 : value === 'Marginal' ? 50 : 20;
        const sparkColor = value === 'Favorable' ? '#f97316' : value === 'Marginal' ? '#eab308' : '#22c55e';
        updateSparkline(name, weatherNum, sparkColor, addToHistory);
    } else {
        // Deterministic jitter for signal display - all users see same
        let displayValue = Math.round(value) || 0;
        const seed = Math.floor(Date.now() / (30 * 60 * 1000));
        const signalIndex = { news: 10, social: 11, flight: 12 }[name] || 13;
        const jitterVal = Math.floor(seededRandom(seed, signalIndex) * 5) - 2;
        displayValue = Math.max(0, Math.min(100, displayValue + jitterVal));
        const colorClass = getColor(displayValue);
        valEl.textContent = `${displayValue}%`;
        valEl.style.color = `var(--${colorClass})`;
        // Update sparkline with color based on value
        const sparkColor = getSparklineColor(displayValue);
        updateSparkline(name, displayValue, sparkColor, addToHistory);
    }
    if (detailEl) detailEl.textContent = detail;
}

function addFeed(source, text, isAlert = false, badge = null) {
    const key = text.substring(0, 50).toLowerCase();
    if (state.seenHeadlines.has(key)) return;
    state.seenHeadlines.add(key);

    const item = { source, text, isAlert, badge, time: formatTime() };
    state.feedItems.unshift(item);
    if (state.feedItems.length > 20) state.feedItems.pop();
    renderFeed();
}

function renderFeed() {
    const list = document.getElementById('feedList');
    const btn = document.getElementById('showMoreBtn');
    const expanded = list.classList.contains('expanded');
    const items = expanded ? state.feedItems : state.feedItems.slice(0, 3);

    list.innerHTML = items.map(i => `
        <div class="feed-item${i.isAlert ? ' alert' : ''}">
            <span class="feed-source">${i.source}</span>
            ${i.badge ? `<span class="feed-badge">${i.badge}</span>` : ''}
            <span class="feed-text">${i.text}</span>
            <span class="feed-time">${i.time}</span>
        </div>
    `).join('');

    btn.textContent = expanded ? 'Show Less' : `Show More (${state.feedItems.length - 3})`;
    btn.style.display = state.feedItems.length > 3 ? 'block' : 'none';
}

function toggleFeed() {
    document.getElementById('feedList').classList.toggle('expanded');
    renderFeed();
}

function showInfo(type) {
    const modal = document.getElementById('infoModal');
    const content = document.getElementById('infoContent');
    content.innerHTML = INFO_CONTENT[type] || 'Information not available.';
    modal.classList.add('open');
}

function closeInfo(e) { if (!e || e.target.id === 'infoModal') document.getElementById('infoModal').classList.remove('open'); }

function shareSnapshot() {
    const url = 'https://backyonatan-alt.github.io/strikeradar';
    const text = `🚨 StrikeRadar Alert\n\nCurrent Risk Level: ${Math.round(state.currentRisk || 0)}%\nStatus: ${getStatusText(state.currentRisk || 0)}\n\n` +
        `🔗 https://backyonatan-alt.github.io/strikeradar`;
    
    if (navigator.share) {
        navigator.share({ title: 'StrikeRadar', text, url }).catch(() => {});
    } else {
        navigator.clipboard.writeText(text);
        showToast('📋 Snapshot copied to clipboard!');
    }
}
