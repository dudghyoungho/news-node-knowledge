// dashboard_ui.js - UI Interaction Logic
const DashboardUI = {
    // 초기화 함수
    init: function(loadLibrarianCallback) {
        this.initMobileMenu();
        this.initSidebarNavigation(loadLibrarianCallback);
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
    }
};