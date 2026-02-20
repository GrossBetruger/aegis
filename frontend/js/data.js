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
