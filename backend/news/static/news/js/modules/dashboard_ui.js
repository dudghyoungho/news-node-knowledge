// dashboard_ui.js - UI Interaction Logic
const DashboardUI = {
    // 초기화 함수
    init: function(loadLibrarianCallback) {
        this.initMobileMenu();
        this.initSidebarNavigation(loadLibrarianCallback);
        this.initModalEvents(); // [New] 모달 이벤트 초기화 필수
    },

    // 1. 모바일 메뉴 토글
    initMobileMenu: function() {
        const mobileBtn = document.getElementById('mobile-menu-btn');
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('mobile-overlay');
        
        if (mobileBtn) {
            mobileBtn.addEventListener('click', () => {
                sidebar.classList.toggle('open');
                overlay.classList.toggle('active');
            });
        }

        if (overlay) {
            overlay.addEventListener('click', () => {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
            });
        }
    },

    // 2. 사이드바 탭 전환
    initSidebarNavigation: function(loadLibrarianCallback) {
        const menuItems = document.querySelectorAll('.menu-item');
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('mobile-overlay');
        let isLibrarianLoaded = false;

        menuItems.forEach(item => {
            item.addEventListener('click', () => {
                // 활성화 스타일 처리
                menuItems.forEach(btn => btn.classList.remove('active'));
                item.classList.add('active');

                // 모바일 메뉴 닫기
                if (window.innerWidth <= 768 && sidebar.classList.contains('open')) {
                    sidebar.classList.remove('open');
                    overlay.classList.remove('active');
                }

                const targetId = item.getAttribute('data-target');
                this.switchTab(targetId, () => {
                    // Librarian 탭 최초 진입 시 데이터 로딩 콜백 실행
                    if (targetId === 'view-librarian' && !isLibrarianLoaded) {
                        if (loadLibrarianCallback) loadLibrarianCallback();
                        isLibrarianLoaded = true;
                    }
                });
            });
        });
    },

    // 3. 화면 전환 (Helper)
    switchTab: function(targetId, callback) {
        const viewOverlay = document.querySelector('.view-overlay');
        const graphBg = document.querySelector('.graph-background');
        const librarian = document.getElementById('view-librarian');

        if (targetId === 'view-knowledge') {
            if (viewOverlay) viewOverlay.style.display = 'flex';
            if (graphBg) graphBg.style.display = 'block';
            if (librarian) librarian.style.display = 'none';
        } else if (targetId === 'view-librarian') {
            if (viewOverlay) viewOverlay.style.display = 'none';
            if (librarian) librarian.style.display = 'block';
        }

        if (callback) callback();
    },

    // ============================================================
    // [NEW] 4. 기사 상세 모달 (Knowledge Bridge) 제어
    // ============================================================
    
    // 모달 열기 (articleId: DB ID, originalUrl: 원문 링크)
    openModal: function(articleId, originalUrl) {
        const modal = document.getElementById('article-modal');
        if (!modal) return;

        // (1) UI 표시 및 초기화
        modal.style.display = 'flex';
        
        // 로딩 텍스트 설정
        document.getElementById('modal-title').innerText = "Loading Context...";
        document.getElementById('modal-date').innerText = "";
        const badge = document.getElementById('modal-category');
        if(badge) badge.style.display = 'none';
        document.getElementById('modal-summary').innerText = "Analyzing content structure...";
        
        // 브릿지 섹션 숨김 (데이터 로드 후 표시됨)
        const bridgeSection = document.getElementById('bridge-section');
        if(bridgeSection) bridgeSection.style.display = 'none';

        // (2) '원문 보기' 버튼 동작 설정
        const btnOriginal = document.getElementById('btn-open-original');
        if (btnOriginal) {
            btnOriginal.onclick = () => window.open(originalUrl, '_blank');
        }

        // (3) 데이터 로딩 트리거 (DashboardData 모듈 호출)
        if (window.DashboardData && typeof window.DashboardData.loadBridgeData === 'function') {
            window.DashboardData.loadBridgeData(articleId);
        } else {
            console.error("DashboardData module not loaded.");
            document.getElementById('modal-title').innerText = "Error: Data Module Missing";
        }
    },

    // 모달 닫기
    closeModal: function() {
        const modal = document.getElementById('article-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    },

    // 모달 이벤트 리스너 (ESC 키, 배경 클릭)
    initModalEvents: function() {
        document.addEventListener('keydown', (event) => {
            if (event.key === "Escape") {
                this.closeModal();
            }
        });

        const modal = document.getElementById('article-modal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal();
                }
            });
        }
    }
};