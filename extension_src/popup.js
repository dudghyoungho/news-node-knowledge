const SERVER_URL = CONFIG.API_BASE_URL;

console.log(`[Popup] Current Env: ${CONFIG.ENV}`); // 확인용 로그
console.log(`[Popup] Server URL: ${SERVER_URL}`);  // 확인용 로그

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const loginSection = document.getElementById('login-section');
    const mainSection = document.getElementById('main-section');
    
    const btnGoogle = document.getElementById('btn-google-login');
    const btnLogout = document.getElementById('btn-logout');
    
    const btnSummarize = document.getElementById('btn-summarize');
    const btnSave = document.getElementById('btn-save');
    const btnGraph = document.getElementById('btn-graph');
    
    // [NEW] Region Selector
    const regionSelector = document.getElementById('region-selector');
    
    const summaryBox = document.getElementById('summary-box');
    const statusMsg = document.getElementById('status');

    let userToken = null;
    let currentUrl = "";
    let currentRegion = 'KR'; // Default region

    // ============================================================
    // 1. Initialization: Check for saved token & region
    // ============================================================
    // [MODIFIED] Retrieve 'region' along with 'api_token'
    chrome.storage.local.get(['api_token', 'region'], (result) => {
        // 1-1. Load saved region preference
        if (result.region) {
            currentRegion = result.region;
            regionSelector.value = currentRegion;
        }

        // 1-2. Auto Login check
        if (result.api_token) {
            userToken = result.api_token;
            showMainSection();
        } else {
            showLoginSection();
        }
    });

    // ============================================================
    // [NEW] 1-B. Region Change Handler
    // ============================================================
    regionSelector.addEventListener('change', (e) => {
        currentRegion = e.target.value;
        // Save the selection permanently
        chrome.storage.local.set({ 'region': currentRegion }, () => {
            // If main section is active, reset UI to encourage new summary
            if (!mainSection.classList.contains('hidden')) {
                summaryBox.textContent = `Region switched to ${currentRegion}. Click button to summarize.`;
                btnSummarize.classList.remove('hidden');
                btnSave.classList.add('hidden');
            }
        });
    });

    // ============================================================
    // 2. Screen Transition Functions
    // ============================================================
    function showLoginSection() {
        loginSection.classList.remove('hidden');
        mainSection.classList.add('hidden');
        statusMsg.textContent = "";
    }

    function showMainSection() {
        loginSection.classList.add('hidden');
        mainSection.classList.remove('hidden');
        
        btnSummarize.classList.remove('hidden');
        btnSummarize.disabled = false;
        btnSummarize.textContent = "⚡️ Start Summarizing";
        
        btnSave.classList.add('hidden');
        btnSave.textContent = "💾 Save to My Library";
        btnSave.disabled = false;
        
        summaryBox.textContent = "Click the button to start AI summarization.";
    }

    // ============================================================
    // 3. Google Login Handler
    // ============================================================
    btnGoogle.addEventListener('click', () => {
        statusMsg.textContent = "Authenticating with Google...";
        
        chrome.identity.getAuthToken({ interactive: true }, function(token) {
            if (chrome.runtime.lastError || !token) {
                console.error(chrome.runtime.lastError);
                statusMsg.textContent = "Login failed: Popup blocked or closed.";
                return;
            }

            statusMsg.textContent = "Logging in to server...";

            fetch(`${SERVER_URL}/api/news/auth/google/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify({ access_token: token })
            })
            .then(res => {
                if (!res.ok) throw new Error("Server response error");
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
                    throw new Error(data.error || "Token generation failed");
                }
            })
            .catch(err => {
                statusMsg.textContent = "Login error: " + err.message;
                console.error(err);
            });
        });
    });

    // ============================================================
    // 4. Logout Handler
    // ============================================================
    btnLogout.addEventListener('click', (e) => {
        e.preventDefault(); 
        chrome.storage.local.remove('api_token', () => {
            userToken = null;
            showLoginSection();
        });
    });

    // ============================================================
    // 5. [Start Summarize] Button Logic
    // ============================================================
    btnSummarize.addEventListener('click', async () => {
        btnSummarize.disabled = true;
        summaryBox.textContent = ""; 
        statusMsg.textContent = "Verifying article URL...";

        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            currentUrl = tab.url;

            statusMsg.textContent = "AI is reading the article...";

            // [MODIFIED] Send 'region' in the request body
            const response = await fetch(`${SERVER_URL}/api/news/summarize/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${userToken}` 
                },
                body: JSON.stringify({ 
                    url: currentUrl,
                    region: currentRegion // <--- Sending selected region
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
                    summaryBox.textContent = `📚 Already saved in your library.\n(Date: ${new Date().toLocaleDateString()})`;
                    btnSummarize.textContent = "Already Saved";
                    statusMsg.textContent = "";
                    return;
                }
                
                throw new Error(errData.error || "Summarization failed");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            statusMsg.textContent = "Writing summary...";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                summaryBox.textContent += chunk;
                summaryBox.scrollTop = summaryBox.scrollHeight;
            }

            btnSummarize.classList.add('hidden'); 
            btnSave.classList.remove('hidden');   
            statusMsg.textContent = "Done! Do you want to save this?";

        } catch (error) {
            summaryBox.textContent = "❌ Error: " + error.message;
            btnSummarize.disabled = false;
            btnSummarize.textContent = "Try Again";
            statusMsg.textContent = "";
        }
    });

    // ============================================================
    // 6. [Save] Button Logic
    // ============================================================
    btnSave.addEventListener('click', async () => {
        statusMsg.textContent = "Saving...";
        
        const finalSummary = summaryBox.textContent;

        try {
            // [MODIFIED] Send 'region' when saving as well (to tag DB correctly)
            const response = await fetch(`${SERVER_URL}/api/news/save/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${userToken}` 
                },
                body: JSON.stringify({ 
                    url: currentUrl,
                    summary: finalSummary,
                    region: currentRegion // <--- Sending region tag
                })
            });

            if (response.ok) {
                btnSave.textContent = "Saved ✅";
                btnSave.disabled = true;
                statusMsg.textContent = "Securely saved to your library.";
                setTimeout(() => window.close(), 1500);
            } else {
                const errData = await response.json();
                throw new Error(errData.error || "Save failed");
            }
        } catch (error) {
            statusMsg.textContent = "Save failed: " + error.message;
        }
    });

    // ============================================================
    // 7. [Dashboard] Button Logic
    // ============================================================
    if (btnGraph) {
        btnGraph.addEventListener('click', () => {
            if (!userToken) {
                alert("Login required.");
                return;
            }

            // [MODIFIED] Append 'region' query parameter
            const targetUrl = `${SERVER_URL}/api/news/dashboard/?token=${userToken}&region=${currentRegion}`;
            chrome.tabs.create({ url: targetUrl });
        });
    }
});