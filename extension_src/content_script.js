// extension_src/content_script.js

const CURRENT_PAGE_URL = window.location.href.split('?')[0];
const START_TIME = Date.now();

console.log(`[NewsNode] Script loaded for: ${CURRENT_PAGE_URL}`);

// 측정 변수
let maxScroll = 0;
let clickCount = 0;
let isLogSent = false;

// 설정 변수
let cachedToken = null;
let cachedRegion = 'KR';

// 설정 로드
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

// 1. 메타데이터 추출 함수
function extractMetaData() {
    const getMeta = (prop) => {
        return document.querySelector(`meta[property="${prop}"]`)?.content || 
               document.querySelector(`meta[name="${prop}"]`)?.content || '';
    };

    // A. 카테고리
    let category = getMeta("article:section"); 
    if (!category) {
        const naverChannel = document.querySelector(".media_end_head_top_channel");
        if (naverChannel) category = naverChannel.innerText;
        const naverMenu = document.querySelector(".Nlnb_menu_list .Nitem_link[aria-selected='true']");
        if (naverMenu) category = naverMenu.innerText;
    }

    // B. 기본 정보
    return {
        title: getMeta("og:title") || document.title,
        description: getMeta("og:description"),
        image_url: getMeta("og:image"),
        category: category || 'General',
        
        // [필터링용] 타입과 발행일 추가 추출
        og_type: getMeta("og:type"),
        published_time: getMeta("article:published_time")
    };
}

// 2. [핵심] 기사 페이지 판별 함수 (사이트별 맞춤 로직)
function isTargetArticle(metaInfo) {
    const url = CURRENT_PAGE_URL;

    // 1. [기존] 특정 사이트별 정밀 로직 (우선 적용)
    // A. The Guardian
    if (url.includes('theguardian.com')) {
        if (!metaInfo.description) return false;
        if (!/\/\d{4}\//.test(url)) return false;
        return true; 
    }

    // B. news.com.au
    if (url.includes('news.com.au')) {
        if (metaInfo.og_type && metaInfo.og_type !== 'article') return false;
        if (!metaInfo.published_time) return false;
        return true;
    }

    // C. 네이버 & 다음 (국내 포털)
    if (url.includes('naver.com') || url.includes('daum.net')) {
        // 네이버/다음은 뉴스 URL 패턴이 확실하므로 패턴으로 거름
        if (url.includes('/article/') || url.includes('/v/')) return true;
        return false;
    }

    // ============================================================
    // 2. [추가] 그 외 모든 사이트 (범용 필터)
    // ============================================================
    
    // 유튜브, 구글, 쇼핑몰 등은 여기서 걸러짐
    if (url.includes('youtube.com') || url.includes('google.com') || url.includes('coupang.com')) {
        return false;
    }

    // ★ 핵심: 표준 메타태그(og:type)가 'article'인 경우만 수집
    // 대부분의 언론사(CNN, BBC, Velog, Medium 등)는 이를 준수함
    if (metaInfo.og_type === 'article') {
        // 내용이 너무 부실하면(제목 5자 미만) 거름
        if (!metaInfo.title || metaInfo.title.length < 5) return false;
        return true;
    }

    // 위 조건에 안 맞으면 기사가 아니라고 판단
    return false;
}

// 3. 이벤트 리스너
document.addEventListener('DOMContentLoaded', () => {
    // DOM 로드 직후 바로 체크하지 않음 (메타 태그가 늦게 뜰 수 있음)
    // sendLog 시점에 체크하도록 변경하여 리소스 절약
    
    window.addEventListener('scroll', () => {
        if (!document.body) return;
        let scrollPercent = Math.round((window.scrollY + window.innerHeight) / document.body.scrollHeight * 100);
        if (scrollPercent > maxScroll) maxScroll = scrollPercent;
    });

    window.addEventListener('click', () => {
        clickCount++;
    });
});

// 4. 로그 전송 함수
function sendLog() {
    if (isLogSent) return;

    let duration = Math.round((Date.now() - START_TIME) / 1000);
    // 7초 미만 무시
    if (duration < 7) return;

    if (!cachedToken) return;

    // ★ 메타데이터 추출 및 필터링 수행
    const metaInfo = extractMetaData();

    // ★ [여기서 필터링] 기사가 아니면 전송 중단
    if (!isTargetArticle(metaInfo)) {
        // 이미 7초가 지났으니, 기사가 아니라고 판단되면 깃발 꽂고 종료 (더 이상 체크 안함)
        isLogSent = true; 
        return;
    }

    const logData = {
        article_url: CURRENT_PAGE_URL,
        dwell_time: duration,
        scroll_depth: maxScroll,
        click_count: clickCount,
        is_valid_view: duration >= 30,
        region: cachedRegion,
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

// 5. 이탈 감지
window.addEventListener('beforeunload', sendLog);
window.addEventListener('pagehide', sendLog);
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'hidden') {
        sendLog();
    }
});

window.addEventListener('keydown', function(e) {
    if (e.key === 'l' || e.key === 'L') {
        isLogSent = false;
        sendLog();
    }
});