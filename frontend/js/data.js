// =============================================
// DATA FETCHING
// =============================================

// Read data from adjacent data.json file (updated by GitHub Actions)
async function getData() {
    try {
        const res = await fetch('./data.json');
        if (res.ok) {
            return await res.json();
        }
    } catch (e) {
        console.log('Error reading data.json:', e.message);
    }
    
    // Fallback if data.json can't be read - use new structure
    return {
        news: { risk: 3, detail: 'Data unavailable', history: [], raw_data: {} },
        flight: { risk: 5, detail: 'Data unavailable', history: [], raw_data: {} },
        tanker: { risk: 1, detail: 'Data unavailable', history: [], raw_data: {} },
        weather: { risk: 0, detail: 'Data unavailable', history: [], raw_data: {} },
        polymarket: { risk: 10, detail: 'Data unavailable', history: [], raw_data: {} },
        pentagon: { risk: 10, detail: 'Data unavailable', history: [], raw_data: {} },
        total_risk: { risk: 20, history: [], elevated_count: 0 },
        last_updated: new Date().toISOString()
    };
}

async function sendTelegramAlert(risk, prevRisk) {
    if (!API_KEYS.telegram) return;

    const now = Date.now();
    const lastAlert = localStorage.getItem('lastAlertTime');
    
    if (lastAlert && (now - parseInt(lastAlert)) < ALERT_COOLDOWN) {
        console.log('Alert cooldown active');
        return;
    }

    if (risk < 61 || risk <= prevRisk) return; // Only alert on high risk increases

    const message = `🚨 <b>StrikeRadar Alert</b>

Risk Level: <b>${Math.round(risk)}%</b>
Status: <b>${getStatusText(risk)}</b>

Elevated signals detected. Monitor the dashboard for updates.

🔗 <a href="https://backyonatan-alt.github.io/strikeradar">View Dashboard</a>`;

    try {
        const res = await fetch(`https://api.telegram.org/bot${API_KEYS.telegram}/sendMessage`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: TELEGRAM_CHANNEL,
                text: message,
                parse_mode: 'HTML',
                disable_web_page_preview: true
            })
        });

        if (res.ok) {
            localStorage.setItem('lastAlertTime', now.toString());
            let lastAlertSent = now;
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
