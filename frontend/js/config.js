// =============================================
// CONFIG & CONSTANTS
// =============================================

const state = {
    trendLabels: [],
    trendData: [],
    signalHistory: {
        news: [],
        flight: [],
        tanker: [],
        pentagon: [],
        polymarket: [],
        weather: [],
        oil: [],
        gdelt: [],
        trends: []
    }
};

const KEYWORDS = ['retaliation', 'strike', 'attack', 'escalation', 'military', 'threat', 'imminent', 'missile', 'nuclear', 'war'];

const INFO_CONTENT = {
    about: {
        title: 'About Strike Radar',
        content: `<div class="modal-body" id="infoBody"><strong>Disclaimer</strong><br><br>This is an <strong>experimental project</strong> for informational purposes only.<br><br><strong>NOT:</strong><br>• Official intelligence<br>• Verified predictions<br>• Basis for decisions<br><br><strong>Data Sources</strong><br>• BBC World & Al Jazeera<br>• GDELT Global News<br>• OpenSky Network<br>• Polymarket<br>• Yahoo Finance (Oil)<br>• Google Trends<br>• OpenWeatherMap<br><br><strong>Limitations</strong><br>Cannot account for classified intel or diplomatic activity. One data point among many.<br><br><em>Stay informed. Think critically.</em></div>`
    },
    calculation: {
        title: 'How We Calculate Risk',
        content: `<strong>Total Risk = Weighted Sum of 9 Signals</strong><br><br>
        <strong>News Intel (20%):</strong> Breaking news with critical keywords increases risk.<br><br>
        <strong>Civil Aviation (20%):</strong> Fewer flights over Iran = airlines avoiding = higher risk.<br><br>
        <strong>Military Tankers (15%):</strong> More US tankers in the region = higher risk.<br><br>
        <strong>Market Odds (15%):</strong> Prediction market betting odds for strike within 7 days.<br><br>
        <strong>Oil Prices (10%):</strong> Price spikes and high levels indicate market tension.<br><br>
        <strong>Global News (5%):</strong> GDELT volume and tone of worldwide Iran coverage.<br><br>
        <strong>Public Interest (5%):</strong> Google search trends for Iran-related terms.<br><br>
        <strong>Pentagon Activity (5%):</strong> Unusual late-night activity near Pentagon = higher risk.<br><br>
        <strong>Weather (5%):</strong> Clear skies in Tehran = favorable for operations = higher risk.<br><br>
        <strong>Escalation Multiplier:</strong> If 3+ signals are elevated, total gets a 15% boost.<br><br>
        <strong>Risk Levels:</strong><br>
        • 0-30% = Low<br>
        • 31-60% = Elevated<br>
        • 61-85% = High<br>
        • 86-100% = Imminent`
    },
    news: `<strong>News Intelligence</strong><br><br>
        Scans BBC World and Al Jazeera for Iran-related news.<br><br>
        <strong>What we look for:</strong> Headlines containing "strike", "attack", "military", "missile", "war", "imminent"<br><br>
        <strong>How it works:</strong> More critical articles = higher risk. The ratio of alarming headlines to total coverage drives the score.<br><br>
        <strong>Weight:</strong> 20% of total risk`,
    flight: `<strong>Civil Aviation</strong><br><br>
        Tracks commercial flights over Iranian airspace via OpenSky Network.<br><br>
        <strong>Why it matters:</strong> Airlines avoid conflict zones. When flights drop, it often signals that carriers have intelligence suggesting danger.<br><br>
        <strong>How it works:</strong> Fewer aircraft = higher risk. Normal traffic (~100+ planes) = low risk.<br><br>
        <strong>Weight:</strong> 20% of total risk`,
    tanker: `<strong>Military Tankers</strong><br><br>
        Monitors US Air Force refueling aircraft in the Middle East.<br><br>
        <strong>Why it matters:</strong> Tankers (KC-135, KC-46) enable fighters and bombers to operate far from base. A surge in tanker activity often precedes military operations.<br><br>
        <strong>How it works:</strong> More tankers detected = higher risk.<br><br>
        <strong>Weight:</strong> 15% of total risk`,
    pentagon: `<strong>Pentagon Activity</strong><br><br>
        Monitors activity patterns near the Pentagon.<br><br>
        <strong>Why it matters:</strong> Unusual late-night or weekend activity can indicate crisis planning sessions.<br><br>
        <strong>How it works:</strong> Normal business hours = low risk. Elevated activity at odd hours = higher risk.<br><br>
        <strong>Weight:</strong> 5% of total risk`,
    polymarket: `<strong>Prediction Markets</strong><br><br>
        Real-money betting odds on "US or Israel strike Iran" within 7 days.<br><br>
        <strong>Source:</strong> Polymarket<br><br>
        <strong>Why it matters:</strong> When people bet real money, they research carefully. Market odds aggregate the wisdom of thousands of informed traders.<br><br>
        <strong>Weight:</strong> 15% of total risk`,
    weather: `<strong>Weather Conditions</strong><br><br>
        Current weather in Tehran, Iran.<br><br>
        <strong>Why it matters:</strong> Military operations favor clear skies for visibility and precision targeting. Poor weather provides natural cover.<br><br>
        <strong>How it works:</strong> Clear skies = higher risk. Cloudy/poor visibility = lower risk.<br><br>
        <strong>Weight:</strong> 5% of total risk`,
    oil: `<strong>Oil Prices (Brent Crude)</strong><br><br>
        Tracks real-time Brent crude oil prices and 24-hour changes.<br><br>
        <strong>Source:</strong> Yahoo Finance<br><br>
        <strong>Why it matters:</strong> Oil prices spike during Middle East tensions. Traders price in conflict risk before events occur. Brent crude recently topped $70/barrel on Iran concerns.<br><br>
        <strong>How it works:</strong> Price spikes (>3% in 24h) and high absolute prices (>$75/barrel) = higher risk.<br><br>
        <strong>Weight:</strong> 10% of total risk`,
    gdelt: `<strong>Global News (GDELT)</strong><br><br>
        Analyzes worldwide news coverage via the GDELT Project.<br><br>
        <strong>Source:</strong> GDELT monitors news in 65+ languages, updated every 15 minutes.<br><br>
        <strong>Why it matters:</strong> Provides broader coverage than English-only sources. Includes sentiment/tone analysis to detect negative coverage spikes.<br><br>
        <strong>How it works:</strong> High article volume + negative tone = higher risk. Looks for "strike", "attack", "war" keywords related to Iran.`,
    trends: `<strong>Public Interest (Google Trends)</strong><br><br>
        Tracks Google search interest for Iran-related terms in the US.<br><br>
        <strong>Keywords tracked:</strong> "Iran war", "Iran strike", "Iran attack", "Iran nuclear", "Iran conflict"<br><br>
        <strong>Why it matters:</strong> Public search behavior can be a leading indicator. People search for information before and during major events.<br><br>
        <strong>How it works:</strong> Sudden spikes in search interest (2-3x normal) or sustained high interest = higher risk.<br><br>
        <strong>Weight:</strong> 5% of total risk`
};

const ALERT_COOLDOWN = 60 * 60 * 1000; // 1 hour between alerts
