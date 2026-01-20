// Django 서버 주소 (urls.py 설정에 맞춰 수정)
// 예: path('api/news/', include('news.urls')) 인 경우 아래와 같음
const SERVER_URL = "http://localhost:8000/api/news"; 

document.addEventListener('DOMContentLoaded', () => {
    // DOM 요소 가져오기
    const loginSection = document.getElementById('login-section');
    const mainSection = document.getElementById('main-section');
    
    const btnGoogle = document.getElementById('btn-google-login');
    const btnLogout = document.getElementById('btn-logout');
    
    const btnSummarize = document.getElementById('btn-summarize');
    const btnSave = document.getElementById('btn-save');
    
    const summaryBox = document.getElementById('summary-box');
    const statusMsg = document.getElementById('status');

    let userToken = null;
    let currentUrl = "";

    // ============================================================
    // 1. 초기화: 저장된 토큰이 있는지 확인 (자동 로그인)
    // ============================================================
    chrome.storage.local.get(['api_token'], (result) => {
        if (result.api_token) {
            console.log("자동 로그인 성공");
            userToken = result.api_token;
            showMainSection();
        } else {
            showLoginSection();
        }
    });

    // ============================================================
    // 2. 화면 전환 함수들
    // ============================================================
    function showLoginSection() {
        loginSection.classList.remove('hidden');
        mainSection.classList.add('hidden');
        statusMsg.textContent = "";
    }

    function showMainSection() {
        loginSection.classList.add('hidden');
        mainSection.classList.remove('hidden');
        
        // 메인 화면 진입 시 버튼 상태 초기화
        btnSummarize.classList.remove('hidden');
        btnSummarize.disabled = false;
        btnSummarize.textContent = "⚡️ 3줄 요약 시작";
        
        btnSave.classList.add('hidden');
        btnSave.textContent = "💾 내 서재에 저장";
        btnSave.disabled = false;
        
        summaryBox.textContent = "버튼을 누르면 AI가 기사를 읽기 시작합니다.";
    }

    // ============================================================
    // 3. 구글 로그인 핸들러
    // ============================================================
    btnGoogle.addEventListener('click', () => {
        statusMsg.textContent = "구글 인증 진행 중...";
        
        // 1. 크롬에게 구글 토큰 요청 (manifest.json의 oauth2 설정 사용)
        chrome.identity.getAuthToken({ interactive: true }, function(token) {
            if (chrome.runtime.lastError || !token) {
                console.error(chrome.runtime.lastError);
                statusMsg.textContent = "로그인 실패: 팝업이 차단되었거나 닫혔습니다.";
                return;
            }

            statusMsg.textContent = "서버 로그인 중...";

            // 2. Django 서버로 구글 토큰 전송 -> DRF 토큰 발급 요청
            fetch(`${SERVER_URL}/auth/google/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ access_token: token })
            })
            .then(res => {
                if (!res.ok) throw new Error("서버 응답 오류");
                return res.json();
            })
            .then(data => {
                if (data.token) {
                    userToken = data.token;
                    // 3. 토큰을 크롬 스토리지에 영구 저장 (앱을 껐다 켜도 유지)
                    chrome.storage.local.set({ 'api_token': userToken }, () => {
                        showMainSection();
                        statusMsg.textContent = "";
                    });
                } else {
                    throw new Error(data.error || "토큰 발급 실패");
                }
            })
            .catch(err => {
                statusMsg.textContent = "로그인 오류: " + err.message;
                console.error(err);
            });
        });
    });

    // ============================================================
    // 4. 로그아웃 핸들러
    // ============================================================
    btnLogout.addEventListener('click', (e) => {
        e.preventDefault(); // 링크 이동 방지
        // 저장된 토큰 삭제
        chrome.storage.local.remove('api_token', () => {
            userToken = null;
            showLoginSection();
            
            // (선택) 구글 인증 캐시 삭제 (완전 로그아웃 원할 시 주석 해제)
            // chrome.identity.getAuthToken({ 'interactive': false }, function(current_token) {
            //   if (!chrome.runtime.lastError && current_token) {
            //     chrome.identity.removeCachedAuthToken({ token: current_token }, function() {});
            //   }
            // });
        });
    });

    // ============================================================
    // 5. [요약 시작] 버튼 로직 (Streaming)
    // ============================================================
    btnSummarize.addEventListener('click', async () => {
        // UI 잠금
        btnSummarize.disabled = true;
        summaryBox.textContent = ""; 
        statusMsg.textContent = "기사 주소를 확인 중...";

        try {
            // 현재 활성화된 탭의 URL 가져오기
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            currentUrl = tab.url;

            statusMsg.textContent = "AI가 기사를 읽고 있습니다...";

            // 서버 요청 (헤더에 토큰 포함!)
            const response = await fetch(`${SERVER_URL}/summarize/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${userToken}`  // ★ 핵심: 인증 헤더
                },
                body: JSON.stringify({ url: currentUrl })
            });

            // 에러 처리
            if (!response.ok) {
                // 401 Unauthorized: 토큰 만료됨 -> 로그아웃 처리
                if (response.status === 401) {
                    alert("로그인 세션이 만료되었습니다. 다시 로그인해주세요.");
                    btnLogout.click();
                    return;
                }

                const errData = await response.json();
                
                // 이미 저장된 기사일 경우
                if (errData.status === 'ALREADY_SAVED') {
                    summaryBox.textContent = "📚 이미 서재에 저장된 기사입니다.\n(날짜: " + new Date().toLocaleDateString() + ")";
                    btnSummarize.textContent = "저장 완료됨";
                    statusMsg.textContent = "";
                    return;
                }
                
                throw new Error(errData.error || "요약 실패");
            }

            // ★ 스트리밍 데이터 처리 (한 글자씩 타자기처럼)
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            statusMsg.textContent = "작성 중...";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                summaryBox.textContent += chunk;
                
                // 스크롤을 항상 아래로 유지
                summaryBox.scrollTop = summaryBox.scrollHeight;
            }

            // 완료 후 UI 변경
            btnSummarize.classList.add('hidden'); // 요약 버튼 숨기기
            btnSave.classList.remove('hidden');   // 저장 버튼 보이기
            statusMsg.textContent = "요약 완료! 저장하시겠습니까?";

        } catch (error) {
            summaryBox.textContent = "❌ 에러 발생: " + error.message;
            btnSummarize.disabled = false;
            btnSummarize.textContent = "다시 시도";
            statusMsg.textContent = "";
        }
    });

    // ============================================================
    // 6. [저장] 버튼 로직
    // ============================================================
    btnSave.addEventListener('click', async () => {
        statusMsg.textContent = "저장 중...";
        
        // ★ 추가: 화면에 있는 요약문 가져오기
        const finalSummary = summaryBox.textContent;

        try {
            const response = await fetch(`${SERVER_URL}/save/`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${userToken}` 
                },
                // ★ 수정: url 뿐만 아니라 summary도 함께 전송
                body: JSON.stringify({ 
                    url: currentUrl,
                    summary: finalSummary 
                })
            });

            if (response.ok) {
                btnSave.textContent = "저장 완료 ✅";
                btnSave.disabled = true;
                statusMsg.textContent = "내 서재에 안전하게 보관되었습니다.";
                setTimeout(() => window.close(), 1500);
            } else {
                const errData = await response.json();
                throw new Error(errData.error || "저장 실패");
            }
        } catch (error) {
            statusMsg.textContent = "저장 실패: " + error.message;
        }
    });
});

