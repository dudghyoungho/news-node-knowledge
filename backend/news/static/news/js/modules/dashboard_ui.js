// dashboard_ui.js - UI Interaction Logic
window.DashboardUI = {
    // 1. 초기화 (Main Entry Point)
    init: function(loadLibrarianCallback) {
        console.log("3. [DashboardUI] init() 실행됨");
        this.initMobileMenu();
        this.initSidebarNavigation(loadLibrarianCallback);
        this.initModalEvents();
    },

    // 2. 모바일 메뉴 토글 (반응형)
    initMobileMenu: function() {
        const mobileBtn = document.getElementById('mobile-menu-btn');
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('mobile-overlay');
        
        if (mobileBtn) {
            mobileBtn.addEventListener('click', () => {
                sidebar.classList.toggle('open');
                if(overlay) overlay.classList.toggle('active');
            });
        }

        if (overlay) {
            overlay.addEventListener('click', () => {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
            });
        }
    },

    // 3. 사이드바 탭 전환 (핵심 로직)
    initSidebarNavigation: function(loadLibrarianCallback) {
        const menuItems = document.querySelectorAll('.menu-item');
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('mobile-overlay');
        
        // 중복 로딩 방지 플래그
        let isLibrarianLoaded = false;

        menuItems.forEach(item => {
            item.addEventListener('click', (e) => {
                // (1) 메뉴 활성화 스타일 처리
                menuItems.forEach(btn => btn.classList.remove('active'));
                item.classList.add('active');

                // (2) 모바일에서 메뉴 클릭 시 사이드바 닫기
                if (window.innerWidth <= 768 && sidebar.classList.contains('open')) {
                    sidebar.classList.remove('open');
                    if(overlay) overlay.classList.remove('active');
                }

                // (3) 탭 전환 실행
                const targetId = item.getAttribute('data-target'); // 예: view-knowledge, view-librarian
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

    // [Helper] 화면 전환 로직 (HTML/CSS 호환성 유지)
    switchTab: function(targetId, callback) {
        // 모든 뷰 섹션 숨김
        const sections = document.querySelectorAll('.view-section');
        sections.forEach(el => {
            el.style.display = 'none';
            el.classList.remove('active');
        });

        // 타겟 뷰만 표시
        const targetView = document.getElementById(targetId);
        if (targetView) {
            // Tailwind/CSS 호환성을 위해 display: block 강제 적용
            targetView.style.display = 'block';
            targetView.classList.add('active');
            
            // Knowledge 탭일 때만 그래프 배경 보이기
            const graphBg = document.querySelector('.graph-background');
            if (graphBg) {
                graphBg.style.display = (targetId === 'view-knowledge') ? 'block' : 'none';
            }
        }

        if (callback) callback();
    },

    // ============================================================
    // 4. 기사 상세 모달 (Knowledge Bridge) 제어
    // ============================================================
    
    // 모달 열기 (articleId: DB ID, originalUrl: 원문 링크)
    openModal: function(articleId, originalUrl) {
        const modal = document.getElementById('article-modal');
        if (!modal) return;

        // (1) UI 표시 및 초기화
        modal.style.display = 'flex'; // Flex로 열어야 중앙 정렬됨
        
        // 로딩 텍스트 설정
        const titleEl = document.getElementById('modal-title');
        const summaryEl = document.getElementById('modal-summary');
        if(titleEl) titleEl.innerText = "Loading Context...";
        if(summaryEl) summaryEl.innerText = "Analyzing content structure...";

        document.getElementById('modal-date').innerText = "";
        const badge = document.getElementById('modal-category');
        if(badge) badge.style.display = 'none';
        
        // 썸네일 숨기기 (로딩 중)
        const thumb = document.getElementById('modal-thumb');
        if(thumb) thumb.style.display = 'none';
        
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
            if(titleEl) titleEl.innerText = "Error: Data Module Missing";
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
        // ESC 키 닫기
        document.addEventListener('keydown', (event) => {
            if (event.key === "Escape") {
                this.closeModal();
            }
        });

        // 배경 클릭 닫기
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