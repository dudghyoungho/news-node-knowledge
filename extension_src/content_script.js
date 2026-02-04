// extension_src/content_script.js

console.log(`[NewsNode] Logger started in ${CONFIG.ENV} mode.`);

let startTime = Date.now();
let maxScroll = 0;
let clickCount = 0;

// 1. 토큰과 지역 정보를 담을 변수
let cachedToken = null;
let cachedRegion = 'KR'; 

// ================================================================
// 초기화: 저장된 토큰과 지역 정보 로드
// ================================================================
chrome.storage.local.get(['api_token', 'region'], function(result) {
    if (result.api_token) {
        cachedToken = result.api_token;
        console.log("[NewsNode] Initial Token loaded.");
    } else {
        console.log("[NewsNode] No token initially. Waiting for login...");
    }

    if (result.region) {
        cachedRegion = result.region;
        console.log(`[NewsNode] Region set to: ${cachedRegion}`);
    }
});

// ================================================================
// 실시간 감지: 팝업에서 로그인/지역 변경 시 즉시 반영
// ================================================================
chrome.storage.onChanged.addListener(function(changes, namespace) {
    if (namespace === 'local') {
        // 토큰 변경 감지
        if (changes.api_token) {
            if (changes.api_token.newValue) {
                cachedToken = changes.api_token.newValue;
                console.log("[NewsNode] Token updated in real-time!");
            } else {
                cachedToken = null;
                console.log("[NewsNode] Token removed (Logged out).");
            }
        }
        
        // 지역 변경 감지
        if (changes.region) {
            cachedRegion = changes.region.newValue || 'KR';
            console.log(`[NewsNode] Region updated to: ${cachedRegion}`);
        }
    }
});

// 3. 스크롤 추적
window.addEventListener('scroll', () => {
    let scrollPercent = Math.round(
        (window.scrollY + window.innerHeight) / document.body.scrollHeight * 100
    );
    if (scrollPercent > maxScroll) maxScroll = scrollPercent;
});

// 4. 클릭 추적
window.addEventListener('click', () => {
    clickCount++;
});

// 5. 로그 전송 (페이지를 떠날 때)
function sendLog() {
    let duration = Math.round((Date.now() - startTime) / 1000);

    // 5초 미만 무시 (테스트 시엔 1초로 줄여도 됨)
    if (duration < 5) return;

    // 토큰 없으면 중단
    if (!cachedToken) {
        if (CONFIG.ENV === 'development') console.log("[NewsNode] No token. Skip.");
        return;
    }

    const logData = {
        article_url: window.location.href.split('?')[0],
        dwell_time: duration,
        scroll_depth: maxScroll,
        click_count: clickCount,
        is_valid_view: duration >= 30,
        region: cachedRegion 
    };

    const apiUrl = `${CONFIG.API_BASE_URL}/api/news/logs/`;

    // ★ [핵심 수정] 직접 fetch하지 않고, Background Script에 "대신 보내줘" 요청
    chrome.runtime.sendMessage({
        type: 'SEND_LOG',
        payload: {
            apiUrl: apiUrl,
            logData: logData,
            token: cachedToken
        }
    }, function(response) {
        // 탭이 닫히는 순간에는 이 콜백이 실행되지 않을 수 있지만 에러 방지용입니다.
        if (chrome.runtime.lastError) {
            // Background Script가 깨어나지 못했거나 연결 오류 시
            console.error("Message sending failed:", chrome.runtime.lastError);
        } else {
            console.log("[NewsNode] Log request sent to background.");
        }
    });
}

// 6. 전송 트리거
window.addEventListener('beforeunload', sendLog);
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'hidden') sendLog();
});

// [디버깅용] L키 눌러서 강제 전송
window.addEventListener('keydown', function(e) {
    if (e.key === 'l' || e.key === 'L') {
        console.log("[NewsNode] Manual Log Triggered via Keydown!");
        sendLog();
    }
});