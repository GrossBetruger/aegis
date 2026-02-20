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
        showToast('⚠️ Connection lost - showing last known data');
    }
}
