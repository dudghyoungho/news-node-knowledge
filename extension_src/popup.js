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
    const btnDemoLogin = document.getElementById('btn-demo-login'); // [추가됨]
    const btnLogout = document.getElementById('btn-logout');
    const btnSummarize = document.getElementById('btn-summarize');
    const btnSave = document.getElementById('btn-save');
    const btnGraph = document.getElementById('btn-graph');
    
    // Inputs & Display
    const regionSelector = document.getElementById('region-selector');
    const summaryBox = document.getElementById('summary-box');
    const statusMsg = document.getElementById('status');
    const toggleTracking = document.getElementById('toggle-tracking');

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

        // 2-2. Load Tracking Setting
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
        
        // 데모 버튼 상태 초기화
        if(btnDemoLogin) {
            btnDemoLogin.textContent = "🚀 Try Demo Mode (Guest)";
            btnDemoLogin.disabled = false;
        }
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
    
    // [Google Login]
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
                .then(res => res.json())
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

    // [NEW] Demo Login Logic (여기에 추가됨)
    if (btnDemoLogin) {
        btnDemoLogin.addEventListener('click', async () => {
            // UI Update
            const originalText = btnDemoLogin.textContent;
            btnDemoLogin.textContent = "Connecting...";
            btnDemoLogin.disabled = true;
            statusMsg.textContent = "Entering Demo Mode...";

            try {
                // 1. Call Backend Demo API
                const response = await fetch(`${SERVER_URL}/api/news/auth/demo/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                const data = await response.json();

                if (response.ok && data.token) {
                    // 2. Save Token (Same key 'api_token' as Google Login)
                    userToken = data.token;
                    chrome.storage.local.set({ 
                        'api_token': userToken,
                        'username': data.username // Optional: if you want to display name
                    }, () => {
                        console.log("✅ Demo Token Saved");
                        showMainSection();
                        statusMsg.textContent = `Welcome, ${data.username}!`;
                    });
                } else {
                    throw new Error(data.message || "Demo login failed");
                }
            } catch (error) {
                console.error("Demo Login Error:", error);
                statusMsg.textContent = "Error: " + error.message;
                btnDemoLogin.textContent = originalText;
                btnDemoLogin.disabled = false;
            }
        });
    }

    // [Logout]
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
    // 6. Summarize Logic (기존 로직 그대로 사용 - 토큰만 있으면 됨)
    // ----------------------------------------------------------------
    if(btnSummarize) {
        btnSummarize.addEventListener('click', async () => {
            btnSummarize.disabled = true;
            summaryBox.textContent = "Analyzing article..."; 
            statusMsg.textContent = "Processing...";

            try {
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if(!tab) throw new Error("No active tab found");
                currentUrl = tab.url;

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
                    if (errData.is_saved) { // 백엔드 응답 키 확인 필요 (is_saved or status)
                         summaryBox.textContent = `📚 Already saved.\nCheck your library.`;
                         btnSummarize.textContent = "Already in Library";
                         statusMsg.textContent = "";
                         return;
                    }
                    throw new Error(errData.error || "Summarization failed");
                }

                // Streaming Response Handling
                summaryBox.textContent = ""; 
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value);
                    summaryBox.textContent += chunk;
                    summaryBox.scrollTop = summaryBox.scrollHeight;
                }

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
    // 7. Save Logic (기존 로직 그대로 사용)
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
            // 일반 대시보드로 이동 (데모 계정도 로그인이 되어 있으므로 정상 작동)
            const targetUrl = `${SERVER_URL}/api/news/dashboard/?token=${userToken}&region=${currentRegion}`;
            chrome.tabs.create({ url: targetUrl });
        });
    }
});