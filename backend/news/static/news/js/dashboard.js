document.addEventListener("DOMContentLoaded", function() {
    
    // ============================================
    // 0. [Core] Region & URL Params Parsing
    // ============================================
    const urlParams = new URLSearchParams(window.location.search);
    const currentRegion = urlParams.get('region') || 'KR'; // 기본값 KR
    
    console.log(`🚀 Dashboard Initialized. Mode: ${currentRegion}`);

    // UI 텍스트 언어팩 (간단한 로컬라이징)
    const uiText = {
        'KR': {
            reviewTitle: "📅 과거의 기억",
            readButton: "🔗 원문 읽기",
            keywordLabel: "🛰️ AI 추천 키워드:",
            noExternal: "추천할 외부 기사가 없습니다.",
            hot: "인기",
            source: "뉴스 출처"
        },
        'AU': {
            reviewTitle: "📅 Memory from",
            readButton: "🔗 Read Article",
            keywordLabel: "🛰️ AI Keyword:",
            noExternal: "No recommendations found.",
            hot: "HOT",
            source: "Source"
        }
    };
    const textPack = uiText[currentRegion];

    // ============================================
    // 1. Sidebar Tab Logic
    // ============================================
    const menuItems = document.querySelectorAll('.menu-item');
    const sections = document.querySelectorAll('.view-section');
    
    let isLibrarianLoaded = false;

    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            menuItems.forEach(btn => btn.classList.remove('active'));
            item.classList.add('active');

            sections.forEach(sec => sec.style.display = 'none');
            
            const targetId = item.getAttribute('data-target');
            const targetSection = document.getElementById(targetId);
            if(targetSection) targetSection.style.display = 'flex'; 

            // 'My Librarian' 탭을 처음 누를 때만 데이터를 로드 (트래픽 절약)
            if (targetId === 'view-librarian' && !isLibrarianLoaded) {
                loadLibrarianData();
                isLibrarianLoaded = true;
            }
        });
    });

    // ============================================
    // 2. Load Knowledge Stats (Initial Load)
    // ============================================
    loadStatsData();

    // ============================================
    // 3. Load RAG Data (My Librarian)
    // ============================================
    function loadLibrarianData() {
        // (1) Knowledge Time Capsule (Review)
        // [수정] URL에 region 파라미터 추가
        fetch(`/api/news/rag/review/?region=${currentRegion}`)
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                
                if (data.message) {
                    container.innerHTML = `<p style="text-align:center; color:#636e72; padding: 20px;">${data.message}</p>`;
                    return;
                }

                container.innerHTML = `
                    <div style="font-size:12px; color:#00b894; margin-bottom:5px; font-weight:bold;">
                        ${textPack.reviewTitle} ${data.date}
                    </div>
                    <div style="font-size:16px; font-weight:bold; color:#2d3436; margin-bottom:10px; line-height: 1.4;">
                        ${data.title}
                    </div>
                    <div class="ai-comment" style="background:#f1f2f6; padding:15px; border-radius:8px; color:#2d3436; font-style:italic;">
                        "${data.comment.replace(/\n/g, '<br>')}"
                    </div>
                    <button class="btn-link" style="margin-top:15px; width:100%; text-align:center; background:none; border:none; color:#0984e3; cursor:pointer;" onclick="window.open('${data.url}', '_blank')">
                        ${textPack.readButton}
                    </button>
                `;
            })
            .catch(err => {
                console.error("Review Error:", err);
                const container = document.getElementById('review-card');
                if(container) container.innerHTML = `<p style="color:#b2bec3; text-align:center;">Failed to connect to AI Librarian.</p>`;
            });

        // (2) Knowledge Expansion (External)
        // [수정] URL에 region 파라미터 추가
        fetch(`/api/news/rag/external/?region=${currentRegion}`)
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('external-list');
            const items = data.articles || []; 
            const keyword = data.keyword || "General";

            if (items.length === 0) {
                container.innerHTML = `<div style='padding:10px; color:#b2bec3; text-align:center;'>${textPack.noExternal}</div>`;
                return;
            }

            let html = `<div style="margin-bottom:15px; font-weight:bold; color:#0984e3; font-size:15px;">
                            ${textPack.keywordLabel} <span style="color:#2d3436; background:#dfe6e9; padding:2px 6px; border-radius:4px;">#${keyword}</span>
                        </div>`;
            
            items.forEach(item => {
                const link = item.url || item.link || '#';
                // HTML 태그가 포함되어 있을 수 있으므로 제거하거나 텍스트만 추출
                const title = item.title.replace(/<[^>]*>?/gm, ''); 
                const summary = item.summary || item.snippet || item.description || "";
                const source = item.source || textPack.source;
                
                let dateStr = "";
                if (item.date || item.pubDate) {
                    try {
                        const rawDate = item.date || item.pubDate;
                        dateStr = rawDate.substring(0, 10); // YYYY-MM-DD만 자르기
                    } catch(e) {}
                }

                html += `
                    <div class="reco-item" onclick="window.open('${link}', '_blank')" 
                         style="cursor:pointer; margin-bottom:12px; padding:15px; background:#fff; border-radius:10px; border:1px solid #dfe6e9; box-shadow: 0 2px 5px rgba(0,0,0,0.03); transition: transform 0.2s;">
                        
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:10px; background:#ffeaa7; color:#d63031; padding:2px 8px; border-radius:4px; font-weight:bold;">${textPack.hot}</span>
                            <span style="font-size:11px; color:#b2bec3;">${source} ${dateStr ? '| ' + dateStr : ''}</span>
                        </div>
                        
                        <div style="font-weight:bold; margin-bottom: 6px; color:#2d3436; font-size:15px; line-height:1.4;">
                            ${title}
                        </div>
                        
                        ${summary ? `<div style="font-size:12px; color:#636e72; line-height:1.4; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;">
                            ${summary}
                        </div>` : ''}
                    </div>
                `;
            });
            
            container.innerHTML = html;
        })
        .catch(err => {
            console.error("Recommendation Error:", err);
            const container = document.getElementById('external-list');
            if (container) container.innerHTML = `<div style="color:#ff7675; text-align:center;">Failed to load data.</div>`;
        });
    }

    // ============================================
    // Load Stats Function (수정됨)
    // ============================================
    function loadStatsData() {
        if (!document.getElementById('weeklyChart')) return; 

        // 1. API 호출
        fetch(`/api/news/stats/?region=${currentRegion}`)
            .then(res => res.json())
            .then(data => {
                console.log("📊 API Data Received:", data); // [디버깅용] 콘솔에서 데이터 확인 가능

                // 2. [수정] 전체 기사 수 매핑 (total_count -> total_articles)
                if (document.getElementById('total-count')) {
                    document.getElementById('total-count').innerText = data.total_articles || 0;
                }
                
                // 3. 페르소나 매핑
                if(document.getElementById('user-persona') && data.persona) {
                    document.getElementById('user-persona').innerText = data.persona;
                }

                // 4. [수정] 차트 데이터 확인 (category_stats -> category_distribution)
                // 백엔드가 보낸 키값은 'category_distribution' 입니다.
                // 이 값이 없으면 여기서 함수가 멈춰서 차트가 안 그려졌던 것입니다.
                if (!data.category_distribution) {
                    console.log("❌ 카테고리 데이터가 없습니다.");
                    return;
                }

                // 5. Weekly Chart 그리기
                if (data.daily_activity) {
                    const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
                    
                    // 기존 차트가 있으면 삭제 (중복 렌더링 방지, 선택사항)
                    // if (window.weeklyChartInstance) window.weeklyChartInstance.destroy();

                    new Chart(weeklyCtx, {
                        type: 'bar', 
                        data: {
                            labels: data.daily_activity.map(d => d.date),
                            datasets: [{
                                label: 'Articles',
                                data: data.daily_activity.map(d => d.count),
                                backgroundColor: '#0984e3',
                                borderRadius: 4,
                                barThickness: 20
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: { legend: { display: false } },
                            scales: { 
                                y: { display: false, beginAtZero: true }, 
                                x: { grid: { display: false } } 
                            }
                        }
                    });
                }

                // 6. [수정] Category Chart 그리기 (category_stats -> category_distribution)
                const categoryCtx = document.getElementById('categoryChart').getContext('2d');
                const categories = data.category_distribution; // 여기가 핵심 수정 포인트입니다.
                
                new Chart(categoryCtx, {
                    type: 'doughnut',
                    data: {
                        labels: categories.map(c => c.category || 'General'),
                        datasets: [{
                            data: categories.map(c => c.count),
                            backgroundColor: [
                                '#fd79a8', '#ffeaa7', '#55efc4', '#74b9ff', '#a29bfe',
                                '#ff7675', '#00cec9', '#fab1a0', '#6c5ce7', '#dfe6e9'
                            ],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { 
                            legend: { 
                                position: 'right', 
                                labels: { boxWidth: 10, font: { size: 11 }, padding: 10, color: '#2d3436' } 
                            } 
                        },
                        cutout: '70%'
                    }
                });
            })
            .catch(err => console.error("Error loading stats:", err));
    }
});