// dashboard_data.js - API Fetching & Rendering
window.DashboardData = {
    region: 'KR',
    textPack: {},

    // 설정 주입
    init: function(region, textPack) {
        this.region = region;
        this.textPack = textPack;
        
        // 초기 데이터 로드
        this.loadStatsData();
        this.loadRecentNews();
    },

    // 1. 통계 데이터 (차트 & 페르소나)
    loadStatsData: function() {
        if (!document.getElementById('weeklyChart')) return; 

        fetch(`/api/news/stats/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                if(document.getElementById('user-persona') && data.persona) {
                    document.getElementById('user-persona').innerText = data.persona;
                }
                this.renderWeeklyChart(data.daily_activity);
                this.renderCategoryChart(data.category_distribution);
            })
            .catch(err => console.error("Error loading stats:", err));
    },

    // 2. 최근 뉴스 (우측 패널)
    loadRecentNews: function() {
        const container = document.getElementById('recent-news-list');
        if (!container) return;

        fetch(`/api/news/stats/?region=${this.region}`) 
            .then(res => res.json())
            .then(data => {
                const articles = data.recent_articles || []; 
                if (articles.length === 0) {
                    container.innerHTML = `<div style="padding: 20px 0; text-align: center; color: #636e72; font-size: 12px;">No recent stars found.</div>`;
                    return;
                }
                let html = '';
                articles.slice(0, 5).forEach(art => {
                    let dateDisplay = art.date ? art.date.substring(5, 10) : 'Recent';
                    html += `
                        <div class="item" onclick="window.open('${art.url}', '_blank')">
                            <div class="title">${art.title}</div>
                            <div class="date">${dateDisplay}</div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            })
            .catch(err => console.warn("Recent News API not ready yet."));
    },

    // 3. Librarian 데이터 로드 (Time Capsule + Recommendations)
    loadLibrarianData: function() {
        // (1) Time Capsule (과거의 기억)
        fetch(`/api/news/rag/review/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                if(!container) return;
                
                if (data.message) {
                    container.innerHTML = `<p style="text-align:center; color:#636e72; padding: 20px;">${data.message}</p>`;
                    return;
                }
                // Time Capsule은 디자인 유지
                container.innerHTML = `
                    <div style="font-size:12px; color:#55efc4; margin-bottom:5px; font-weight:bold;">
                        ${this.textPack.reviewTitle} ${data.date || ""}
                    </div>
                    <div style="font-size:16px; font-weight:bold; color:#fff; margin-bottom:15px; line-height: 1.4;">
                        ${data.title}
                    </div>
                    <div class="ai-comment" style="background:rgba(255,255,255,0.05); padding:15px; border-radius:8px; color:#dfe6e9; font-style:italic; border-left: 3px solid #55efc4;">
                        "${data.comment.replace(/\n/g, '<br>')}"
                    </div>
                    <button class="btn-link" style="margin-top:15px; width:100%; text-align:center; background:none; border:none; color:#74b9ff; cursor:pointer; font-weight:bold;" onclick="window.open('${data.article ? data.article.url : data.url}', '_blank')">
                        ${this.textPack.readButton} →
                    </button>
                `;
            })
            .catch(err => console.log("Librarian sleeping..."));

        // (2) Recommendations (External + Vector) -> [수정] 통합 렌더링
        fetch(`/api/news/rag/external/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                this.renderVectorRecs(data.vector_recommendations || []);
                this.renderSearchRecs(data.search_recommendations || {});
            })
            .catch(err => {
                console.error(err);
                const container = document.getElementById('external-list');
                if (container) container.innerHTML = `<div style="color:#ff7675; text-align:center;">Failed to connect.</div>`;
            });
    },

// ============================================================
    // [NEW] ★ 핵심: 공통 카드 HTML 생성 함수 (Unified Design) ★
    // ============================================================
    createCardHTML: function(item, type) {
        // 1. 데이터 안전하게 추출 (백엔드 키 통일됨)
        const title = (item.title || "No Title").replace(/<[^>]*>?/gm, '');
        const summary = item.summary || "No description.";
        const link = item.url || "#";
        const thumbnail = item.thumbnail || ""; 
        const date = item.date || "";
        const source = item.source || "Web";

        // [수정] ★ 여기가 누락되어 있었습니다! 데이터를 변수로 꺼내야 합니다. ★
        const reasonTag = item.reason_tag || "";
        const reasonDesc = item.reason_desc || "";

        // 2. 타입별 배지 & 메타 정보 설정
        let badgeClass = "";
        let metaRight = ""; 

        if (type === 'vector') {
            badgeClass = "badge-vector";
            if (item.similarity) {
                metaRight = `<span class="lib-meta-text" style="color:#a29bfe;">${item.similarity}% Match</span>`;
            } else {
                 metaRight = `<span class="lib-meta-text">${date}</span>`;
            }
        } else {
            badgeClass = "badge-search";
            metaRight = `<span class="lib-meta-text">${date}</span>`;
        }

        // [수정] 이제 reasonTag 변수가 정의되었으므로 정상 작동합니다.
        let reasonHtml = "";
        if (type === 'vector' && reasonTag) {
            // 사유를 보여주는 작은 헤더
            reasonHtml = `
                <div style="font-size:11px; color:#a29bfe; margin-bottom:4px; font-weight:600; display:flex; align-items:center; gap:6px;">
                    <span style="background:rgba(162,155,254,0.1); padding:2px 6px; border-radius:4px; border:1px solid rgba(162,155,254,0.2);">${reasonTag}</span>
                    <span style="color:#b2bec3; font-weight:400; font-size:11px;">${reasonDesc}</span>
                </div>
            `;
        }

        // 3. 이미지 태그 생성
        const imgHtml = thumbnail 
            ? `<img src="${thumbnail}" class="lib-card-thumb" onerror="this.parentNode.innerHTML='<div class=\'lib-card-no-img\'>📰</div>'">`
            : `<div class="lib-card-no-img">📰</div>`;

        // 4. 최종 HTML 조립
        return `
            <div class="lib-card" onclick="window.open('${link}', '_blank')">
                <div class="lib-card-thumb-box">
                    ${imgHtml}
                </div>
                <div class="lib-card-body">
                    ${reasonHtml}
                    
                    <div>
                        <div class="lib-card-meta">
                            <span class="lib-badge ${badgeClass}">${source}</span>
                            ${metaRight}
                        </div>
                        <div class="lib-card-title">${title}</div>
                    </div>
                    <div class="lib-card-desc">${summary}</div>
                </div>
            </div>
        `;
    },
    
    // [수정] 벡터 추천 렌더링 (createCardHTML 사용)
    renderVectorRecs: function(items) {
        const container = document.getElementById('vector-list');
        if (!container) return;

        if (items.length === 0) {
            container.innerHTML = `<div style="padding:15px; color:#636e72; font-size:13px; text-align:center;">Read more articles to get personalized recommendations.</div>`;
            return;
        }
        
        container.innerHTML = items.map(item => this.createCardHTML(item, 'vector')).join('');
    },

    // [수정] 검색 추천 렌더링 (createCardHTML 사용)
    renderSearchRecs: function(data) {
        const container = document.getElementById('external-list');
        const keywordContainer = document.getElementById('discovery-keywords');
        if (!container) return;

        const items = data.articles || [];
        
        // 키워드 태그 렌더링
        if (keywordContainer) {
            const keywords = (data.keywords || data.keyword || "General").split(',');
            let kwHtml = '';
            keywords.forEach(k => { kwHtml += `<span class="keyword-tag">#${k.trim()}</span>`; });
            keywordContainer.innerHTML = kwHtml;
        }

        if (items.length === 0) {
            container.innerHTML = `<div style='padding:20px; color:#636e72; text-align:center;'>${this.textPack.noExternal}</div>`;
            return;
        }

        container.innerHTML = items.map(item => this.createCardHTML(item, 'search')).join('');
    },

    // --- 차트 렌더링 함수들 (기존 유지) ---
    renderWeeklyChart: function(data) {
        if (!data) return;
        const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
        new Chart(weeklyCtx, {
            type: 'bar', 
            data: {
                labels: data.map(d => d.date),
                datasets: [{
                    label: 'Articles',
                    data: data.map(d => d.count),
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
                scales: { y: { display: false }, x: { grid: { display: false }, ticks: { font: { size: 10 } } } }
            }
        });
    },

    renderCategoryChart: function(data) {
        if (!data) return;
        const categoryCtx = document.getElementById('categoryChart').getContext('2d');
        new Chart(categoryCtx, {
            type: 'doughnut',
            data: {
                labels: data.map(c => c.category || 'General'),
                datasets: [{
                    data: data.map(c => c.count),
                    backgroundColor: ['#ff7675', '#74b9ff', '#55efc4', '#a29bfe', '#fab1a0', '#ffeaa7', '#00cec9', '#fd79a8', '#6c5ce7', '#b2bec3'],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'right', labels: { boxWidth: 8, padding: 10, font: { size: 11 }, color: '#e0e6ed' } } },
                cutout: '75%'
            }
        });
    }
};