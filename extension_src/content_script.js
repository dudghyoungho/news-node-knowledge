// extension_src/content_script.js

// 1. [상수 박제] URL 변조 방지
const CURRENT_PAGE_URL = window.location.href.split('?')[0];
const START_TIME = Date.now();

console.log(`[NewsNode] Tracking started for: ${CURRENT_PAGE_URL}`);

// 측정 변수
let maxScroll = 0;
let clickCount = 0;
let isLogSent = false;

// 설정 변수
let cachedToken = null;
let cachedRegion = 'KR';

// 2. 설정 로드
chrome.storage.local.get(['api_token', 'region'], function(result) {
    if (result.api_token) cachedToken = result.api_token;
    if (result.region) cachedRegion = result.region;
});

chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local') {
        if (changes.api_token) cachedToken = changes.api_token.newValue;
        if (changes.region) cachedRegion = changes.region.newValue;
    }
});

// 3. [NEW] 메타데이터 추출 함수 (빠져있던 부분!)
function extractMetaData() {
    const getMeta = (prop) => {
        return document.querySelector(`meta[property="${prop}"]`)?.content || 
               document.querySelector(`meta[name="${prop}"]`)?.content || '';
    };

    // A. 카테고리 (Guardian, News.com.au 표준 + 네이버 예외처리)
    let category = getMeta("article:section"); 
    if (!category) {
        // 네이버 뉴스
        const naverChannel = document.querySelector(".media_end_head_top_channel");
        if (naverChannel) category = naverChannel.innerText;
        // 네이버 스포츠/연예
        const naverMenu = document.querySelector(".Nlnb_menu_list .Nitem_link[aria-selected='true']");
        if (naverMenu) category = naverMenu.innerText;
    }

    // B. 제목, 설명, 이미지
    let title = getMeta("og:title") || document.title;
    let description = getMeta("og:description");
    let image_url = getMeta("og:image");

    return {
        title: title,
        description: description,
        image_url: image_url,
        category: category || 'General'
    };
}

// 4. 이벤트 리스너
document.addEventListener('DOMContentLoaded', () => {
    window.addEventListener('scroll', () => {
        if (!document.body) return;
        let scrollPercent = Math.round((window.scrollY + window.innerHeight) / document.body.scrollHeight * 100);
        if (scrollPercent > maxScroll) maxScroll = scrollPercent;
    });

    window.addEventListener('click', () => {
        clickCount++;
    });
});

// 5. 로그 전송 함수
function sendLog() {
    if (isLogSent) return;

    let duration = Math.round((Date.now() - START_TIME) / 1000);
    if (duration < 7) return;

    if (!cachedToken) {
        if (typeof CONFIG !== 'undefined' && CONFIG.ENV === 'development') console.log("[NewsNode] No token. Skip.");
        return;
    }

    // ★ [핵심 수정] 메타데이터 추출 실행
    const metaInfo = extractMetaData();

    const logData = {
        article_url: CURRENT_PAGE_URL,
        dwell_time: duration,
        scroll_depth: maxScroll,
        click_count: clickCount,
        is_valid_view: duration >= 30,
        region: cachedRegion,

        // ★ [핵심 수정] 추출한 메타데이터를 여기에 실어야 백엔드로 갑니다!
        title: metaInfo.title,
        description: metaInfo.description,
        image_url: metaInfo.image_url,
        category: metaInfo.category
    };

    const apiUrl = `${CONFIG.API_BASE_URL}/api/news/logs/`;
    isLogSent = true;

    chrome.runtime.sendMessage({
        type: 'SEND_LOG',
        payload: { apiUrl, logData, token: cachedToken }
    }, (response) => {
        if (!chrome.runtime.lastError) {
            console.log(`[NewsNode] Log saved: ${metaInfo.title}`);
        }
    });
}

// 6. 이탈 감지
window.addEventListener('beforeunload', sendLog);
window.addEventListener('pagehide', sendLog);
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'hidden') {
        sendLog();
    }
});

// 테스트용 L키
window.addEventListener('keydown', function(e) {
    if (e.key === 'l' || e.key === 'L') {
        isLogSent = false;
        sendLog();
    }
});