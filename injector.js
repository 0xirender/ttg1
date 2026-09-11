/**
 * Dual-Tier Telegram Web Session Injector (Browser-Side Script)
 * 
 * Injects pre-authorized MTProto auth keys and application state into:
 * 1. Official Telegram Web A multiaccount & legacy storage (from src/util/sessions.ts)
 * 2. localStorage ('tt-global-state', 'account1', 'user_auth', 'dc', 'dcX_auth_key')
 * 3. IndexedDB ('tt-data' / 'keyval') with non-blocking timeout
 */

(function(payload, doneCallback) {
    try {
        const dcId = Number(payload.dc_id);
        const authKeyArray = payload.auth_key_array || [];
        const authKeyHex = payload.auth_key_hex || Array.from(authKeyArray).map(b => b.toString(16).padStart(2, '0')).join('');
        const userId = String(payload.user_id || "12345678");
        const serverTimeOffset = payload.server_time_offset || 0;

        console.log('[Injector] Injecting session for DC:', dcId, 'User:', userId);

        // -------------------------------------------------------------
        // TIER 1: Populate localStorage (Official Telegram Web A Storage)
        // -------------------------------------------------------------

        // 1. Account 1 Slot Storage (used by official loadSlotSession in sessions.ts)
        const slotData = {
            dcId: dcId,
            userId: userId,
            isTest: false,
            [`dc${dcId}_auth_key`]: authKeyHex
        };
        localStorage.setItem('account1', JSON.stringify(slotData));

        // 2. Legacy Storage (used by official loadStoredLegacySession)
        localStorage.setItem('user_auth', JSON.stringify({
            dcID: dcId,
            id: userId,
            test: false,
            date: Math.floor(Date.now() / 1000)
        }));
        localStorage.setItem('dc', String(dcId));
        localStorage.setItem(`dc${dcId}_auth_key`, JSON.stringify(authKeyHex));

        // 3. Clear any partial/stale global state so Telegram Web uses clean initialState
        localStorage.removeItem('tt-global-state');
        localStorage.removeItem('tt-shared-state');
        console.log('[Injector] localStorage successfully populated with official session keys.');

        // -------------------------------------------------------------
        // TIER 2: Safe, Non-Blocking IndexedDB Write (Optional Cache)
        // -------------------------------------------------------------
        let isDone = false;
        function finish(msg) {
            if (!isDone) {
                isDone = true;
                if (doneCallback) {
                    doneCallback({ success: true, message: msg || 'Injection complete' });
                }
            }
        }

        // Safety timeout: Never let IndexedDB lock or hang Selenium
        setTimeout(() => {
            finish('Completed with localStorage (IndexedDB timed out or non-blocking)');
        }, 800);

        try {
            const authKeyBuffer = new Uint8Array(authKeyArray);
            const req = indexedDB.open('tt-data', 1);

            req.onupgradeneeded = function(e) {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('keyval')) {
                    db.createObjectStore('keyval');
                }
            };

            req.onblocked = function() {
                console.warn('[Injector] IndexedDB open blocked by another connection, skipping IDB write.');
                finish('IndexedDB blocked, completed via localStorage');
            };

            req.onerror = function() {
                console.warn('[Injector] IndexedDB open error, skipping IDB write.');
                finish('IndexedDB error, completed via localStorage');
            };

            req.onsuccess = function(e) {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('keyval')) {
                    db.close();
                    finish('IndexedDB keyval store not ready, completed via localStorage');
                    return;
                }

                try {
                    const tx = db.transaction('keyval', 'readwrite');
                    const store = tx.objectStore('keyval');
                    store.put(authKeyBuffer, `dc${dcId}_auth_key`);
                    store.put(serverTimeOffset, 'server_time_offset');
                    tx.oncomplete = function() {
                        db.close();
                        finish('Dual-tier injection complete (localStorage + IndexedDB)');
                    };
                    tx.onerror = function() {
                        db.close();
                        finish('Completed via localStorage (IndexedDB tx error)');
                    };
                } catch (txErr) {
                    db.close();
                    finish('Completed via localStorage (IndexedDB tx catch)');
                }
            };
        } catch (idbErr) {
            console.warn('[Injector] IndexedDB error:', idbErr);
            finish('Completed via localStorage');
        }

    } catch (globalErr) {
        console.error('[Injector] Global error:', globalErr);
        if (doneCallback) {
            doneCallback({ success: false, error: String(globalErr) });
        }
    }
})(arguments[0], arguments[1]);
