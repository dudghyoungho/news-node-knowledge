// extension_src/background.js

// 1. 설정 파일 로드 (환경 변수 등)
try {
    importScripts('config.js');
} catch (e) {
    console.error("[NewsNode] config.js 로드 실패:", e);
}

// 2. 뉴스 사이트 도메인 화이트리스트 (감지 대상)
// RSS 피드 및 주요 뉴스 사이트를 모두 포함합니다.
const NEWS_DOMAINS = [
    // [Global & US]
    "cnn.com", 
    "bbc.com", 
    "nytimes.com",
    "theguardian.com",
    "abcnews.go.com", // 미국 ABC

    // [Australia]
    "news.com.au", 
    "abc.net.au",     // 호주 ABC
    "businessnews.com.au",
    "theconversation.com",
    "sbs.com.au",

    // [Korea - Portal]
    "news.naver.com", 
    "v.daum.net", 

    // [Korea - RSS Feeds]
    "mk.co.kr",         // 매일경제
    "etnews.com",       // 전자신문
    "nocutnews.co.kr",  // 노컷뉴스
    "sbs.co.kr",        // SBS (한국)
    "donga.com",        // 동아일보 (스포츠동아 포함)

    // [Tech & Blogs]
    "medium.com", 
    "velog.io"
];

// 3. 탭 업데이트 감지 (Lazy Injection & Duplicate Check)
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    // 페이지 로딩이 완료되었고 URL이 존재할 때만 실행
    if (changeInfo.status === 'complete' && tab.url) {
        
        // 현재 URL이 화이트리스트에 포함되는지 확인
        const isNewsSite = NEWS_DOMAINS.some(domain => tab.url.includes(domain));
        
        if (isNewsSite) {
            // console.log(`[NewsNode] Target detected: ${tab.url}`);

            // [핵심] 스크립트 중복 주입 방지를 위한 사전 체크 (PING)
            // 탭에 메시지를 보내서 "이미 실행 중이니?" 물어봅니다.
            chrome.tabs.sendMessage(tabId, { type: "PING" })
                .then(() => {
                    // 응답이 오면 이미 content_script가 돌고 있다는 뜻 -> 주입 안 함
                    // console.log("[NewsNode] Script already active on this tab.");
                })
                .catch(() => {
                    // 응답이 없으면(에러 나면) 스크립트가 없다는 뜻 -> 주입 실행!
                    console.log(`[NewsNode] Injecting script into: ${tab.url}`);
                    
                    chrome.scripting.executeScript({
                        target: { tabId: tabId },
                        // config.js를 먼저 넣어야 content_script에서 CONFIG 변수를 쓸 수 있음
                        files: ['config.js', 'content_script.js'] 
                    }).catch(err => console.log("[NewsNode] Script injection failed:", err));
                });
        }
    }
});

// 4. 로그 전송 요청 처리 (Content Script -> Background -> Server)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "SEND_LOG") {
        const { apiUrl, logData, token } = request.payload;

        // keepalive: true 옵션으로 탭이 닫혀도 전송을 시도함 (Navigator.sendBeacon 대용)
        fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Token ${token}`
            },
            body: JSON.stringify(logData),
            keepalive: true 
        })
        .then(response => {
            if (!response.ok) {
                console.error(`[NewsNode] Log upload failed: ${response.status}`);
            }
        })
        .catch(err => console.error("[NewsNode] Network error:", err));

        // 비동기 응답 처리를 위해 true 리턴
        return true; 
    }
});