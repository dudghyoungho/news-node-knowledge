// popup.js

// config.js에서 설정된 값을 가져옴
const SERVER_URL = typeof CONFIG !== 'undefined' ? CONFIG.API_BASE_URL : "http://localhost:8000";

console.log(`[Popup] Current Env: ${typeof CONFIG !== 'undefined' ? CONFIG.ENV : 'DEV'}`);
console.log(`[Popup] Server URL: ${SERVER_URL}`);

document.addEventListener('DOMContentLoaded', () => {
    // ----------------------------------------------------------------
    // 1. DOM Elements Selection
    // ----------------------------------------------------------------
    const loginSection = document.getElementById('login-section');
    const mainSection = document.getElementById('main-section');
    
    // Buttons
    const btnGoogle = document.getElementById('btn-google-login');
    const btnLogout = document.getElementById('btn-logout');
    const btnSummarize = document.getElementById('btn-summarize');
    const btnSave = document.getElementById('btn-save');
    const btnGraph = document.getElementById('btn-graph');
    
    // Inputs & Display
    const regionSelector = document.getElementById('region-selector');
    const summaryBox = document.getElementById('summary-box');
    const statusMsg = document.getElementById('status');
    const toggleTracking = document.getElementById('toggle-tracking'); // [New] Tracking Toggle

    // State Variables
    let userToken = null;
    let currentUrl = "";
    let currentRegion = 'KR'; // Default

    // ----------------------------------------------------------------
    // 2. Initialization (Token, Region, Tracking Settings)
    // ----------------------------------------------------------------
    chrome.storage.local.get(['api_token', 'region', 'enableTracking'], (result) => {
        // 2-1. Load Region
        if (result.region) {
            currentRegion = result.region;
            if(regionSelector) regionSelector.value = currentRegion;
        }

        // 2-2. Load Tracking Setting (Default: false is safer for review, but let's assume true if undefined for UX)
        // 심사를 위해서는 기본값 false가 안전하지만, 사용자 경험상 최초 1회는 켜져있거나 팝업으로 물어보는 게 좋습니다.
        // 여기서는 저장된 값이 없으면 true(켜짐)로 설정합니다.
        const isTrackingEnabled = result.enableTracking !== false; 
        if(toggleTracking) toggleTracking.checked = isTrackingEnabled;

        // 2-3. Check Login
        if (result.api_token) {
            userToken = result.api_token;
            showMainSection();
        } else {
            showLoginSection();
        }
    });

    // ----------------------------------------------------------------
    // 3. UI Event Handlers
    // ----------------------------------------------------------------

    // [Region Change]
    if(regionSelector) {
        regionSelector.addEventListener('change', (e) => {
            currentRegion = e.target.value;
            chrome.storage.local.set({ 'region': currentRegion }, () => {
                if (!mainSection.classList.contains('hidden')) {
                    // Reset UI to encourage re-summarization with new region
                    summaryBox.textContent = `Region switched to ${currentRegion}.\nClick button to summarize.`;
                    btnSummarize.classList.remove('hidden');
                    btnSave.classList.add('hidden');
                }
            });
        });
    }

    // [Tracking Toggle Change]
    if(toggleTracking) {
        toggleTracking.addEventListener('change', (e) => {
            const isEnabled = e.target.checked;
            chrome.storage.local.set({ 'enableTracking': isEnabled }, () => {
                console.log(`[Popup] Tracking set to: ${isEnabled}`);
                // (선택사항) 상태 메시지로 알려줌
                statusMsg.textContent = isEnabled ? "Context learning enabled." : "Context learning disabled.";
                setTimeout(() => { statusMsg.textContent = ""; }, 1500);
            });
        });
    }

    // ----------------------------------------------------------------
    // 4. Helper Functions (Screen Transition)
    // ----------------------------------------------------------------
    function showLoginSection() {
        if(loginSection) loginSection.classList.remove('hidden');
        if(mainSection) mainSection.classList.add('hidden');
        if(statusMsg) statusMsg.textContent = "";
    }

    function showMainSection() {
        if(loginSection) loginSection.classList.add('hidden');
        if(mainSection) mainSection.classList.remove('hidden');
        
        if(btnSummarize) {
            btnSummarize.classList.remove('hidden');
            btnSummarize.disabled = false;
            btnSummarize.textContent = "⚡️ Generate Summary";
        }
        
        if(btnSave) {
            btnSave.classList.add('hidden');
            btnSave.textContent = "Save to My Library";
            btnSave.disabled = false;
        }
        
        if(summaryBox) summaryBox.textContent = "Click the button to start AI summarization.";
    }

    // ----------------------------------------------------------------
    // 5. Auth Logic (Login / Logout)
    // ----------------------------------------------------------------
    if(btnGoogle) {
        btnGoogle.addEventListener('click', () => {
            statusMsg.textContent = "Authenticating...";
            
            chrome.identity.getAuthToken({ interactive: true }, function(token) {
                if (chrome.runtime.lastError || !token) {
                    console.error(chrome.runtime.lastError);
                    statusMsg.textContent = "Login failed.";
                    return;
                }

                statusMsg.textContent = "Verifying token...";

                // Backend Login API
                fetch(`${SERVER_URL}/api/news/auth/google/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ access_token: token })
                })
                .then(res => {
                    if (!res.ok) throw new Error("Server error");
                    return res.json();
                })
                .then(data => {
                    if (data.token) {
                        userToken = data.token;
                        chrome.storage.local.set({ 'api_token': userToken }, () => {
                            showMainSection();
                            statusMsg.textContent = "";
                        });
                    } else {
                        throw new Error(data.error || "Login failed");
                    }
                })
                .catch(err => {
                    statusMsg.textContent = "Error: " + err.message;
                });
            });
        });
    }

    if(btnLogout) {
        btnLogout.addEventListener('click', (e) => {
            e.preventDefault(); 
            chrome.storage.local.remove(['api_token'], () => {
                userToken = null;
                showLoginSection();
            });
        });
    }

    // ----------------------------------------------------------------
    // 6. Summarize Logic
    // ----------------------------------------------------------------
    if(btnSummarize) {
        btnSummarize.addEventListener('click', async () => {
            btnSummarize.disabled = true;
            summaryBox.textContent = "Analyzing article..."; 
            statusMsg.textContent = "Processing...";

            try {
                // Get active tab URL
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if(!tab) throw new Error("No active tab found");
                currentUrl = tab.url;

                // API Call
                const response = await fetch(`${SERVER_URL}/api/news/summarize/`, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Authorization': `Token ${userToken}` 
                    },
                    body: JSON.stringify({ 
                        url: currentUrl,
                        region: currentRegion 
                    })
                });

                if (!response.ok) {
                    if (response.status === 401) {
                        alert("Session expired. Please log in again.");
                        btnLogout.click();
                        return;
                    }

                    const errData = await response.json();
                    
                    if (errData.status === 'ALREADY_SAVED') {
                        summaryBox.textContent = `📚 Already saved.\n(Date: ${new Date().toLocaleDateString()})`;
                        btnSummarize.textContent = "Already in Library";
                        statusMsg.textContent = "";
                        return;
                    }
                    
                    throw new Error(errData.error || "Summarization failed");
                }

                // Streaming Response Handling
                // (백엔드가 StreamingResponse인 경우)
                summaryBox.textContent = ""; // Clear
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    summaryBox.textContent += chunk;
                    summaryBox.scrollTop = summaryBox.scrollHeight;
                }

                // Finish
                btnSummarize.classList.add('hidden'); 
                btnSave.classList.remove('hidden');   
                statusMsg.textContent = "Summary generated.";

            } catch (error) {
                summaryBox.textContent = "❌ Error: " + error.message;
                btnSummarize.disabled = false;
                btnSummarize.textContent = "Retry";
                statusMsg.textContent = "";
            }
        });
    }

    // ----------------------------------------------------------------
    // 7. Save Logic
    // ----------------------------------------------------------------
    if(btnSave) {
        btnSave.addEventListener('click', async () => {
            statusMsg.textContent = "Saving...";
            const finalSummary = summaryBox.textContent;

            try {
                const response = await fetch(`${SERVER_URL}/api/news/save/`, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Authorization': `Token ${userToken}` 
                    },
                    body: JSON.stringify({ 
                        url: currentUrl,
                        summary: finalSummary,
                        region: currentRegion
                    })
                });

                if (response.ok) {
                    btnSave.textContent = "Saved ✅";
                    btnSave.disabled = true;
                    statusMsg.textContent = "Saved to Library.";
                    setTimeout(() => window.close(), 1500);
                } else {
                    const errData = await response.json();
                    throw new Error(errData.error || "Save failed");
                }
            } catch (error) {
                statusMsg.textContent = "Error: " + error.message;
            }
        });
    }

    // ----------------------------------------------------------------
    // 8. Dashboard Link
    // ----------------------------------------------------------------
    if (btnGraph) {
        btnGraph.addEventListener('click', () => {
            if (!userToken) {
                alert("Login required.");
                return;
            }
            const targetUrl = `${SERVER_URL}/api/news/dashboard/?token=${userToken}&region=${currentRegion}`;
            chrome.tabs.create({ url: targetUrl });
        });
    }
});