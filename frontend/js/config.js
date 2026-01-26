// =============================================
// CONFIG & CONSTANTS
// =============================================
const API_KEYS = {
    telegram: '7798704396:AAHdV18HFUC3gfP1q6DWx-4RtOXLmFRGVH8'
};

const TELEGRAM_CHANNEL = '@StrikeRadarAlerts';

// Cache duration: 30 minutes (frontend reads from data.json)
const CACHE_DURATION = 30 * 60 * 1000; // 30 minutes

const state = {
    trendLabels: [],
    trendData: [],
    feedItems: [],
    seenHeadlines: new Set(),
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

const KEYWORDS = ['retaliation', 'strike', 'attack', 'escalation', 'military', 'threat', 'imminent', 'missile', 'nuclear', 'war'];

const INFO_CONTENT = {
    news: `<strong>News Intelligence Monitor</strong><br><br>
        Analyzes breaking news from BBC World and Al Jazeera for Iran conflict developments.<br><br>
        <strong>Alert triggers:</strong> Headlines with keywords like "strike", "retaliation", "imminent"<br>
        <strong>Max contribution:</strong> 30% of total risk<br>
        <strong>Update frequency:</strong> Every 30 minutes via server`,
    social: `<strong>Public Interest Tracker</strong><br><br>
        Combines GDELT news coverage and Wikipedia traffic for Iran-related pages.<br><br>
        <strong>Sources:</strong> GDELT Event Database + Wikipedia Pageviews API<br>
        <strong>Max contribution:</strong> 25% of total risk<br>
        <strong>Indicates:</strong> Public attention and media focus`,
    flight: `<strong>Civil Aviation Monitor</strong><br><br>
        Tracks commercial aircraft over Iranian airspace using OpenSky Network.<br><br>
        <strong>Logic:</strong> Fewer flights = Higher risk (airlines avoiding area)<br>
        <strong>Max contribution:</strong> 35% of total risk<br>
        <strong>Data source:</strong> OpenSky Network API`,
    tanker: `<strong>Military Tanker Activity</strong><br><br>
        Monitors US Air Force refueling tankers (KC-135, KC-10, KC-46) in the Middle East.<br><br>
        <strong>Significance:</strong> Tanker presence enables extended combat operations<br>
        <strong>Max contribution:</strong> 15% of total risk<br>
        <strong>Region:</strong> 20°-45°N, 30°-65°E`,
    pentagon: `<strong>Pentagon Pizza Meter</strong><br><br>
        Monitors pizza delivery activity near the Pentagon as a proxy for late-night military activity.<br><br>
        <strong>Theory:</strong> Unusual late-night orders may indicate crisis planning<br>
        <strong>Max contribution:</strong> 10% of total risk<br>
        <strong>Update frequency:</strong> Every 30 minutes`,
    polymarket: `<strong>Prediction Market Odds</strong><br><br>
        Real-money betting markets on Iran strike probability.<br><br>
        <strong>Source:</strong> Polymarket (decentralized prediction market)<br>
        <strong>Max contribution:</strong> 10% of total risk<br>
        <strong>Why it matters:</strong> Aggregates wisdom of thousands of traders with money at stake`,
    weather: `<strong>Operation Conditions</strong><br><br>
        Weather conditions in Tehran that could affect military operations.<br><br>
        <strong>Favorable:</strong> Clear skies, good visibility (higher risk)<br>
        <strong>Max contribution:</strong> 5% of total risk<br>
        <strong>Source:</strong> OpenWeatherMap API`
};

const ALERT_COOLDOWN = 60 * 60 * 1000; // 1 hour between alerts
const MIN_API_INTERVAL = 15 * 60 * 1000; // Minimum 15 minutes between API calls
