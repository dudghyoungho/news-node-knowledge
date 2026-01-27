document.addEventListener("DOMContentLoaded", function() {
    
    // ============================================
    // 0. [Core] Region & Global Settings
    // ============================================
    const urlParams = new URLSearchParams(window.location.search);
    const currentRegion = urlParams.get('region') || 'KR'; 
    
    console.log(`🚀 Dashboard Initialized. Mode: ${currentRegion}`);

    // [중요] Chart.js 전역 설정 (다크 테마용)
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = '#e0e6ed'; 
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.08)'; 
        Chart.defaults.font.family = "'Apple SD Gothic Neo', sans-serif";
    }

    // UI 텍스트 언어팩
    const uiText = {
        'KR': {
            reviewTitle: "과거의 기억",
            readButton: "원문 읽기",
            keywordLabel: "AI 추천 키워드:",
            noExternal: "추천할 외부 기사가 없습니다.",
            hot: "인기",
            source: "뉴스 출처"
        },
        'AU': {
            reviewTitle: "Memory from",
            readButton: "Read Article",
            keywordLabel: "AI Keyword:",
            noExternal: "No recommendations found.",
            hot: "HOT",
            source: "Source"
        }
    };
    const textPack = uiText[currentRegion] || uiText['KR'];

    // ============================================
    // 1. [NEW] Mobile Sidebar Toggle Logic
    // ============================================
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('mobile-overlay');
    
    // 1-1. 햄버거 버튼 클릭 -> 사이드바 열기/닫기
    if (mobileBtn) {
        mobileBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        });
    }

    // 1-2. 오버레이(바깥) 클릭 -> 사이드바 닫기
    if (overlay) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
    }

    // ============================================
    // 2. Sidebar Navigation Logic
    // ============================================
    const menuItems = document.querySelectorAll('.menu-item');
    let isLibrarianLoaded = false;

    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            // 2-1. 메뉴 활성화 스타일 처리
            menuItems.forEach(btn => btn.classList.remove('active'));
            item.classList.add('active');

            // 2-2. 모바일일 경우 메뉴 클릭 시 사이드바 닫기
            if (window.innerWidth <= 768 && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
            }

            const targetId = item.getAttribute('data-target');

            // 2-3. 화면 전환 로직
            if (targetId === 'view-knowledge') {
                // Knowledge 탭: 오버레이 UI와 배경 그래프 표시, Librarian 숨김
                const viewOverlay = document.querySelector('.view-overlay');
                const graphBg = document.querySelector('.graph-background');
                const librarian = document.getElementById('view-librarian');

                if (viewOverlay) viewOverlay.style.display = 'flex';
                if (graphBg) graphBg.style.display = 'block';
                if (librarian) librarian.style.display = 'none';

            } else if (targetId === 'view-librarian') {
                // Librarian 탭: 오버레이 UI와 배경 그래프 숨김, Librarian 표시
                const viewOverlay = document.querySelector('.view-overlay');
                const graphBg = document.querySelector('.graph-background'); // 그래프도 가리거나 숨김
                const librarian = document.getElementById('view-librarian');

                if (viewOverlay) viewOverlay.style.display = 'none';
                // 그래프를 아예 숨기지 않으면 겹쳐 보일 수 있으므로 숨김 처리 추천
                // (투명도 조절보다는 display:none이 성능상 유리)
                // if (graphBg) graphBg.style.display = 'none'; 
                
                if (librarian) librarian.style.display = 'block';

                // 데이터 지연 로딩
                if (!isLibrarianLoaded) {
                    loadLibrarianData();
                    isLibrarianLoaded = true;
                }
            }
        });
    });

    // ============================================
    // 3. Initial Data Loading
    // ============================================
    loadStatsData();   // 차트 및 페르소나
    loadRecentNews();  // 최근 뉴스 리스트 (플로팅 패널용)

    // ============================================
    // 4. Load Stats Data (Charts & Persona)
    // ============================================
    function loadStatsData() {
        if (!document.getElementById('weeklyChart')) return; 

        fetch(`/api/news/stats/?region=${currentRegion}`)
            .then(res => res.json())
            .then(data => {
                // 1. 페르소나 업데이트
                if(document.getElementById('user-persona') && data.persona) {
                    document.getElementById('user-persona').innerText = data.persona;
                }

                // 2. Weekly Chart (Bar Chart)
                if (data.daily_activity) {
                    const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
                    
                    new Chart(weeklyCtx, {
                        type: 'bar', 
                        data: {
                            labels: data.daily_activity.map(d => d.date),
                            datasets: [{
                                label: 'Articles',
                                data: data.daily_activity.map(d => d.count),
                                backgroundColor: '#74b9ff',
                                hoverBackgroundColor: '#a29bfe',
                                borderRadius: 4,
                                barThickness: 15
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: { legend: { display: false } },
                            scales: { 
                                y: { display: false, beginAtZero: true }, 
                                x: { grid: { display: false }, ticks: { font: { size: 10 } } } 
                            }
                        }
                    });
                }

                // 3. Category Chart (Doughnut)
                if (data.category_distribution) {
                    const categoryCtx = document.getElementById('categoryChart').getContext('2d');
                    const categories = data.category_distribution;
                    
                    new Chart(categoryCtx, {
                        type: 'doughnut',
                        data: {
                            labels: categories.map(c => c.category || 'General'),
                            datasets: [{
                                data: categories.map(c => c.count),
                                backgroundColor: [
                                    '#ff7675', '#74b9ff', '#55efc4', '#a29bfe', '#fab1a0',
                                    '#ffeaa7', '#00cec9', '#fd79a8', '#6c5ce7', '#b2bec3'
                                ],
                                borderWidth: 0,
                                hoverOffset: 10
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: { 
                                legend: { 
                                    position: 'right', 
                                    labels: { boxWidth: 8, padding: 10, font: { size: 11 }, color: '#e0e6ed' } 
                                } 
                            },
                            cutout: '75%'
                        }
                    });
                }
            })
            .catch(err => console.error("Error loading stats:", err));
    }

    // ============================================
    // 5. Load Recent News (Floating Panel)
    // ============================================
    function loadRecentNews() {
        const container = document.getElementById('recent-news-list');
        if (!container) return;

        fetch(`/api/news/stats/?region=${currentRegion}`) 
            .then(res => res.json())
            .then(data => {
                const articles = data.recent_articles || []; 

                if (articles.length === 0) {
                    // 데이터 없음 안내
                    container.innerHTML = `
                        <div style="padding: 20px 0; text-align: center;">
                            <div style="font-size: 24px; margin-bottom: 5px;">🪐</div>
                            <div style="color: #636e72; font-size: 12px;">
                                No recent stars found.<br>
                                Reading history will appear here.
                            </div>
                        </div>`;
                    return;
                }

                let html = '';
                articles.slice(0, 5).forEach(art => {
                    let dateDisplay = 'Recent';
                    if (art.date) dateDisplay = art.date.substring(5, 10);

                    html += `
                        <div class="item" onclick="window.open('${art.url}', '_blank')">
                            <div class="title">${art.title}</div>
                            <div class="date">${dateDisplay}</div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            })
            .catch(err => {
                console.warn("Recent News API not ready yet (Ignored).");
                container.innerHTML = `
                    <div style="padding: 20px 0; text-align: center;">
                        <div style="font-size: 20px; margin-bottom: 5px;">🔭</div>
                        <div style="color: #636e72; font-size: 12px;">
                            Waiting for signals...<br>
                            (Feature coming soon)
                        </div>
                    </div>`;
            });
    }

    // ============================================
    // 6. Load RAG Data (My Librarian Tab)
    // ============================================
    function loadLibrarianData() {
        // (1) Knowledge Time Capsule (Review)
        fetch(`/api/news/rag/review/?region=${currentRegion}`)
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                
                if (data.message) {
                    container.innerHTML = `<p style="text-align:center; color:#636e72; padding: 20px;">${data.message}</p>`;
                    return;
                }

                container.innerHTML = `
                    <div style="font-size:12px; color:#55efc4; margin-bottom:5px; font-weight:bold;">
                        ${textPack.reviewTitle} ${data.date}
                    </div>
                    <div style="font-size:16px; font-weight:bold; color:#fff; margin-bottom:15px; line-height: 1.4;">
                        ${data.title}
                    </div>
                    <div class="ai-comment" style="background:rgba(255,255,255,0.05); padding:15px; border-radius:8px; color:#dfe6e9; font-style:italic; border-left: 3px solid #55efc4;">
                        "${data.comment.replace(/\n/g, '<br>')}"
                    </div>
                    <button class="btn-link" style="margin-top:15px; width:100%; text-align:center; background:none; border:none; color:#74b9ff; cursor:pointer; font-weight:bold;" onclick="window.open('${data.url}', '_blank')">
                        ${textPack.readButton} →
                    </button>
                `;
            })
            .catch(err => {
                const container = document.getElementById('review-card');
                if(container) container.innerHTML = `<p style="color:#636e72; text-align:center;">AI Librarian is sleeping...</p>`;
            });

        // (2) Knowledge Expansion (External)
        fetch(`/api/news/rag/external/?region=${currentRegion}`)
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('external-list');
            const items = data.articles || []; 
            const keyword = data.keyword || "General";

            if (items.length === 0) {
                container.innerHTML = `<div style='padding:20px; color:#636e72; text-align:center;'>${textPack.noExternal}</div>`;
                return;
            }

            let html = `<div style="margin-bottom:15px; font-weight:bold; color:#74b9ff; font-size:14px;">
                            ${textPack.keywordLabel} <span style="color:#fff; background:rgba(116, 185, 255, 0.2); padding:3px 8px; border-radius:4px; font-size:12px;">#${keyword}</span>
                        </div>`;
            
            items.forEach(item => {
                const link = item.url || item.link || '#';
                const title = item.title.replace(/<[^>]*>?/gm, ''); 
                const summary = item.summary || item.snippet || item.description || "";
                const source = item.source || textPack.source;
                let dateStr = "";
                try { dateStr = (item.date || item.pubDate).substring(0, 10); } catch(e) {}

                html += `
                    <div class="reco-item" onclick="window.open('${link}', '_blank')" 
                         style="cursor:pointer; margin-bottom:15px; padding:15px; background:rgba(255,255,255,0.05); border-radius:12px; border:1px solid rgba(255,255,255,0.05); transition: background 0.2s;">
                        
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:10px; background:rgba(255, 118, 117, 0.2); color:#ff7675; padding:2px 8px; border-radius:4px; font-weight:bold;">${textPack.hot}</span>
                            <span style="font-size:11px; color:#636e72;">${source} ${dateStr ? '| ' + dateStr : ''}</span>
                        </div>
                        <div style="font-weight:bold; margin-bottom: 8px; color:#fff; font-size:15px; line-height:1.4;">${title}</div>
                        ${summary ? `<div style="font-size:13px; color:#b2bec3; line-height:1.5; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;">${summary}</div>` : ''}
                    </div>
                `;
            });
            container.innerHTML = html;
        })
        .catch(err => {
            const container = document.getElementById('external-list');
            if (container) container.innerHTML = `<div style="color:#ff7675; text-align:center;">Failed to connect.</div>`;
        });
    }
});