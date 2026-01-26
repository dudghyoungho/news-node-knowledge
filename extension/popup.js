// Django Server URL (Adjust based on your urls.py)
const SERVER_URL = "http://43.203.231.70"; 

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const loginSection = document.getElementById('login-section');
    const mainSection = document.getElementById('main-section');
    
    const btnGoogle = document.getElementById('btn-google-login');
    const btnLogout = document.getElementById('btn-logout');
    
    const btnSummarize = document.getElementById('btn-summarize');
    const btnSave = document.getElementById('btn-save');

    const btnGraph = document.getElementById('btn-graph');
    
    const summaryBox = document.getElementById('summary-box');
    const statusMsg = document.getElementById('status');

    let userToken = null;
    let currentUrl = "";

    // ============================================================
    // 1. Initialization: Check for saved token (Auto Login)
    // ============================================================
    chrome.storage.local.get(['api_token'], (result) => {
        if (result.api_token) {
            console.log("Auto-login successful");
            userToken = result.api_token;
            showMainSection();
        } else {
            showLoginSection();
        }
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
        
        // Reset button states when entering main screen
        btnSummarize.classList.remove('hidden');
        btnSummarize.disabled = false;
        btnSummarize.textContent = "⚡️ Start Summarizing"; // Fixed typo: Summerizing -> Summarizing
        
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
        
        // 1. Request Google Token from Chrome
        chrome.identity.getAuthToken({ interactive: true }, function(token) {
            if (chrome.runtime.lastError || !token) {
                console.error(chrome.runtime.lastError);
                statusMsg.textContent = "Login failed: Popup blocked or closed.";
                return;
            }

            statusMsg.textContent = "Logging in to server...";

            // 2. Send Google Token to Django Server
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
                    // 3. Save token to Chrome Storage
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
        // Remove saved token
        chrome.storage.local.remove('api_token', () => {
            userToken = null;
            showLoginSection();
        });
    });

    // ============================================================
    // 5. [Start Summarize] Button Logic (Streaming)
    // ============================================================
    btnSummarize.addEventListener('click', async () => {
        // Lock UI
        btnSummarize.disabled = true;
        summaryBox.textContent = ""; 
        statusMsg.textContent = "Verifying article URL...";

        try {
            // Get current tab URL
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            currentUrl = tab.url;

            statusMsg.textContent = "AI is reading the article...";

            // Server Request
            const response = await fetch(`${SERVER_URL}/api/news/summarize/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${userToken}` 
                },
                body: JSON.stringify({ url: currentUrl })
            });

            // Error Handling
            if (!response.ok) {
                // 401 Unauthorized
                if (response.status === 401) {
                    alert("Session expired. Please log in again.");
                    btnLogout.click();
                    return;
                }

                const errData = await response.json();
                
                // Already Saved
                if (errData.status === 'ALREADY_SAVED') {
                    summaryBox.textContent = `📚 Already saved in your library.\n(Date: ${new Date().toLocaleDateString()})`;
                    btnSummarize.textContent = "Already Saved";
                    statusMsg.textContent = "";
                    return;
                }
                
                throw new Error(errData.error || "Summarization failed");
            }

            // Stream Handling
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            statusMsg.textContent = "Writing summary...";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                summaryBox.textContent += chunk;
                
                // Auto Scroll
                summaryBox.scrollTop = summaryBox.scrollHeight;
            }

            // UI Update on Completion
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
            const response = await fetch(`${SERVER_URL}/api/news/save/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${userToken}` 
                },
                body: JSON.stringify({ 
                    url: currentUrl,
                    summary: finalSummary 
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
            console.log("Current Token:", userToken); 

            if (!userToken) {
                alert("Login required.");
                return;
            }

            const targetUrl = `${SERVER_URL}/api/news/dashboard/?token=${userToken}`;
            console.log("Target URL:", targetUrl); 

            chrome.tabs.create({ url: targetUrl });
        });
    }
});