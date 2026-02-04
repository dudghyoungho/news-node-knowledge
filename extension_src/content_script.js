// extension_src/content_script.js

// 1. [핵심] 스크립트 시작 시점의 URL을 상수로 박제 (절대 변하지 않음)
const CURRENT_PAGE_URL = window.location.href.split('?')[0];
const START_TIME = Date.now();

console.log(`[NewsNode] Tracking started for: ${CURRENT_PAGE_URL}`);

// 측정 변수
let maxScroll = 0;
let clickCount = 0;
let isLogSent = false; // 중복 방지 깃발

// 설정 변수
let cachedToken = null;
let cachedRegion = 'KR';

// 2. 설정 로드 (비동기이므로 빨리 실행해둠)
chrome.storage.local.get(['api_token', 'region'], function(result) {
    if (result.api_token) cachedToken = result.api_token;
    if (result.region) cachedRegion = result.region;
});

// 설정 변경 감지
chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local') {
        if (changes.api_token) cachedToken = changes.api_token.newValue;
        if (changes.region) cachedRegion = changes.region.newValue;
    }
});

// 3. 스크롤 & 클릭 이벤트 (DOM이 로드된 후에 붙여야 안전함)
// document_start로 바꿨으므로, DOMContentLoaded 이벤트를 기다림
document.addEventListener('DOMContentLoaded', () => {
    window.addEventListener('scroll', () => {
        // body가 없을 수도 있으므로 안전장치
        if (!document.body) return;
        let scrollPercent = Math.round((window.scrollY + window.innerHeight) / document.body.scrollHeight * 100);
        if (scrollPercent > maxScroll) maxScroll = scrollPercent;
    });

    window.addEventListener('click', () => {
        clickCount++;
    });
});

// 4. 로그 전송 함수 (단순화)
function sendLog() {
    // 이미 보냈으면 절대 다시 보내지 않음 (Strict Mode)
    if (isLogSent) return;

    // 체류 시간 계산
    let duration = Math.round((Date.now() - START_TIME) / 1000);

    // [설정] 7초 미만은 칼같이 무시
    if (duration < 7) {
        // 개발 모드에서만 로그 찍기 (너무 짧음)
        // console.log(`[NewsNode] Too short (${duration}s). Ignored.`);
        return;
    }

    if (!cachedToken) {
        if (CONFIG && CONFIG.ENV === 'development') console.log("[NewsNode] No token. Skip.");
        return;
    }

    const logData = {
        // ★ 여기서 window.location.href를 쓰지 않고, 박제해둔 상수를 씁니다.
        article_url: CURRENT_PAGE_URL, 
        dwell_time: duration,
        scroll_depth: maxScroll,
        click_count: clickCount,
        is_valid_view: duration >= 30,
        region: cachedRegion 
    };

    const apiUrl = `${CONFIG.API_BASE_URL}/api/news/logs/`;

    // 깃발 꽂기 (중복 방지)
    isLogSent = true;

    chrome.runtime.sendMessage({
        type: 'SEND_LOG',
        payload: { apiUrl, logData, token: cachedToken }
    }, (response) => {
        if (!chrome.runtime.lastError) {
            console.log(`[NewsNode] Log saved for ${CURRENT_PAGE_URL} (${duration}s)`);
        }
    });
}

// 5. [핵심] 페이지 이탈 감지 (가장 강력한 조합)

// A. 탭을 닫거나 새로고침 할 때 (PC 표준)
window.addEventListener('beforeunload', sendLog);

// B. 모바일이나 뒤로가기 캐시(bfcache)로 이동할 때 (최신 브라우저 표준)
window.addEventListener('pagehide', sendLog);

// C. 탭 전환 시 (visibilitychange)
// 주의: 탭을 잠깐 바꿨다 돌아오는 것은 '이탈'로 보지 않고 시간을 계속 잴 것인가?
// 사용자의 요청: "중복 저장 방지". 따라서 탭 전환시에는 보내지 않고, 
// "아예 탭을 닫거나 URL이 바뀔 때"만 보내는 것이 가장 깔끔함.
// 하지만 '브라우저 종료'를 visibilitychange로만 잡는 경우도 있으므로 아래 로직 사용:

document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'hidden') {
        // 탭을 가렸을 때 일단 보냄? -> 
        // 문제는 "잠깐 가렸다가 돌아오면" 이미 isLogSent가 true라서 로그가 끝남.
        // 로그 누락을 막기 위해 "hidden 상태에서는 무조건 시도" 하되, 
        // 탭을 닫는게 아니라면 사용자가 돌아왔을 때 로그가 끊기는 단점이 있음.
        
        // 타협안: 7초 이상 읽었으면 일단 저장. (데이터 보존 우선)
        sendLog();
    }
});

// [테스트용] L키 강제 전송
window.addEventListener('keydown', function(e) {
    if (e.key === 'l' || e.key === 'L') {
        isLogSent = false; // 테스트니까 깃발 잠시 해제
        sendLog();
    }
});