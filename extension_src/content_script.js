// content_script.js

if (window.hasRun) {
    // 중복 실행 방지: 이미 실행된 경우 아무것도 하지 않음
    console.log("[NewsNode] Content script already running.");
} else {
    window.hasRun = true;

    // URL 정제
    const rawUrl = window.location.href;
    const cleanUrl = rawUrl.split('?')[0].split('#')[0];

    // ============================================================
    // 1. Active Time (실제 보고 있는 시간) 측정 로직
    // ============================================================
    let totalActiveTime = 0;
    let lastStartTime = Date.now();
    let isTabVisible = true;

    // 탭 상태 변경 감지 (화면 켜짐/꺼짐)
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            // 숨겨질 때: 지금까지 본 시간을 누적
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
    // 2. 변수 및 설정 (Tracking 설정 추가)
    // ============================================================
    let maxScroll = 0;
    let clickCount = 0;
    let isLogSent = false;
    
    // 캐싱 변수
    let cachedToken = null;
    let cachedRegion = 'KR';
    let isTrackingEnabled = true; // [New] 기본값: 수집 허용 (저장된 값 없으면 true)

    console.log(`[NewsNode] Tracker Ready: ${cleanUrl}`);

    // 스토리지에서 토큰, 지역, 그리고 [추가된] 추적 설정 불러오기
    chrome.storage.local.get(['api_token', 'region', 'enableTracking'], function(result) {
        if (result.api_token) {
            cachedToken = result.api_token;
            console.log("[NewsNode] Token loaded.");
        } else {
            console.warn("[NewsNode] No token found. Please login via popup.");
        }
        
        if (result.region) cachedRegion = result.region;

        // [New] 추적 설정 로드 (undefined면 true로 간주)
        // 사용자가 명시적으로 껐을 때(false)만 false가 됨
        if (result.enableTracking === false) {
            isTrackingEnabled = false;
            console.log("[NewsNode] Context learning is DISABLED by user.");
        } else {
            isTrackingEnabled = true;
            console.log("[NewsNode] Context learning is ENABLED.");
        }
    });

    // 설정 변경 감지 (Popup에서 끄면 즉시 반영)
    chrome.storage.onChanged.addListener((changes, namespace) => {
        if (namespace === 'local' && changes.enableTracking) {
            isTrackingEnabled = changes.enableTracking.newValue;
            console.log(`[NewsNode] Tracking setting changed to: ${isTrackingEnabled}`);
        }
    });

    // ============================================================
    // 3. 메타데이터 추출 (기존 유지)
    // ============================================================
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
            description: getMeta("og:description") || getMeta("description"),
            image_url: getMeta("og:image"),
            category: category || 'General',
            og_type: getMeta("og:type"),
            published_time: getMeta("article:published_time")
        };
    }

    // ============================================================
    // 4. 기사 판별 로직 (RSS 사이트 호환성 유지)
    // ============================================================
    function isTargetArticle(metaInfo) {
        const url = cleanUrl; 

        if (url.length < 15) return false;

        // [Global & AU]
        if (url.includes('abc.net.au')) {
            if (url.includes('/news/') && /\/\d{4}-\d{2}-\d{2}\//.test(url)) return true;
            if (metaInfo.og_type === 'article') return true;
            return false;
        }
        if (url.includes('theguardian.com')) return /\/\d{4}\//.test(url);
        if (url.includes('news.com.au')) return metaInfo.og_type === 'article';
        if (url.includes('businessnews.com.au')) return url.includes('/article/');
        if (url.includes('theconversation.com')) return metaInfo.og_type === 'article';
        
        // [KR - Portal]
        if (url.includes('naver.com') || url.includes('daum.net')) return (url.includes('/article/') || url.includes('/v/'));

        // [KR - RSS Specific]
        // 1. 매일경제 (mk.co.kr)
        if (url.includes('mk.co.kr')) {
            if (url.includes('/news/')) return true;
            if (metaInfo.og_type === 'article') return true;
            return false;
        }

        // 2. 전자신문 (etnews.com)
        if (url.includes('etnews.com')) {
            if (/\/\d{8,}/.test(url)) return true; 
            if (metaInfo.og_type === 'article') return true;
            return false;
        }

        // 3. 노컷뉴스, SBS, 동아일보, 정책브리핑 등
        if (url.includes('nocutnews.co.kr') && url.includes('/news/')) return true;
        if (url.includes('sbs.co.kr') && (url.includes('/news/') || url.includes('news.sbs.co.kr'))) return true;
        if (url.includes('donga.com') && url.includes('/news/')) return true;
        if (url.includes('korea.kr') && url.includes('/newsWeb/')) return true; // 정책브리핑

        // [Tech Blogs]
        if (url.includes('medium.com')) return true;
        if (url.includes('velog.io')) return true;
        if (url.includes('woowahan.com')) return true;

        // [범용 필터]
        if (metaInfo.og_type === 'article') {
            if (!metaInfo.title || metaInfo.title.length < 5) return false;
            return true;
        }
        
        // 날짜 패턴 (블로그 등)
        if (url.match(/\/\d{4}\/\d{2}\/\d{2}\//)) return true;

        return false;
    }

    // ============================================================
    // 5. 로그 전송 (설정 체크 추가됨)
    // ============================================================
    function sendLog() {
        // [New] 사용자가 추적을 껐으면 전송 중단
        if (!isTrackingEnabled) {
            console.log("[NewsNode] Log Skipped: User disabled tracking.");
            return;
        }

        if (isLogSent) return;
        if (!cachedToken) return;

        const activeSeconds = getActiveDuration();
        
        // 7초 미만 체류는 무시
        if (activeSeconds < 7) {
            console.log(`[NewsNode] Skipped: Too short (${activeSeconds}s).`);
            return; 
        }

        const metaInfo = extractMetaData();
        if (!isTargetArticle(metaInfo)) {
            isLogSent = true; 
            return;
        }

        const logData = {
            article_url: cleanUrl,
            dwell_time: activeSeconds, 
            scroll_depth: maxScroll,
            click_count: clickCount,
            is_valid_view: activeSeconds >= 15,
            region: cachedRegion,
            title: metaInfo.title,
            description: metaInfo.description ? metaInfo.description.substring(0, 300) : "",
            image_url: metaInfo.image_url,
            category: metaInfo.category
        };

        const apiBase = (typeof CONFIG !== 'undefined' && CONFIG.API_BASE_URL) 
                        ? CONFIG.API_BASE_URL 
                        : "https://news.young-dev.link"; 
        
        const targetUrl = `${apiBase}/api/news/logs/`;

        console.log("[NewsNode] Sending log (Direct w/ keepalive):", targetUrl);

        // [핵심 수정] Background를 거치지 않고 직접 전송 + keepalive: true
        // keepalive: true는 탭이 닫혀도 브라우저가 백그라운드에서 네트워크 요청을 완료하도록 보장합니다.
        fetch(targetUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${cachedToken}` // 캐시된 토큰 사용
            },
            body: JSON.stringify(logData),
            keepalive: true // ★ 이 옵션이 탭 닫기 시 전송을 보장함 ★
        }).catch(err => console.error("[NewsNode] Log send failed:", err));

        isLogSent = true;
    }

    // ============================================================
    // 6. 이벤트 리스너 등록
    // ============================================================
    
    // 스크롤 깊이 측정
    window.addEventListener('scroll', () => {
        const scrollTop = window.scrollY;
        const docHeight = document.body.scrollHeight - window.innerHeight;
        if (docHeight > 0) {
            const scrollPercent = Math.round((scrollTop / docHeight) * 100);
            if (scrollPercent > maxScroll) maxScroll = scrollPercent;
        }
    });

    // 클릭 횟수 측정
    document.addEventListener('click', () => {
        clickCount++;
    });

    // 종료 시점 감지 (페이지 이동, 닫기)
    window.addEventListener('pagehide', sendLog);
    
    // 탭 전환 시점 감지 (탭 숨겨질 때 전송 시도 - 모바일/백그라운드 전환 등)
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            sendLog();
        }
    });

    // Background의 PING 요청 응답 (Content Script 생존 확인용)
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.type === "PING") {
            sendResponse({ status: "ALIVE" });
        }
    });
}