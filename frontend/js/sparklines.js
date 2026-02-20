// =============================================
// SPARKLINE RENDERING
// =============================================

function generateSparkline(data, color = '#22c55e') {
    if (!data || data.length < 2) return '';

    const width = 100;
    const height = 40;
    const padding = 2;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const points = data.map((val, i) => ({
        x: padding + (i / (data.length - 1)) * (width - 2 * padding),
        y: height - padding - ((val - min) / range) * (height - 2 * padding)
    }));

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

    // Get history from state (loaded from data.json)
    const history = state.signalHistory[name] || [];
    
    // Only render real data from data.json
    if (history.length >= 2) {
        container.innerHTML = generateSparkline(history, color);
    } else {
        container.innerHTML = ''; // Show nothing until we have at least 2 points
    }
}

function getSparklineColor(value) {
    if (value >= 86) return '#ef4444'; // red
    if (value >= 61) return '#f97316'; // orange
    if (value >= 31) return '#eab308'; // yellow
    return '#22c55e'; // green
}
