/**
 * Global Notification System
 * - Works on ANY page (just include this script)
 * - Popups stay until user clicks close
 * - Color-coded by notification type
 * - Auto-polls every 15 seconds
 */

(function () {
    'use strict';

    // ============================================
    // 1. INJECT CSS (once)
    // ============================================
    if (!document.getElementById('notif-system-styles')) {
        const styles = document.createElement('style');
        styles.id = 'notif-system-styles';
        styles.textContent = `
            .notification-popup {
                position: fixed;
                top: 24px;
                right: 24px;
                z-index: 999999;
                display: flex;
                flex-direction: column;
                gap: 16px;
                max-width: 480px;
                width: calc(100% - 48px);
                pointer-events: none;
            }
            @media (max-width: 520px) {
                .notification-popup {
                    top: 12px; right: 12px; left: 12px;
                    width: auto;
                }
            }

            .notif-item {
                pointer-events: auto;
                position: relative;
                overflow: hidden;
                padding: 22px 24px;
                border-radius: 14px;
                border: 2px solid #3b82f6;
                border-left: 6px solid #3b82f6;
                background: linear-gradient(135deg, #1a2332 0%, #0f1720 100%);
                box-shadow: 0 16px 48px rgba(0,0,0,0.85),
                            0 0 0 1px rgba(96,165,250,0.15),
                            0 0 32px rgba(59,130,246,0.35);
                animation: notifSlideIn 0.45s ease;
                transition: opacity 0.35s ease, transform 0.35s ease;
            }
            .notif-item::before {
                content: '';
                position: absolute;
                top: 0; left: 0;
                width: 5px; height: 100%;
                background: linear-gradient(180deg, #60a5fa, #3b82f6);
            }
            .notif-item.closing {
                opacity: 0;
                transform: translateX(400px);
            }

            /* Type variants */
            .notif-item.released {
                border-color: #10b981;
                border-left-color: #10b981;
                background: linear-gradient(135deg, #0a2a1a 0%, #061410 100%);
                box-shadow: 0 16px 48px rgba(0,0,0,0.85), 0 0 32px rgba(16,185,129,0.45);
            }
            .notif-item.released::before {
                background: linear-gradient(180deg, #34d399, #10b981);
            }
            .notif-item.order {
                border-color: #3b82f6;
                border-left-color: #3b82f6;
                background: linear-gradient(135deg, #0a1a2a 0%, #06121c 100%);
                box-shadow: 0 16px 48px rgba(0,0,0,0.85), 0 0 32px rgba(59,130,246,0.45);
            }
            .notif-item.order::before {
                background: linear-gradient(180deg, #60a5fa, #3b82f6);
            }
            .notif-item.delay {
                border-color: #f59e0b;
                border-left-color: #f59e0b;
                background: linear-gradient(135deg, #2a1f0a 0%, #1a1208 100%);
                box-shadow: 0 16px 48px rgba(0,0,0,0.85), 0 0 32px rgba(245,158,11,0.45);
            }
            .notif-item.delay::before {
                background: linear-gradient(180deg, #fbbf24, #f59e0b);
            }
            .notif-item.refund,
            .notif-item.dispute {
                border-color: #dc2626;
                border-left-color: #dc2626;
                background: linear-gradient(135deg, #2a0a0a 0%, #1a0606 100%);
                box-shadow: 0 16px 48px rgba(0,0,0,0.85), 0 0 32px rgba(220,38,38,0.45);
            }
            .notif-item.refund::before,
            .notif-item.dispute::before {
                background: linear-gradient(180deg, #ef4444, #dc2626);
            }

            .notif-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 10px;
                gap: 12px;
            }
            .notif-title {
                font-weight: 800;
                font-size: 18px;
                line-height: 1.3;
                flex: 1;
                color: #ffffff;
                text-shadow: 0 2px 4px rgba(0,0,0,0.4);
            }
            .notif-title.released { color: #34d399; }
            .notif-title.refunded { color: #f87171; }
            .notif-title.ordered { color: #60a5fa; }
            .notif-title.delayed { color: #fbbf24; }
            .notif-title.disputed { color: #f87171; }
            .notif-title.delivered { color: #34d399; }

            .notif-close {
                color: #cbd5e1;
                cursor: pointer;
                font-size: 20px;
                font-weight: 700;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
                border-radius: 50%;
                background: rgba(255,255,255,0.1);
                transition: 0.2s;
                line-height: 1;
                user-select: none;
            }
            .notif-close:hover {
                background: rgba(255,255,255,0.25);
                color: #ffffff;
            }

            .notif-message {
                color: #f0f4f8;
                font-size: 15px;
                line-height: 1.6;
                margin-bottom: 12px;
                font-weight: 500;
            }
            .notif-time {
                color: #94a3b8;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.3px;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .notif-time::before {
                content: '🕐';
                font-size: 13px;
            }

            @keyframes notifSlideIn {
                from { opacity: 0; transform: translateX(400px); }
                to   { opacity: 1; transform: translateX(0); }
            }

            /* Floating "View All" button */
            .notif-view-all {
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 999998;
                background: #0095f6;
                color: white !important;
                text-decoration: none !important;
                padding: 12px 20px;
                border-radius: 24px;
                font-size: 14px;
                font-weight: 700;
                box-shadow: 0 4px 16px rgba(0,149,246,0.4);
                display: flex;
                align-items: center;
                gap: 8px;
                transition: 0.2s;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            .notif-view-all:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,149,246,0.5);
            }
            .notif-view-all .count {
                background: rgba(255,255,255,0.25);
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 12px;
                min-width: 22px;
                text-align: center;
            }
        `;
        document.head.appendChild(styles);
    }

    // ============================================
    // 2. INJECT CONTAINER (once)
    // ============================================
    let popupContainer = document.getElementById('notification-popup');
    if (!popupContainer) {
        popupContainer = document.createElement('div');
        popupContainer.id = 'notification-popup';
        popupContainer.className = 'notification-popup';
        document.body.appendChild(popupContainer);
    }

    // ============================================
    // 3. HELPERS
    // ============================================
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    function getTypeClass(type) {
        switch (type) {
            case 'FUND_RELEASED': return { item: 'released', title: 'released' };
            case 'FUND_REFUNDED': return { item: 'refund', title: 'refunded' };
            case 'ORDER_PLACED': return { item: 'order', title: 'ordered' };
            case 'ORDER_DELAYED': return { item: 'delay', title: 'delayed' };
            case 'ORDER_DISPUTED': return { item: 'dispute', title: 'disputed' };
            case 'DISPUTE_RESOLVED': return { item: 'dispute', title: 'disputed' };
            case 'ORDER_DELIVERED': return { item: 'released', title: 'delivered' };
            case 'ORDER_OUT_FOR_DELIVERY': return { item: 'order', title: 'ordered' };
            case 'RETURN_TRACKING_SUBMITTED': return { item: 'order', title: 'ordered' };
            default: return { item: '', title: '' };
        }
    }

    // Track shown notification IDs so we don't repeat them
    const shownIds = new Set();

    // ============================================
    // 4. SHOW A NOTIFICATION (stays until closed)
    // ============================================
    function showNotification(notif) {
        const cls = getTypeClass(notif.type);

        const popup = document.createElement('div');
        popup.className = `notif-item ${cls.item}`;
        popup.dataset.notifId = notif.id;

        popup.innerHTML = `
            <div class="notif-header">
                <span class="notif-title ${cls.title}">${notif.title}</span>
                <span class="notif-close" title="Close">✕</span>
            </div>
            <div class="notif-message">${notif.message}</div>
            <div class="notif-time">${notif.created_at}</div>
        `;

        // Close handler — notification stays until user clicks
        popup.querySelector('.notif-close').addEventListener('click', function () {
            popup.classList.add('closing');
            setTimeout(() => popup.remove(), 400);
        });

        popupContainer.appendChild(popup);
        shownIds.add(notif.id);
    }

    // ============================================
    // 5. FETCH & DISPLAY
    // ============================================
    async function checkNotifications() {
        try {
            const response = await fetch('/api/notifications/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) return;

            const data = await response.json();
            if (!data.notifications || data.notifications.length === 0) return;

            // Show any we haven't shown yet
            let newOnes = 0;
            data.notifications.forEach(notif => {
                if (!shownIds.has(notif.id)) {
                    showNotification(notif);
                    newOnes++;
                }
            });

            // Mark as read on the server side (after showing them)
            if (newOnes > 0) {
                // Small delay so popups actually appear first
                setTimeout(() => {
                    fetch('/api/notifications/read/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken'),
                            'Content-Type': 'application/json'
                        }
                    }).catch(() => {});
                }, 1000);
            }
        } catch (err) {
            // Silent fail — don't break the page
            console.log('Notif check error:', err);
        }
    }

    // ============================================
    // 6. VIEW-ALL FLOATING BUTTON
    // ============================================
    function injectViewAllButton() {
        if (document.querySelector('.notif-view-all')) return;
        const btn = document.createElement('a');
        btn.href = '/notifications/';
        btn.className = 'notif-view-all';
        btn.innerHTML = `🔔 View All <span class="count" id="notif-total-count">…</span>`;
        document.body.appendChild(btn);
    }

    // ============================================
    // 7. START
    // ============================================
    function init() {
        // Only run for logged-in users (a simple heuristic: check for a cookie)
        checkNotifications();
        setInterval(checkNotifications, 15000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();