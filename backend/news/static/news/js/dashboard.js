// dashboard.js - Main Entry Point & Configuration
document.addEventListener("DOMContentLoaded", function() {
    
    // ============================================================
    // 1. [Settings] Region & Global Config
    // ============================================================
    const urlParams = new URLSearchParams(window.location.search);
    // URL에 파라미터가 없으면 기본값 KR
    const currentRegion = urlParams.get('region') || 'KR'; 
    
    console.log(`🚀 [NewsNode] Dashboard Initialized. Region: ${currentRegion}`);

    // [Chart.js Config] 
    // Knowledge 탭은 여전히 Dark Mode이므로, 차트 기본값은 밝은 색(Dark Theme용)으로 유지
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = '#e0e6ed'; 
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.08)'; 
        // 한글/영문 폰트 가독성 최적화
        Chart.defaults.font.family = "'Work Sans', 'Apple SD Gothic Neo', sans-serif";
    }

    // [UI Text Pack] 
    // 신문 디자인(Librarian)에 어울리는 문구로 업데이트
    const uiText = {
        'KR': {
            reviewTitle: "📜 지식 타임캡슐 -",  // Newspaper 스타일 아이콘 추가
            readButton: "기사 원문 정독하기",      // 조금 더 권유하는 어조
            noExternal: "현재 분석된 새로운 토픽이 없습니다.",
            hot: "인기", 
            source: "출처", 
            similarity: "관심도", 
            loading: "데이터 분석중..."
        },
        'AU': {
            reviewTitle: "📜 Time Capsule -",
            readButton: "Read Full Story",
            noExternal: "No new topics discovered yet.",
            hot: "HOT", 
            source: "Source", 
            similarity: "Relevance", 
            loading: "Analyzing..."
        }
    };
    
    const textPack = uiText[currentRegion] || uiText['KR'];

    // ============================================================
    // 2. [Init] Initialize Modules
    // ============================================================
    
    // 2-1. Data Module 초기화 (API 호출 시작)
    if (window.DashboardData) {
        // dashboard_data.js의 init 실행 -> 통계, 최근 뉴스, 사서 데이터 로드 시작
        DashboardData.init(currentRegion, textPack);
    } else {
        console.error("❌ DashboardData module is missing.");
    }

    // 2-2. UI Module 초기화 (이벤트 리스너 등록)
    if (window.DashboardUI) {
        /* DashboardUI.init()에 전달하는 콜백 함수는
           사용자가 'Librarian(AI 사서)' 탭을 처음 클릭했을 때 실행됩니다.
           
           이미 DashboardData.init()에서 데이터를 부르지만, 
           탭 전환 시 데이터를 '새로고침' 하거나 '확실하게 로드'하기 위해 연결해둡니다.
        */
        DashboardUI.init(() => {
            console.log("📂 Tab Switched: Loading Librarian Data...");
            if (window.DashboardData) {
                DashboardData.loadLibrarianData();
            }
        });
    } else {
        console.error("❌ DashboardUI module is missing.");
    }
});