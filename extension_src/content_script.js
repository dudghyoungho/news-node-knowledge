if (window.hasRun) {
    // 중복 실행 방지
} else {
    window.hasRun = true;

    // URL 정제
    const rawUrl = window.location.href;
    const cleanUrl = rawUrl.split('?')[0].split('#')[0];

    // ============================================================
    // [수정 1] Active Time (실제 보고 있는 시간) 측정 로직
    // ============================================================
    let totalActiveTime = 0;
    let lastStartTime = Date.now();
    let isTabVisible = true;

    // 탭 상태 변경 감지 (화면 켜짐/꺼짐)
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            // 숨겨질 때: 지금까지 본 시간을 누적하고 타이머 정지
            if (isTabVisible) {
                totalActiveTime += (Date.now() - lastStartTime);
                isTabVisible = false;
            }
        } else {
            // 다시 보일 때: 타이머 재시작
            lastStartTime = Date.now();
            isTabVisible = true;
        }
    });

    // 현재까지의 총 유효 시간 계산 함수
    function getActiveDuration() {
        let currentSession = 0;
        if (isTabVisible) {
            currentSession = Date.now() - lastStartTime;
        }
        return Math.round((totalActiveTime + currentSession) / 1000);
    }

    // ============================================================
    // 변수 및 설정
    // ============================================================
    let maxScroll = 0;
    let clickCount = 0;
    let isLogSent = false;
    let cachedToken = null;
    let cachedRegion = 'KR';

    console.log(`[NewsNode] Tracker Ready: ${cleanUrl}`);

    chrome.storage.local.get(['api_token', 'region'], function(result) {
        if (result.api_token) {
            cachedToken = result.api_token;
            console.log("[NewsNode] Token loaded.");
        } else {
            console.warn("[NewsNode] No token found. Please login via popup.");
        }
        if (result.region) cachedRegion = result.region;
    });

    // ... (extractMetaData 함수는 기존과 동일하므로 생략, 그대로 두세요) ...
    function extractMetaData() {
        const getMeta = (prop) => {
            return document.querySelector(`meta[property="${prop}"]`)?.content || 
                   document.querySelector(`meta[name="${prop}"]`)?.content || '';
        };
        let category = getMeta("article:section"); 
        if (!category) {
            const naverChannel = document.querySelector(".media_end_head_top_channel");
            if (naverChannel) category = naverChannel.innerText;
        }
        return {
            title: getMeta("og:title") || document.title,
            description: getMeta("og:description"),
            image_url: getMeta("og:image"),
            category: category || 'General',
            og_type: getMeta("og:type"),
            published_time: getMeta("article:published_time")
        };
    }

    // ... (isTargetArticle 함수 기존과 동일) ...
    function isTargetArticle(metaInfo) {
        const url = cleanUrl;
        if (url.length < 15) return false;
        if (url.includes('theguardian.com')) return /\/\d{4}\//.test(url);
        if (url.includes('news.com.au')) return metaInfo.og_type === 'article';
        if (url.includes('naver.com') || url.includes('daum.net')) return (url.includes('/article/') || url.includes('/v/'));
        if (metaInfo.og_type === 'article') return (!metaInfo.title || metaInfo.title.length >= 5);
        if (url.match(/\/\d{4}\/\d{2}\/\d{2}\//)) return true;
        return false;
    }

    // 스크롤/클릭 이벤트 (기존 동일)
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (scrollTimeout) return;
        scrollTimeout = setTimeout(() => {
            if (document.body) {
                let scrollPercent = Math.round((window.scrollY + window.innerHeight) / document.body.scrollHeight * 100);
                if (scrollPercent > maxScroll) maxScroll = scrollPercent;
            }
            scrollTimeout = null;
        }, 500);
    });
    window.addEventListener('click', () => clickCount++);

    // ============================================================
    // [수정 2] 로그 전송 (디버깅 강화)
    // ============================================================
    function sendLog() {
        // 1. 중복 전송 방지
        if (isLogSent) return;

        // 2. 토큰 체크
        if (!cachedToken) {
            console.warn("[NewsNode] Cannot send log: Missing API Token.");
            return;
        }

        // 3. 시간 체크 (Active Time 사용)
        const activeSeconds = getActiveDuration();
        console.log(`[NewsNode] Time check: ${activeSeconds}s active.`);

        if (activeSeconds < 7) {
            console.log("[NewsNode] Skipped: Dwell time too short.");
            return; 
        }

        // 4. 기사 유효성 체크
        const metaInfo = extractMetaData();
        if (!isTargetArticle(metaInfo)) {
            console.log("[NewsNode] Skipped: Not a target article.");
            isLogSent = true; 
            return;
        }

        // 5. 데이터 구성
        const logData = {
            article_url: cleanUrl,
            dwell_time: activeSeconds, // [수정] Wall clock이 아닌 Active Time 전송
            scroll_depth: maxScroll,
            click_count: clickCount,
            is_valid_view: activeSeconds >= 15,
            region: cachedRegion,
            title: metaInfo.title,
            description: metaInfo.description ? metaInfo.description.substring(0, 300) : "",
            image_url: metaInfo.image_url,
            category: metaInfo.category
        };

        // 6. 전송 시도 (URL 하드코딩으로 config.js 의존성 문제 회피 시도 - 테스트용)
        // 만약 config.js가 잘 작동한다면 CONFIG.API_BASE_URL 사용
        const apiBase = (typeof CONFIG !== 'undefined' && CONFIG.API_BASE_URL) 
                        ? CONFIG.API_BASE_URL 
                        : "http://localhost:8000"; 

        console.log("[NewsNode] Sending log to:", `${apiBase}/api/news/logs/`);
        console.log("[NewsNode] Data:", logData);

        chrome.runtime.sendMessage({
            type: 'SEND_LOG',
            payload: { 
                apiUrl: `${apiBase}/api/news/logs/`, 
                logData, 
                token: cachedToken 
            }
        });

        isLogSent = true;
    }

    // 종료 감지
    window.addEventListener('pagehide', sendLog);
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            sendLog();
        }
    });

    // [추가됨] Background의 중복 주입 방지 체크(PING)에 응답
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.type === "PING") {
            sendResponse({ status: "ALIVE" });
        }
    });
} // <--- 기존 else 블록 닫는 괄호