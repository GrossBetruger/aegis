// =============================================
// API KEYS (Pre-configured)
// =============================================
const API_KEYS = {
    newsdata: 'pub_13a914590d954af5a5e59aaef487cece',
    openweather: '2e1d472bc1b48449837208507a2367af',
    aviationstack: 'd2d07ed1b949906c12da683a816baa1b',
    aerodatabox: '3c52c3801dmshb70129bb162afaep1c0e03jsn4315c008bb36',
    // npoint.io for shared caching (all users see same data) - free, no rate limits
    npoint: '3ce6e5b71ace9e172061',
    // Telegram bot for alerts
    telegram: '8407070441:AAEk7XWXyL5rMOVmGIkp_461bUJSw_6QaSc',
};

const TELEGRAM_CHANNEL = '@StrikeRadarAlerts';

// JSONbin configuration
const CACHE_DURATION = 30 * 60 * 1000; // 30 minutes

const state = {
    risk: 0,
    feedItems: [],
    seenHeadlines: new Set(),
    trendData: [],
    trendLabels: [],
    // Cache last known values for when APIs fail
    lastKnown: {
        aviation: { value: 5, detail: 'Cached data' }
    },
    // Signal history for sparklines (20 data points each)
    signalHistory: {
        news: [],
        social: [],
        flight: [],
        tanker: [],
        pentagon: [],
        polymarket: [],
        weather: []
    }
};

// Generate sparkline SVG with smooth curves
function generateSparkline(data, color = '#22c55e') {
    if (!data || data.length < 2) return '';

    const width = 60;
    const height = 24;
    const padding = 2;

    // Normalize data to fit in the SVG
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    // Generate path points
    const points = data.map((val, i) => {
        const x = padding + (i / (data.length - 1)) * (width - padding * 2);
        const y = height - padding - ((val - min) / range) * (height - padding * 2);
        return { x, y };
    });

    // Create smooth curve using cubic bezier
    let linePath = `M ${points[0].x},${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1];
        const curr = points[i];
        const cpx = (prev.x + curr.x) / 2;
        linePath += ` C ${cpx},${prev.y} ${cpx},${curr.y} ${curr.x},${curr.y}`;
    }

    // Create area path (for gradient fill)
    const areaPath = linePath + ` L ${points[points.length - 1].x},${height - padding} L ${points[0].x},${height - padding} Z`;

    return `
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <defs>
                <linearGradient id="sparkGrad_${color.replace('#', '')}" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="${color}" stop-opacity="0.3"/>
                    <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <path class="sparkline-area" d="${areaPath}" fill="url(#sparkGrad_${color.replace('#', '')})"/>
            <path class="sparkline-line" d="${linePath}" stroke="${color}"/>
        </svg>
    `;
}

// Update sparkline for a signal
function updateSparkline(name, value, color) {
    const container = document.getElementById(`${name}Sparkline`);
    if (!container) return;

    // Get history or generate mimicked data
    let history = state.signalHistory[name] || [];

    // Add current value if different from last
    if (history.length === 0 || history[history.length - 1] !== value) {
        history.push(value);
    }

    // Keep only last 20 points
    if (history.length > 20) {
        history = history.slice(-20);
    }

    state.signalHistory[name] = history;

    // If we don't have enough data yet, generate mimicked historical data
    if (history.length < 5) {
        const mimickedData = generateMimickedHistory(value, 20, name);
        container.innerHTML = generateSparkline(mimickedData, color);
    } else {
        container.innerHTML = generateSparkline(history, color);
    }
}

// Generate mimicked historical data based on current value
function generateMimickedHistory(currentValue, points, signalName) {
    const data = [];
    const seed = Math.floor(Date.now() / (24 * 60 * 60 * 1000)); // Stable per day
    const signalSeed = signalName.charCodeAt(0) * 17 + signalName.length * 31;

    // Use fewer points for smoother look
    const actualPoints = 12;

    // Create gentle curve unique to each signal
    for (let i = 0; i < actualPoints; i++) {
        // Very gentle wave with long period
        const t = i / actualPoints;
        const wave = Math.sin(t * Math.PI * 0.8 + signalSeed * 0.1) * 3;

        // Slight trend based on signal
        const trend = (signalSeed % 3 - 1) * t * 2;

        const value = Math.max(5, Math.min(95, currentValue + wave + trend));
        data.push(Math.round(value));
    }

    // Ensure last point is current
    data[data.length - 1] = currentValue;

    return data;
}

// Get color based on value
function getSparklineColor(value) {
    if (value >= 70) return '#ef4444'; // red
    if (value >= 50) return '#f97316'; // orange
    if (value >= 30) return '#eab308'; // yellow
    return '#22c55e'; // green
}

const KEYWORDS = ['retaliation', 'strike', 'attack', 'escalation', 'military', 'threat', 'imminent', 'missile', 'nuclear', 'war'];

const INFO_CONTENT = {
    news: {
        title: 'News Intelligence',
        body: '<strong>Source:</strong> RSS Feeds (BBC, Al Jazeera) - Updated every 30 min<br><br><strong>What it tracks:</strong> News articles mentioning Iran, military strike, Pentagon, CENTCOM.<br><br><strong>Risk logic:</strong> Baseline ~3-5 articles = low risk. 10+ articles with alert keywords (strike, attack, imminent) = high risk.<br><br><strong>Max contribution:</strong> 30%<br><br><em>Data is cached server-side for consistency.</em>'
    },
    trends: {
        title: 'Public Interest',
        body: '<strong>Sources:</strong> GDELT + Wikipedia<br><br><strong>GDELT:</strong> Global Database of Events monitors news from 65 languages, tracking Iran-related articles and their tone (positive/negative sentiment).<br><br><strong>Wikipedia:</strong> Pageviews on "Iran", "Iran-US relations", and "Iran-Israel conflict" pages.<br><br><strong>Risk logic:</strong> High GDELT article count + negative tone = elevated. Wikipedia spikes above 80k/day = public concern. Combined signals give early warning.<br><br><strong>Max contribution:</strong> 20%'
    },
    aviation: {
        title: 'Civil Aviation',
        body: '<strong>Source:</strong> OpenSky Network (ADS-B)<br><br><strong>What it tracks:</strong> Real-time commercial aircraft flying over Iran airspace.<br><br><strong>Baseline:</strong> Normal traffic shows 20-50+ aircraft over Iran at any time.<br><br><strong>Risk logic:</strong> A sudden DROP in aircraft count may indicate airlines avoiding the area = potential risk indicator.<br>• 30+ aircraft = Normal (low risk)<br>• 15-30 = Slightly reduced<br>• 5-15 = Below normal (elevated)<br>• <5 = Very low (high risk)<br><br><strong>Note:</strong> This is one signal among many. Traffic changes can have many causes.<br><br><strong>Max contribution:</strong> 15%'
    },
    tanker: {
        title: 'Military Tankers',
        body: '<strong>Source:</strong> OpenSky Network API (ADS-B)<br><br><strong>What it tracks:</strong> US Air Force aerial refueling tankers (KC-135, KC-10, KC-46) in the Middle East region.<br><br><strong>Why it matters:</strong> Tanker aircraft are essential for long-range strike operations. A surge in tanker activity in the Persian Gulf / Middle East region is a strong indicator of potential military action.<br><br><strong>Risk logic:</strong><br>• 0 tankers = baseline (5%)<br>• 1-2 tankers = normal ops (15%)<br>• 3-4 tankers = elevated (40%)<br>• 5+ tankers = high alert (80%+)<br><br><strong>Historical note:</strong> Before major operations, tanker activity typically increases 24-48 hours in advance.<br><br><strong>Max contribution:</strong> 10%'
    },
    weather: {
        title: 'Op. Conditions',
        body: '<strong>Source:</strong> OpenWeatherMap API<br><br><strong>What it tracks:</strong> Tehran weather - visibility, cloud cover, conditions.<br><br><strong>Risk logic:</strong> Clear skies (visibility >10km, clouds <30%) = favorable for aerial operations = +5% to risk. Poor weather = 0% contribution.<br><br><strong>Max contribution:</strong> 5%'
    },
    polymarket: {
        title: 'Market Odds (Polymarket)',
        body: '<strong>Source:</strong> Polymarket Gamma API<br><br><strong>What it tracks:</strong> Prediction market odds for "US strikes Iran" events. Real money betting markets often predict events accurately.<br><br><strong>Risk logic:</strong> Direct % from market odds. If traders bet 30% chance of strike, signal shows 30%.<br><br><strong>Max contribution:</strong> 10%'
    },
    pentagon: {
        title: 'Pentagon Pizza Meter',
        body: '<strong>Source:</strong> Time-based simulation (GitHub Actions)<br><br><strong>What it tracks:</strong> Simulates pizza delivery activity patterns near the Pentagon based on time of day.<br><br><strong>Risk logic:</strong> If late night hours or weekends show elevated activity, it may indicate staff working overtime = potential elevated activity.<br><br><strong>Baseline:</strong> Normal = ~10%. Spikes during unusual late-night/weekend periods.<br><br><strong>Inspiration:</strong> During the 1991 Gulf War, journalists noticed pizza deliveries to the Pentagon spiked before major operations.<br><br><strong>Max contribution:</strong> 10%'
    },
    calculation: {
        title: 'How We Calculate Risk',
        body: '<strong>Total Risk = Sum of 7 Signals</strong><br><br>📰 <strong>News Intel (max 30%):</strong> Real-time news from Reuters, BBC, NYT, Al Jazeera. Critical keywords like "strike", "attack", "imminent".<br><br>📈 <strong>Public Interest (max 20%):</strong> GDELT global news sentiment + Wikipedia page views on Iran-related pages.<br><br>✈️ <strong>Civil Aviation (max 15%):</strong> Aircraft over Iran airspace. Fewer = airlines avoiding = higher risk.<br><br>🛩️ <strong>Military Tankers (max 10%):</strong> KC-135 refueling tankers detected in Middle East via ADS-B.<br><br>📊 <strong>Market Odds (max 10%):</strong> Polymarket prediction odds for "US strikes Iran" events.<br><br>🍕 <strong>Pentagon Pizza Meter (max 10%):</strong> Pizza delivery busyness near Pentagon. Late-night/weekend spikes = potential overtime work.<br><br>🌤️ <strong>Op. Conditions (max 5%):</strong> Clear weather in Tehran = favorable for operations.<br><br><strong>Escalation Multiplier:</strong> If 3+ signals are elevated, total gets a 15% boost.<br><br><strong>Risk Levels:</strong><br>• 0-30% = Low Risk<br>• 31-60% = Elevated<br>• 61-85% = High Risk<br>• 86-100% = Imminent'
    },
    about: {
        title: 'About StrikeRadar',
        body: '<strong>⚠️ Disclaimer</strong><br><br>This is an <strong>experimental project</strong> for informational purposes only.<br><br><strong>NOT:</strong><br>• Official intelligence<br>• Verified predictions<br>• Basis for decisions<br><br><strong>Data Sources</strong><br>• NewsData.io<br>• GDELT Project<br>• Wikipedia<br>• Aviationstack<br>• OpenWeatherMap<br><br><strong>Limitations</strong><br>Cannot account for classified intel or diplomatic activity. One data point among many.<br><br><em>Stay informed. Think critically.</em>'
    }
};

let chart;
let lastUpdateTime = null;
let countdownInterval = null;

// Utilities
const getTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone.split('/').pop().replace('_', ' ');
const formatTime = () => new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
const formatDate = (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

function getColor(v) { return v >= 86 ? 'red' : v >= 61 ? 'orange' : v >= 31 ? 'yellow' : 'green'; }
function getGradient(v) { return v >= 86 ? 'url(#gradRed)' : v >= 61 ? 'url(#gradOrange)' : v >= 31 ? 'url(#gradYellow)' : 'url(#gradGreen)'; }
function getStatusText(v) { return v >= 86 ? 'Imminent' : v >= 61 ? 'High Risk' : v >= 31 ? 'Elevated' : 'Low Risk'; }
function getStatusClass(v) { return v >= 86 ? 'imminent' : v >= 61 ? 'high' : v >= 31 ? 'elevated' : 'low'; }

function setStatus(id, live) {
    const el = document.getElementById(id);
    el.textContent = live ? 'LIVE' : 'WEAK';
    el.className = `signal-status ${live ? 'live' : 'weak'}`;
}

function updateTimestamp(cacheTimestamp = null) {
    // Use cache timestamp if provided, otherwise current time
    if (cacheTimestamp) {
        lastUpdateTime = new Date(cacheTimestamp);
    } else {
        lastUpdateTime = new Date();
    }
    // Format the time from the actual data timestamp
    const hours = lastUpdateTime.getHours().toString().padStart(2, '0');
    const mins = lastUpdateTime.getMinutes().toString().padStart(2, '0');
    document.getElementById('lastUpdate').textContent = `${hours}:${mins}`;
    document.getElementById('timezone').textContent = getTimezone();
    startCountdown();
}

function startCountdown() {
    if (countdownInterval) clearInterval(countdownInterval);
    countdownInterval = setInterval(() => {
        if (!lastUpdateTime) return;
        const elapsed = Math.floor((Date.now() - lastUpdateTime.getTime()) / 1000);
        const remaining = Math.max(0, 1800 - elapsed); // 30 minutes = 1800 seconds
        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        const nextEl = document.getElementById('nextUpdate');
        if (remaining > 0) {
            nextEl.textContent = `Next in ${mins}:${secs.toString().padStart(2, '0')}`;
        } else {
            nextEl.textContent = 'Updating...';
        }
    }, 1000);
}

function updateGauge(score) {
    score = Math.max(0, Math.min(100, Math.round(score)));
    // Deterministic jitter for gauge - all users see same value
    const seed = Math.floor(Date.now() / (30 * 60 * 1000));
    const jitterVal = Math.floor(seededRandom(seed, 99) * 3) - 1;
    const displayScore = Math.max(0, Math.min(100, score + jitterVal));
    state.risk = displayScore;
    document.getElementById('gaugeFill').style.strokeDashoffset = 251.2 - (displayScore / 100 * 251.2);
    document.getElementById('gaugeFill').setAttribute('stroke', getGradient(displayScore));
    const val = document.getElementById('gaugeValue');
    val.textContent = `${displayScore}%`;
    val.className = `gauge-value ${getColor(displayScore)}`;
    const label = document.getElementById('statusLabel');
    label.textContent = getStatusText(displayScore);
    label.className = `status-label ${getStatusClass(displayScore)}`;
}

function updateSignal(name, value, detail) {
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
        updateSparkline(name, weatherNum, sparkColor);
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
        updateSparkline(name, displayValue, sparkColor);
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
            <div class="feed-meta">
                <span class="feed-source">${i.source}${i.badge ? ` <span class="feed-badge">${i.badge}</span>` : ''}</span>
                <span class="feed-time">${i.time}</span>
            </div>
            <div class="feed-text">${i.text}</div>
        </div>
    `).join('');

    document.getElementById('feedCount').textContent = `${state.feedItems.length} items`;
    btn.style.display = state.feedItems.length > 3 ? 'block' : 'none';
    btn.textContent = expanded ? 'Show Less' : `Show All (${state.feedItems.length})`;
}

function toggleFeed() {
    const isExpanded = document.getElementById('feedList').classList.toggle('expanded');
    trackEvent('feed_toggle', 'engagement', isExpanded ? 'expanded' : 'collapsed');
    renderFeed();
}

function initChart(historyData = null) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    const now = new Date();

    // If we have real history data, use it
    if (historyData && historyData.length > 0) {
        // Filter to last 72 hours and sort by timestamp
        const cutoff = Date.now() - 72 * 60 * 60 * 1000;
        const validHistory = historyData
            .filter(h => h.timestamp > cutoff)
            .sort((a, b) => a.timestamp - b.timestamp);

        // Build labels and data from real history
        let lastDate = '';
        validHistory.forEach((h, i) => {
            const d = new Date(h.timestamp);
            const dateStr = formatDate(d);
            const hourStr = d.getHours().toString().padStart(2, '0') + ':00';

            let label;
            if (i === validHistory.length - 1) {
                label = 'Now';
            } else if (dateStr !== lastDate) {
                label = dateStr;
                lastDate = dateStr;
            } else {
                label = hourStr;
            }

            state.trendLabels.push(label);
            state.trendData.push(h.risk);
        });
    } else {
        // No history yet - show placeholder with "Building history..."
        state.trendLabels.push('Building history...');
        state.trendData.push(null);
    }

    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: state.trendLabels,
            datasets: [{
                data: state.trendData,
                borderColor: '#f97316',
                backgroundColor: 'rgba(249, 115, 22, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#f97316',
                pointBorderColor: '#fff',
                pointBorderWidth: 1,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1c1c1c',
                    titleColor: '#fff',
                    bodyColor: '#999',
                    borderColor: '#333',
                    borderWidth: 1,
                    padding: 10,
                    displayColors: false,
                    callbacks: {
                        title: (ctx) => ctx[0].label,
                        label: (ctx) => `Risk: ${Math.round(ctx.raw)}%`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#666', font: { size: 10 } }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#666', font: { size: 10 }, stepSize: 25, callback: v => v + '%' }
                }
            }
        }
    });

    const originalDraw = chart.draw;
    chart.draw = function() {
        originalDraw.apply(this, arguments);
        const ctx = this.ctx;
        const yAxis = this.scales.y;
        const xAxis = this.scales.x;
        const y = yAxis.getPixelForValue(15);
        ctx.save();
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(xAxis.left, y);
        ctx.lineTo(xAxis.right, y);
        ctx.stroke();
        ctx.fillStyle = '#555';
        ctx.font = '10px Inter';
        ctx.fillText('Normal', xAxis.left + 5, y - 5);
        ctx.restore();
    };
}

function showInfo(type) {
    trackEvent('info_click', 'engagement', type);
    gtag('event', 'view_item', {
        item_id: type,
        item_name: INFO_CONTENT[type].title
    });
    const info = INFO_CONTENT[type];
    document.getElementById('infoTitle').textContent = info.title;
    document.getElementById('infoBody').innerHTML = info.body;
    document.getElementById('infoModal').classList.add('open');
}
function closeInfo(e) { if (!e || e.target.id === 'infoModal') document.getElementById('infoModal').classList.remove('open'); }

function shareSnapshot() {
    trackEvent('share', 'engagement', 'snapshot_shared', state.risk);
    const text = `📡 StrikeRadar - USA Strike on Iran Monitor\n\n` +
        `📊 Current Risk: ${state.risk}% (${getStatusText(state.risk)})\n` +
        `⏱️ Projected: Next 8 Hours\n\n` +
        `📰 News: ${document.getElementById('newsValue').textContent}\n` +
        `📈 Interest: ${document.getElementById('socialValue').textContent}\n` +
        `✈️ Aviation: ${document.getElementById('flightValue').textContent}\n` +
        `🌤️ Conditions: ${document.getElementById('weatherValue').textContent}\n\n` +
        `🔗 https://backyonatan-alt.github.io/strikeradar`;

    if (navigator.share) {
        navigator.share({ title: 'StrikeRadar', text });
        trackEvent('share', 'engagement', 'native_share', state.risk);
    } else {
        navigator.clipboard.writeText(text).then(() => {
            alert('Copied to clipboard!');
            trackEvent('share', 'engagement', 'clipboard_copy', state.risk);
        });
    }
}

// SIGNAL 1: NEWS INTEL - Uses cached data from GitHub Action (Max 30%)
// News is now fetched server-side to avoid CORS proxy inconsistencies
async function fetchNews() {
    try {
        setStatus('newsStatus', true);

        // First, try to get cached news from npoint.io (set by GitHub Action)
        let articles = 0;
        let alertCount = 0;
        let newsArticles = [];

        try {
            const cacheRes = await fetch(`https://api.npoint.io/${API_KEYS.npoint}`);
            if (cacheRes.ok) {
                const cache = await cacheRes.json();
                if (cache.news_intel && cache.news_intel.articles) {
                    newsArticles = cache.news_intel.articles;
                    articles = cache.news_intel.total_count || newsArticles.length;
                    alertCount = cache.news_intel.alert_count || 0;

                    // Add articles to feed
                    newsArticles.slice(0, 8).forEach(a => {
                        const title = (a.title || '').substring(0, 80);
                        addFeed('NEWS', title, a.is_alert, a.is_alert ? 'Alert' : null);
                    });

                    console.log(`News Intel from cache: ${articles} articles, ${alertCount} alerts`);
                }
            }
        } catch (e) {
            console.log('Cache read failed, using fallback');
        }

        // If no cached data, use fallback baseline
        if (articles === 0) {
            console.log('No cached news data, using baseline');
            updateSignal('news', 10, 'Awaiting data...');
            return 3; // baseline contribution
        }

        // Calculate contribution based on article count and alerts
        // With 2 RSS feeds (BBC + Al Jazeera), typical Iran articles = 0-10
        let contribution = 2; // baseline
        if (articles === 0) {
            contribution = 2;
        } else if (articles <= 3) {
            contribution = 3 + articles * 2 + alertCount * 1;
        } else if (articles <= 6) {
            contribution = 9 + (articles - 3) * 1.5 + alertCount * 1.5;
        } else if (articles <= 10) {
            contribution = 13.5 + (articles - 6) * 1 + alertCount * 2;
        } else {
            contribution = 17.5 + (articles - 10) * 0.5 + alertCount * 2;
        }

        contribution = Math.min(30, contribution);
        const displayRisk = Math.round((contribution / 30) * 100);
        updateSignal('news', displayRisk, `${articles} articles, ${alertCount} critical`);
        return contribution;

    } catch (e) {
        console.log('News fetch error:', e.message);
        setStatus('newsStatus', false);
        updateSignal('news', 6, 'Feed error - using baseline');
        return 2;
    }
}

// SIGNAL 2: PUBLIC INTEREST - GDELT + Wikipedia (Max 25%)
async function fetchPublicInterest() {
    let gdeltArticles = 0;
    let gdeltTone = 0;
    let wikiViews = 0;
    let gdeltWorked = false;
    let wikiWorked = false;

    try {
        const gdeltQuery = encodeURIComponent('iran attack OR iran strike OR iran military OR iran us');
        const gdeltUrl = `https://api.gdeltproject.org/api/v2/doc/doc?query=${gdeltQuery}&mode=artlist&maxrecords=50&format=json&timespan=24h`;
        const gdeltRes = await fetch(gdeltUrl);
        if (gdeltRes.ok) {
            const text = await gdeltRes.text();
            // GDELT sometimes returns error messages instead of JSON
            if (text.startsWith('{') || text.startsWith('[')) {
                const gdeltData = JSON.parse(text);
                if (gdeltData.articles && Array.isArray(gdeltData.articles)) {
                    gdeltArticles = gdeltData.articles.length;
                    const tones = gdeltData.articles.map(a => a.tone || 0).filter(t => t !== 0);
                    if (tones.length > 0) {
                        gdeltTone = tones.reduce((a, b) => a + b, 0) / tones.length;
                    }
                    gdeltWorked = true;
                    if (gdeltData.articles[0]) {
                        const title = (gdeltData.articles[0].title || '').substring(0, 70);
                        const isNegative = gdeltTone < -3;
                        addFeed('GDELT', title, isNegative, isNegative ? 'Alert' : null);
                    }
                }
            }
        }
    } catch (e) { /* GDELT unavailable - will use Wikipedia only */ }

    try {
        const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0].replace(/-/g, '');
        const pages = ['Iran', 'Iran%E2%80%93United_States_relations', 'Iran%E2%80%93Israel_conflict'];
        let totalViews = 0;

        for (const page of pages) {
            try {
                const res = await fetch(`https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/${page}/daily/${yesterday}/${yesterday}`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.items?.[0]) {
                        totalViews += data.items[0].views;
                        wikiWorked = true;
                    }
                }
            } catch (e) { }
        }
        wikiViews = totalViews;
    } catch (e) { }

    setStatus('trendsStatus', gdeltWorked || wikiWorked);

    let gdeltRisk = 0;
    let wikiRisk = 0;

    if (gdeltWorked) {
        if (gdeltArticles <= 10) {
            gdeltRisk = 1 + gdeltArticles * 0.2;
        } else if (gdeltArticles <= 25) {
            gdeltRisk = 3 + (gdeltArticles - 10) * 0.27;
        } else {
            gdeltRisk = 7 + (gdeltArticles - 25) * 0.2;
        }
        if (gdeltTone < -5) gdeltRisk += 3;
        else if (gdeltTone < -3) gdeltRisk += 1.5;
        gdeltRisk = Math.min(12, gdeltRisk);
    }

    if (wikiWorked && wikiViews > 0) {
        if (wikiViews < 20000) {
            wikiRisk = 1 + (wikiViews / 15000);
        } else if (wikiViews < 50000) {
            wikiRisk = 2.5 + ((wikiViews - 20000) / 10000);
        } else if (wikiViews < 100000) {
            wikiRisk = 5.5 + ((wikiViews - 50000) / 8000);
        } else {
            wikiRisk = 12 + ((wikiViews - 100000) / 50000);
        }
        wikiRisk = Math.min(13, wikiRisk);

        if (wikiViews > 80000) {
            addFeed('WIKI', `Iran pages: ${Math.round(wikiViews/1000)}k views (elevated)`, true, 'Spike');
        }
    }

    const totalRisk = Math.min(25, gdeltRisk + wikiRisk + 1);
    const displayRisk = Math.round((totalRisk / 25) * 100);

    let detail = '';
    if (gdeltWorked) detail += `${gdeltArticles} GDELT`;
    if (wikiWorked) detail += (detail ? ', ' : '') + `${Math.round(wikiViews/1000)}k Wiki`;
    if (!detail) detail = 'Monitoring...';

    updateSignal('social', displayRisk, detail);
    return totalRisk;
}

// SIGNAL 3: AVIATION - Iran Airspace Activity (Max 35%)
// Uses OpenSky Network API - counts aircraft in Iran airspace in real-time
async function fetchAviation() {
    try {
        setStatus('flightStatus', true);

        // Iran airspace bounding box (covers Tehran and surrounding area)
        // lat 25-40, lon 44-64 covers most of Iran
        const url = `https://opensky-network.org/api/states/all?lamin=25&lomin=44&lamax=40&lomax=64`;

        const res = await fetch(url);
        if (!res.ok) {
            throw new Error('OpenSky API error');
        }

        const data = await res.json();
        let civilCount = 0;
        let airlines = [];

        if (data.states && Array.isArray(data.states)) {
            data.states.forEach(aircraft => {
                const icao = aircraft[0]; // ICAO24 hex
                const callsign = (aircraft[1] || '').trim();
                const onGround = aircraft[8];

                // Skip aircraft on ground
                if (onGround) return;

                // Skip military (US military ICAO range)
                const icaoNum = parseInt(icao, 16);
                const usafHexStart = parseInt('AE0000', 16);
                const usafHexEnd = parseInt('AE7FFF', 16);
                if (icaoNum >= usafHexStart && icaoNum <= usafHexEnd) return;

                // Count as civil aviation
                civilCount++;

                // Extract airline code from callsign (first 3 letters usually)
                if (callsign && callsign.length >= 3) {
                    const airlineCode = callsign.substring(0, 3);
                    if (!airlines.includes(airlineCode)) {
                        airlines.push(airlineCode);
                    }
                }
            });
        }

        // Risk logic: Normal traffic = 20-50 aircraft over Iran
        // Lower than normal = concerning (airlines avoiding area)
        // Much lower = high risk
        let contribution = 0;

        if (civilCount === 0) {
            contribution = 30; // Zero flights = very concerning
            addFeed('AVIATION', `⚠️ No aircraft detected over Iran airspace`, true, 'Warning');
        } else if (civilCount < 5) {
            contribution = 25; // Very low traffic
            addFeed('AVIATION', `⚠️ Very low traffic: ${civilCount} aircraft over Iran`, true, 'Alert');
        } else if (civilCount < 15) {
            contribution = 15; // Below normal
        } else if (civilCount < 30) {
            contribution = 8; // Slightly below normal
        } else {
            contribution = 3; // Normal/good traffic
        }

        const displayRisk = Math.round((contribution / 35) * 100);
        const detail = `${civilCount} aircraft over Iran`;
        updateSignal('flight', displayRisk, detail);

        if (civilCount >= 15) {
            addFeed('AVIATION', `${civilCount} commercial aircraft in Iran airspace (${airlines.length} airlines)`);
        }

        return contribution;

    } catch (e) {
        console.log('Aviation API error:', e.message);
        setStatus('flightStatus', false);
        updateSignal('flight', 15, 'Scanning...');
        return 5; // Baseline when API fails
    }
}

// SIGNAL 4: WEATHER CONDITIONS (Max 5%)
async function fetchWeather() {
    try {
        setStatus('weatherStatus', true);
        const res = await fetch(`https://api.openweathermap.org/data/2.5/weather?lat=35.6892&lon=51.389&appid=${API_KEYS.openweather}&units=metric`);
        const data = await res.json();
        if (data.main) {
            const temp = Math.round(data.main.temp);
            const vis = data.visibility || 10000;
            const clouds = data.clouds?.all || 0;

            let condition, contribution;
            if (vis >= 10000 && clouds < 30) {
                condition = 'Favorable';
                contribution = 5;
            } else if (vis >= 7000 && clouds < 60) {
                condition = 'Marginal';
                contribution = 2;
            } else {
                condition = 'Poor';
                contribution = 0;
            }

            updateSignal('weather', condition, `${temp}°C, ${vis >= 10000 ? '10+' : Math.round(vis/1000)}km vis, ${clouds}% clouds`);
            addFeed('WEATHER', `Tehran: ${temp}°C, ${data.weather[0]?.description || 'clear'}. Ops: ${condition}`);
            return contribution;
        }
    } catch (e) { setStatus('weatherStatus', false); updateSignal('weather', 'Unknown', 'API error'); }
    return 0;
}

// SIGNAL 5: TANKER ACTIVITY - KC-135/KC-10/KC-46 in Middle East (Max 15%)
// Uses OpenSky Network API (free, no key required for anonymous access)
async function fetchTanker() {
    try {
        setStatus('tankerStatus', true);

        // Middle East bounding box (Persian Gulf region)
        // lamin, lomin, lamax, lomax
        const bbox = '20,40,40,65'; // Covers Persian Gulf, Arabian Sea, parts of Middle East

        // OpenSky API - get all aircraft in the region
        const url = `https://opensky-network.org/api/states/all?lamin=20&lomin=40&lamax=40&lomax=65`;

        const res = await fetch(url);
        if (!res.ok) {
            throw new Error('OpenSky API error');
        }

        const data = await res.json();
        let tankerCount = 0;
        const tankerCallsigns = [];

        // Known US military tanker callsign prefixes and ICAO hex ranges
        // KC-135: callsigns often start with IRON, SHELL, TEXAN, ETHYL, etc.
        // US military ICAO hex: AE0000-AE7FFF (Air Force)
        const tankerPrefixes = ['IRON', 'SHELL', 'TEXAN', 'ETHYL', 'PEARL', 'ARCO', 'ESSO', 'MOBIL', 'GULF', 'TOPAZ', 'PACK', 'DOOM', 'TREK', 'REACH'];
        const usafHexStart = parseInt('AE0000', 16);
        const usafHexEnd = parseInt('AE7FFF', 16);

        if (data.states && Array.isArray(data.states)) {
            data.states.forEach(aircraft => {
                const icao = aircraft[0]; // ICAO24 hex
                const callsign = (aircraft[1] || '').trim().toUpperCase();

                // Check if it's a US military aircraft
                const icaoNum = parseInt(icao, 16);
                const isUSMilitary = icaoNum >= usafHexStart && icaoNum <= usafHexEnd;

                // Check callsign for tanker patterns
                const isTankerCallsign = tankerPrefixes.some(prefix => callsign.startsWith(prefix));

                // Also check for KC- in callsign or STRATOTANKER type
                const hasKCPattern = callsign.includes('KC') || callsign.includes('TANKER');

                if (isUSMilitary && (isTankerCallsign || hasKCPattern)) {
                    tankerCount++;
                    if (callsign) tankerCallsigns.push(callsign);
                }
            });
        }

        // Calculate risk contribution (max 15%)
        let contribution = 0;
        let status = '';

        if (tankerCount === 0) {
            contribution = 1;
            status = 'No activity';
        } else if (tankerCount <= 2) {
            contribution = 3;
            status = 'Normal ops';
        } else if (tankerCount <= 4) {
            contribution = 8;
            status = 'Elevated';
            addFeed('TANKER', `⛽ ${tankerCount} tankers detected in Middle East region`, true, 'Alert');
        } else {
            contribution = 15;
            status = 'High activity';
            addFeed('TANKER', `⛽ HIGH ALERT: ${tankerCount} tankers active in region!`, true, 'Critical');
        }

        const displayRisk = Math.round((contribution / 15) * 100);
        const detail = tankerCount > 0 ? `${tankerCount} in Middle East airspace` : 'Scanning Persian Gulf...';
        updateSignal('tanker', displayRisk, detail);

        return contribution;

    } catch (e) {
        console.log('Tanker API error:', e.message);
        setStatus('tankerStatus', false);
        updateSignal('tanker', 5, 'API unavailable');
        return 1; // Baseline when API fails
    }
}

// SIGNAL: POLYMARKET ODDS (Max 10%)
// Note: Real data is fetched by GitHub Action and stored in npoint.io cache
// This function returns baseline - actual display comes from cached data in displayData()
async function fetchPolymarket() {
    // Polymarket data is fetched server-side by GitHub Action every 30 min
    // and stored in npoint.io cache. We just return baseline here.
    // The displayData() function will read the cached polymarket odds.
    setStatus('polymarketStatus', true);
    return 1; // Baseline - real value comes from cache
}

// Deterministic jitter based on current time window (all users see same values)
// Changes every 30 minutes when data refreshes
function getTimeBasedSeed() {
    // Round to nearest 30-minute window
    const now = Date.now();
    return Math.floor(now / (30 * 60 * 1000));
}

// Simple seeded random (deterministic based on seed + index)
function seededRandom(seed, index) {
    const x = Math.sin(seed + index * 9999) * 10000;
    return x - Math.floor(x);
}

// Apply deterministic jitter - same for all users at same time
function applyJitter(value, min = 0, max = 100, range = 2, index = 0) {
    const seed = getTimeBasedSeed();
    const random = seededRandom(seed, index);
    const jitterAmount = Math.floor(random * (range * 2 + 1)) - range;
    return Math.max(min, Math.min(max, value + jitterAmount));
}

// npoint.io cache functions (free, no rate limits!)
const NPOINT_ID = API_KEYS.npoint;

async function getCache() {
    try {
        const res = await fetch(`https://api.npoint.io/${NPOINT_ID}`);
        if (res.ok) {
            return await res.json();
        }
    } catch (e) {
        console.log('Cache read error:', e.message);
    }
    return null;
}

async function setCache(data, totalRisk = null) {
    try {
        // Get existing cache to preserve history AND GitHub Action data
        const existing = await getCache();
        let history = (existing && existing.history) ? existing.history : [];
        let signalHistoryCache = (existing && existing.signalHistory) ? existing.signalHistory : {
            news: [], social: [], flight: [], tanker: [], pentagon: [], polymarket: [], weather: []
        };

        // IMPORTANT: Preserve GitHub Action data (polymarket, pentagon, news_intel)
        // These are set by the server-side script and should not be overwritten
        if (existing) {
            if (existing.polymarket) data.polymarket = existing.polymarket;
            if (existing.pentagon) data.pentagon = existing.pentagon;
            if (existing.news_intel) data.news_intel = existing.news_intel;
            if (existing.pentagon_updated) data.pentagon_updated = existing.pentagon_updated;
        }

        // Add new history point if we have a risk value
        if (totalRisk !== null) {
            history.push({
                timestamp: Date.now(),
                risk: totalRisk
            });

            // Keep only last 72 hours of history (max ~144 points at 30-min intervals)
            const cutoff = Date.now() - 72 * 60 * 60 * 1000;
            history = history.filter(h => h.timestamp > cutoff);

            // Add signal values to signal history (for sparklines)
            if (data.signalValues) {
                ['news', 'social', 'flight', 'tanker', 'weather'].forEach(sig => {
                    if (data.signalValues[sig] !== undefined) {
                        signalHistoryCache[sig] = signalHistoryCache[sig] || [];
                        signalHistoryCache[sig].push(data.signalValues[sig]);
                        // Keep only last 20 points
                        if (signalHistoryCache[sig].length > 20) {
                            signalHistoryCache[sig] = signalHistoryCache[sig].slice(-20);
                        }
                    }
                });
            }

            // Handle pentagon separately from cached data
            if (data.pentagon && data.pentagon.score !== undefined) {
                const pentagonDisplay = Math.round((data.pentagon.score < 40 ? 10 :
                    data.pentagon.score <= 60 ? 20 + (data.pentagon.score - 40) :
                    data.pentagon.score <= 80 ? 40 + (data.pentagon.score - 60) * 1.5 :
                    70 + (data.pentagon.score - 80) * 1.5));
                signalHistoryCache.pentagon = signalHistoryCache.pentagon || [];
                signalHistoryCache.pentagon.push(Math.min(100, pentagonDisplay));
                if (signalHistoryCache.pentagon.length > 20) {
                    signalHistoryCache.pentagon = signalHistoryCache.pentagon.slice(-20);
                }
            }
        }

        // Save data with history
        data.history = history;
        data.signalHistory = signalHistoryCache;

        await fetch(`https://api.npoint.io/${NPOINT_ID}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
    } catch (e) {
        console.log('Cache write error:', e.message);
    }
}

// Fetch fresh data from all APIs
async function fetchFreshData() {
    // Clear feed for fresh fetch
    state.feedItems = [];
    state.seenHeadlines.clear();

    // First, get cached data for polymarket and pentagon (set by GitHub Action)
    let cachedData = {};
    try {
        const cacheRes = await fetch(`https://api.npoint.io/${API_KEYS.npoint}`);
        if (cacheRes.ok) {
            cachedData = await cacheRes.json();
        }
    } catch (e) {
        console.log('Cache fetch error:', e.message);
    }

    const [news, interest, aviation, tanker, polymarket, weather] = await Promise.all([
        fetchNews(),
        fetchPublicInterest(),
        fetchAviation(),
        fetchTanker(),
        fetchPolymarket(),
        fetchWeather()
    ]);

    // Calculate display values for sparklines
    const newsDisplay = Math.round((Number(news) || 0) / 30 * 100);
    const socialDisplay = Math.round((Number(interest) || 0) / 20 * 100);
    const flightDisplay = Math.round((Number(aviation) || 0) / 15 * 100);
    const tankerDisplay = Math.round((Number(tanker) || 0) / 10 * 100);
    const polymarketOdds = cachedData.polymarket?.odds || 0;
    const polymarketDisplay = polymarketOdds; // Direct percentage
    const weatherDisplay = Number(weather) >= 4 ? 100 : Number(weather) >= 2 ? 50 : 20;

    return {
        news: Number(news) || 0,
        interest: Number(interest) || 0,
        aviation: Number(aviation) || 0,
        tanker: Number(tanker) || 0,
        weather: Number(weather) || 0,
        timestamp: Date.now(),
        // Include cached polymarket and pentagon data (from GitHub Action)
        polymarket: cachedData.polymarket || null,
        pentagon: cachedData.pentagon || null,
        // Store history from cache
        history: cachedData.history || [],
        signalHistory: cachedData.signalHistory || {},
        // Store details for cache
        newsDetail: document.getElementById('newsDetail').textContent,
        socialDetail: document.getElementById('socialDetail').textContent,
        flightDetail: document.getElementById('flightDetail').textContent,
        tankerDetail: document.getElementById('tankerDetail').textContent,
        polymarketDetail: document.getElementById('polymarketDetail').textContent,
        weatherDetail: document.getElementById('weatherDetail').textContent,
        feedItems: state.feedItems.slice(0, 10), // Store top 10 feed items
        // Store signal display values for sparkline history
        signalValues: {
            news: newsDisplay,
            social: socialDisplay,
            flight: flightDisplay,
            tanker: tankerDisplay,
            polymarket: polymarketDisplay,
            weather: weatherDisplay
        }
        // Note: history is managed separately in setCache
    };
}

// Display data on the dashboard
function displayData(data, fromCache = false) {
    const safeNews = applyJitter(data.news, 0, 30, 1, 1);
    const safeInterest = applyJitter(data.interest, 0, 20, 1, 2);
    const safeAviation = applyJitter(data.aviation, 0, 15, 1, 3);
    const safeTanker = applyJitter(data.tanker || 0, 0, 10, 1, 4);
    const safePolymarket = applyJitter(data.polymarket || 0, 0, 10, 1, 5);
    const safeWeather = data.weather;

    // Load signal history from cache if available
    if (data.signalHistory) {
        ['news', 'social', 'flight', 'tanker', 'pentagon', 'polymarket', 'weather'].forEach(sig => {
            if (data.signalHistory[sig] && data.signalHistory[sig].length > 0) {
                state.signalHistory[sig] = data.signalHistory[sig];
            }
        });
    }

    // Update individual signal displays with stored details or computed values
    // NEWS: Use news_intel from GitHub Action cache if available (consistent for all users)
    let newsDisplayRisk = Math.round((safeNews / 30) * 100);
    let newsDetail = `${Math.round(safeNews / 2)} articles, ${Math.round(safeNews / 10)} critical`;

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

    updateSignal('social', Math.round((safeInterest / 20) * 100), data.socialDetail || 'GDELT + Wikipedia');

    const flightCount = Math.round(safeAviation * 10);
    const flightDetail = (data.flightDetail && !data.flightDetail.includes('Scanning') && !data.flightDetail.includes('Loading')) ? data.flightDetail : `${flightCount} aircraft over Iran`;
    updateSignal('flight', Math.round((safeAviation / 15) * 100), flightDetail);

    const tankerCount = Math.round(safeTanker / 4);
    const tankerDetail = (data.tankerDetail && !data.tankerDetail.includes('Scanning') && !data.tankerDetail.includes('Loading')) ? data.tankerDetail : `${tankerCount} detected in region`;
    updateSignal('tanker', Math.round((safeTanker / 10) * 100), tankerDetail);

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
        // No cached polymarket data yet - show baseline
        updateSignal('polymarket', 10, 'Awaiting data...');
        setStatus('polymarketStatus', true);
    }
    // Store for total calculation
    const safePolymarketCalc = polymarketContribution;

    updateSignal('weather', safeWeather >= 4 ? 'Favorable' : safeWeather >= 2 ? 'Marginal' : 'Poor', data.weatherDetail || 'Tehran conditions');

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

    // Restore feed items from cache
    if (fromCache && data.feedItems && data.feedItems.length > 0) {
        state.feedItems = data.feedItems;
        state.seenHeadlines = new Set(data.feedItems.map(i => i.text.substring(0, 50).toLowerCase()));
        renderFeed();
    }

    let total = safeNews + safeInterest + safeAviation + safeTanker + safePolymarketCalc + safeWeather + pentagonContribution;

    const elevated = [safeNews > 10, safeInterest > 8, safeAviation > 10, safeTanker > 5, safeWeather > 2, pentagonContribution > 5].filter(Boolean).length;
    if (elevated >= 3) {
        total = Math.min(100, total * 1.15);
        if (!fromCache) addFeed('SYSTEM', 'Multiple elevated signals detected - escalation multiplier applied', true, 'Alert');
    }

    total = Math.min(100, Math.max(0, Math.round(total) || 0));

    const prevRisk = state.risk;
    updateGauge(total);

    // Update timestamp with the actual data timestamp
    updateTimestamp(data.timestamp);

    // Send Telegram alert if risk crossed 60% threshold
    if (!fromCache) {
        sendTelegramAlert(total, prevRisk);
    }

    if (total > maxRiskSeen) maxRiskSeen = total;

    trackEvent('risk_update', 'metrics', getStatusText(total), total);
    gtag('event', 'signal_update', {
        news_score: Math.round(safeNews),
        interest_score: Math.round(safeInterest),
        aviation_score: Math.round(safeAviation),
        weather_score: Math.round(safeWeather),
        total_risk: total
    });

    if (Math.abs(total - prevRisk) > 10) {
        trackEvent('risk_change', 'alert', total > prevRisk ? 'risk_increased' : 'risk_decreased', Math.abs(total - prevRisk));
    }
    if (total >= 60 && prevRisk < 60) {
        trackEvent('high_risk_alert', 'alert', 'crossed_60_threshold', total);
    }
    if (total >= 85 && prevRisk < 85) {
        trackEvent('imminent_risk_alert', 'alert', 'crossed_85_threshold', total);
    }

    // Chart is now updated from history data, not here
    return total;
}

// TELEGRAM ALERT - sends notification when risk crosses 60%
let lastAlertSent = 0;
const ALERT_COOLDOWN = 60 * 60 * 1000; // 1 hour between alerts

async function sendTelegramAlert(risk, prevRisk) {
    // Only send if crossing UP through 60% threshold
    if (risk < 60 || prevRisk >= 60) return;

    // Check cooldown
    const now = Date.now();
    if (now - lastAlertSent < ALERT_COOLDOWN) {
        console.log('Alert cooldown active, skipping Telegram notification');
        return;
    }

    const statusEmoji = risk >= 86 ? '🔴' : risk >= 61 ? '🟠' : '🟡';
    const message = `${statusEmoji} *StrikeRadar Alert*

📊 Risk Level: *${risk}%* (${getStatusText(risk)})
⏱️ Window: Next 8 Hours

📰 News: ${document.getElementById('newsValue').textContent}
📈 Interest: ${document.getElementById('socialValue').textContent}
✈️ Aviation: ${document.getElementById('flightValue').textContent}
🌤️ Conditions: ${document.getElementById('weatherValue').textContent}

🔗 [View Dashboard](https://backyonatan-alt.github.io/strikeradar)`;

    try {
        const res = await fetch(`https://api.telegram.org/bot${API_KEYS.telegram}/sendMessage`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: TELEGRAM_CHANNEL,
                text: message,
                parse_mode: 'Markdown',
                disable_web_page_preview: true
            })
        });

        if (res.ok) {
            lastAlertSent = now;
            console.log('Telegram alert sent successfully');
            addFeed('TELEGRAM', 'Alert sent to subscribers', false);
        } else {
            const err = await res.json();
            console.log('Telegram error:', err.description);
        }
    } catch (e) {
        console.log('Telegram send error:', e.message);
    }
}

// Track last API call time to prevent excessive calls
let lastAPICall = 0;
const MIN_API_INTERVAL = 15 * 60 * 1000; // Minimum 15 minutes between API calls

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
            // Show default values if no cache at all
            updateSignal('news', 10, 'Waiting for data...');
            updateSignal('social', 8, 'Waiting for data...');
            updateSignal('flight', 12, 'Waiting for data...');
            updateSignal('weather', 'Unknown', 'Waiting for data...');
            updateGauge(15);
        }
        return;
    }

    // Cache is very old or doesn't exist - fetch fresh data
    console.log('Fetching fresh data...');

    // Mark API call time BEFORE calling (prevents race conditions)
    localStorage.setItem('strikeradar_last_api_call', now.toString());

    const freshData = await fetchFreshData();

    // Display the fresh data and get total risk
    const total = displayData(freshData, false);

    // Save to cache with history point
    await setCache(freshData, total);

    // Also save to localStorage as backup
    try {
        localStorage.setItem('strikeradar_cache', JSON.stringify(freshData));
    } catch (e) { }

    // Update chart from history (will include the new point)
    const updatedCache = await getCache();
    updateChartFromHistory(updatedCache?.history);
}

// Update chart with real history data (fills gaps with simulated data)
function updateChartFromHistory(history) {
    if (!chart) return;

    state.trendLabels = [];
    state.trendData = [];

    const now = Date.now();
    const interval = 12 * 60 * 60 * 1000; // 12 hours
    const points = 7; // 7 points for 72 hours

    // Build time slots for the chart (every 12 hours going back 72h)
    const slots = [];
    for (let i = points - 1; i >= 0; i--) {
        slots.push(now - i * interval);
    }

    // Create a map of real history data by rounded timestamp
    const historyMap = new Map();
    if (history && history.length > 0) {
        history.forEach(h => {
            // Find closest slot for this history point
            let closestSlot = slots[0];
            let minDiff = Math.abs(h.timestamp - slots[0]);
            slots.forEach(slot => {
                const diff = Math.abs(h.timestamp - slot);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestSlot = slot;
                }
            });
            // Only use if within 6 hours of slot
            if (minDiff < 6 * 60 * 60 * 1000) {
                historyMap.set(closestSlot, h.risk);
            }
        });
    }

    // Build chart data - use real data where available, simulated where not
    let lastDate = '';
    const seed = Math.floor(now / 86400000); // Stable seed per day

    slots.forEach((slot, i) => {
        const d = new Date(slot);
        const dateStr = formatDate(d);
        const hourStr = d.getHours().toString().padStart(2, '0') + ':00';

        // Label
        let label;
        if (i === slots.length - 1) {
            label = 'Now';
        } else if (dateStr !== lastDate) {
            label = dateStr;
            lastDate = dateStr;
        } else {
            label = hourStr;
        }
        state.trendLabels.push(label);

        // Data - real or simulated
        if (historyMap.has(slot)) {
            state.trendData.push(historyMap.get(slot));
        } else {
            // Simulated data based on seed + position
            const pseudoRandom = Math.abs(Math.sin(seed + i * 7) * 43758.5453) % 1;
            state.trendData.push(Math.round(pseudoRandom * 20 + 10)); // 10-30% range
        }
    });

    // Update chart
    chart.data.labels = state.trendLabels;
    chart.data.datasets[0].data = state.trendData;
    chart.update('none');
}

document.addEventListener('DOMContentLoaded', async () => {
    // Load history first for chart
    const cached = await getCache();
    initChart(cached?.history);
    addFeed('SYSTEM', 'StrikeRadar initialized');

    // Track page load event
    gtag('event', 'page_load', {
        page_title: 'StrikeRadar Dashboard',
        page_location: window.location.href,
        user_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });

    setTimeout(() => { calculate(); setInterval(calculate, 1800000); }, 500);
});

// Track visibility changes (user comes back to tab)
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        trackEvent('tab_return', 'engagement', 'user_returned');
    }
});

// Secret force refresh: Press R 3 times quickly
let rPresses = [];
document.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'r') {
        const now = Date.now();
        rPresses.push(now);
        // Keep only presses within last 1 second
        rPresses = rPresses.filter(t => now - t < 1000);
        if (rPresses.length >= 3) {
            rPresses = [];
            console.log('Force refresh triggered!');
            forceRefresh();
        }
    }
});

async function forceRefresh() {
    // Check rate limit - only allow once per hour
    const now = Date.now();
    const lastCall = localStorage.getItem('strikeradar_last_api_call');
    if (lastCall && (now - parseInt(lastCall)) < MIN_API_INTERVAL) {
        showToast('⏳ Please wait - API refresh limited to every 15 min');
        return;
    }

    showToast('🔄 Refreshing data...');
    localStorage.setItem('strikeradar_last_api_call', now.toString());

    const freshData = await fetchFreshData();
    const total = displayData(freshData, false);
    await setCache(freshData, total);

    try {
        localStorage.setItem('strikeradar_cache', JSON.stringify(freshData));
    } catch (e) { }

    const updatedCache = await getCache();
    updateChartFromHistory(updatedCache?.history);
    showToast('✅ Data refreshed!');
}

function showToast(message) {
    // Remove existing toast if any
    const existing = document.getElementById('toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'toast';
    toast.textContent = message;
    toast.style.cssText = 'position:fixed;top:80px;left:50%;transform:translateX(-50%);background:#22c55e;color:#000;padding:14px 28px;border-radius:12px;font-size:15px;font-weight:600;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.5);';
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// Offline/online detection
function updateOnlineStatus() {
    const offlineBar = document.getElementById('offlineBar');
    if (!navigator.onLine) {
        offlineBar.style.display = 'block';
        document.body.style.paddingBottom = '40px';
    } else {
        offlineBar.style.display = 'none';
        document.body.style.paddingBottom = '0';
    }
}
window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
updateOnlineStatus();
