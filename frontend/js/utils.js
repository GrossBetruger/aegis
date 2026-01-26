// =============================================
// UTILITY FUNCTIONS
// =============================================

const getTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone.split('/').pop().replace('_', ' ');
const formatTime = () => new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
const formatDate = (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

function getColor(v) { return v >= 86 ? 'red' : v >= 61 ? 'orange' : v >= 31 ? 'yellow' : 'green'; }
function getGradient(v) { return v >= 86 ? 'url(#gradRed)' : v >= 61 ? 'url(#gradOrange)' : v >= 31 ? 'url(#gradYellow)' : 'url(#gradGreen)'; }
function getStatusText(v) { return v >= 86 ? 'Imminent' : v >= 61 ? 'High Risk' : v >= 31 ? 'Elevated' : 'Low Risk'; }
function getStatusClass(v) { return v >= 86 ? 'imminent' : v >= 61 ? 'high' : v >= 31 ? 'elevated' : 'low'; }

function setStatus(id, live) {
    const el = document.getElementById(id);
    if (el) el.textContent = live ? 'LIVE' : 'STALE';
}

function getTimeBasedSeed() {
    return Math.floor(Date.now() / (30 * 60 * 1000)); // Changes every 30 min
}

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

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    });
}

function updateOnlineStatus() {
    if (!navigator.onLine) {
        showToast('⚠️ Connection lost - showing cached data');
    }
}
