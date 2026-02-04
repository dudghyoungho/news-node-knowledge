// extension_src/background.js

// [중요] config.js를 불러와서 현재 환경(CONFIG.ENV)을 확인합니다.
try {
    importScripts('config.js');
} catch (e) {
    console.error("config.js 로드 실패:", e);
}

// 1. 설치 또는 업데이트 시 실행되는 이벤트
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === "install") {
        console.log(`[NewsNode] 설치 완료! (${CONFIG.ENV} 모드)`);
    } else if (details.reason === "update") {
        console.log(`[NewsNode] 업데이트 완료! (현재 버전: ${chrome.runtime.getManifest().version})`);
    }
});

// 2. 메시지 리스너 (핵심: Content Script의 심부름을 수행)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    // ★ [추가됨] Content Script가 "로그 보내줘(SEND_LOG)"라고 요청했을 때
    if (request.type === "SEND_LOG") {
        const { apiUrl, logData, token } = request.payload;

        // Background Script는 CORS나 Private Network 제한 없이 localhost에 접근 가능합니다.
        fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // 백엔드 설정에 맞춰 'Token' 또는 'Bearer' 사용 (현재 Token 사용 중)
                'Authorization': `Token ${token}` 
            },
            body: JSON.stringify(logData)
        })
        .then(response => {
            if (response.ok) {
                if (CONFIG.ENV === 'development') console.log(`[Background] Log sent successfully: ${logData.article_url}`);
            } else {
                console.error(`[Background] Server error (${response.status}):`, response.statusText);
            }
        })
        .catch(err => {
            console.error("[Background] Network error:", err);
        });

        // 비동기 작업이므로 true를 반환하여 채널을 유지하는 것이 관례지만,
        // fire-and-forget 방식이라 필수는 아님. (안전하게 return true)
        return true; 
    }

    return true; 
});

// 3. 스토리지 변경 감지 (디버깅용)
chrome.storage.onChanged.addListener((changes, namespace) => {
    // api_token으로 변경된 것 반영
    if (namespace === 'local' && changes.api_token) {
        const newToken = changes.api_token.newValue;
        if (newToken) {
            console.log("[Auth] 토큰이 저장/갱신되었습니다. (로그 수집 준비 완료)");
        } else {
            console.log("[Auth] 토큰이 삭제되었습니다. (로그아웃)");
        }
    }
});