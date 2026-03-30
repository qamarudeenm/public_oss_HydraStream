(function() {
    const API_ENDPOINT = 'http://localhost:5000/events';
    const SESSION_ID = 'sess_' + Math.random().toString(36).substr(2, 9);
    const USER_ID = 'user_' + Math.random().toString(36).substr(2, 9);

    const NexusTracker = {
        track: function(eventType, data = {}) {
            const event = {
                event_type: eventType,
                page_url: window.location.href,
                user_id: USER_ID,
                session_id: SESSION_ID,
                data: data,
                timestamp: new Date().toISOString()
            };

            console.log('[NexusTracker] Tracking event:', event);

            fetch(API_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(event)
            }).catch(err => console.error('[NexusTracker] Failed to send event:', err));
        }
    };

    // Auto-track clicks
    document.addEventListener('click', function(e) {
        const target = e.target;
        if (target.tagName === 'BUTTON' || target.tagName === 'A') {
            NexusTracker.track('click', {
                element_id: target.id || null,
                element_text: target.innerText || null,
                classes: target.className
            });
        }
    }, true);

    window.NexusTracker = NexusTracker;
    console.log('[NexusTracker] Initialized with Session:', SESSION_ID);
})();
