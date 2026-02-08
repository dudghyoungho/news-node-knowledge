// dashboard.js - Main Entry Point
document.addEventListener("DOMContentLoaded", function() {
    
    // 1. [Settings] Region & Global Config
    const urlParams = new URLSearchParams(window.location.search);
    const currentRegion = urlParams.get('region') || 'KR'; 
    console.log(`🚀 Dashboard Initialized. Mode: ${currentRegion}`);

    // Chart.js Default Config
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = '#e0e6ed'; 
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.08)'; 
        Chart.defaults.font.family = "'Apple SD Gothic Neo', sans-serif";
    }

    // UI Text Pack
    const uiText = {
        'KR': {
            reviewTitle: "과거의 기억", readButton: "원문 읽기", noExternal: "추천할 외부 기사가 없습니다.",
            hot: "인기", source: "출처", similarity: "유사도", loading: "로딩중..."
        },
        'AU': {
            reviewTitle: "Memory from", readButton: "Read Article", noExternal: "No recommendations found.",
            hot: "HOT", source: "Source", similarity: "Match", loading: "Loading..."
        }
    };
    const textPack = uiText[currentRegion] || uiText['KR'];

    // 2. [Init] Initialize Modules
    // Data 모듈 초기화 (설정값 주입)
    DashboardData.init(currentRegion, textPack);

    // UI 모듈 초기화 (Librarian 탭 클릭 시 실행할 데이터 로딩 함수 전달)
    DashboardUI.init(() => {
        DashboardData.loadLibrarianData();
    });
});