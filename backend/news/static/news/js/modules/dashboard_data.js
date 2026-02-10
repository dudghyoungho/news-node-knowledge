// dashboard_data.js - API Fetching & Rendering
window.DashboardData = {
    region: 'KR',
    textPack: {},

    // 1. 초기화
    init: function(region, textPack) {
        console.log("1. [DashboardData] init() 실행됨");
        this.region = region;
        this.textPack = textPack;
        
        this.loadStatsData();      // 통계 차트
        this.loadRecentNews();     // 최근 기사 (사이드바 + Bridge)
        this.loadLibrarianData();  // [중요] 이 함수가 없어서 에러가 났던 것임 (Time Capsule 등)
    },

    // 2. 통계 데이터 로드
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
            .catch(err => console.error(err));
    },

    // 3. 최근 뉴스 로드 (사이드바 + Knowledge Map 트리거)
    loadRecentNews: function() {
        console.log("2. [DashboardData] loadRecentNews() 시작");
        const container = document.getElementById('recent-news-list');
        
        // Bridge 관련 요소 미리 가져오기
        const bridgeLoading = document.getElementById('bridge-loading-state');
        const bridgeContent = document.getElementById('bridge-content-box');

        if (!container) return;

        fetch(`/api/news/stats/?region=${this.region}`) 
            .then(res => res.json())
            .then(data => {
                const articles = data.recent_articles || []; 
                
                // [CASE A] 최근 기사가 없는 경우 (0개)
                if (articles.length === 0) {
                    container.innerHTML = `<div style="padding: 20px 0; text-align: center; color: #636e72; font-size: 12px;">No recent reading history.</div>`;
                    
                    // Bridge 섹션도 "데이터 없음" 처리
                    if (bridgeLoading) {
                        bridgeLoading.style.display = 'block';
                        bridgeLoading.innerHTML = `
                            <div style="padding: 10px 0;">
                                <div style="font-size: 20px; margin-bottom: 8px;">📭</div>
                                <div style="color: #b2bec3; font-weight: bold; font-size: 13px; margin-bottom: 4px;">
                                    No Context Found
                                </div>
                                <div style="color: #636e72; font-size: 11px;">
                                    Read news to generate your knowledge map.
                                </div>
                            </div>
                        `;
                    }
                    if (bridgeContent) bridgeContent.style.display = 'none';
                    return; 
                }
                
                // [CASE B] 기사가 있는 경우 -> 사이드바 리스트 렌더링
                let html = '';
                articles.slice(0, 5).forEach(art => {
                    let dateDisplay = art.date ? art.date.substring(5, 10) : 'Recent';
                    
                    // [수정 완료] 클릭 시 모달이 아니라 '새 창'으로 이동
                    html += `
                        <div class="item" onclick="window.open('${art.url}', '_blank')" style="cursor: pointer;">
                            <div class="title">${art.title}</div>
                            <div class="date">${dateDisplay}</div>
                        </div>
                    `;
                });
                container.innerHTML = html;

                // [핵심] 가장 최신 기사 ID로 Bridge(Context Map) 로딩 시작
                if (articles.length > 0) {
                    this.loadEmbeddedBridge(articles[0].id);
                }
            })
            .catch(err => {
                console.warn("Recent News Error:", err);
                if (bridgeLoading) bridgeLoading.innerHTML = "Failed to load data.";
            });
    },

    // 4. Librarian 데이터 로드 (Time Capsule + Recommendations)
    loadLibrarianData: function() {
        // (1) Time Capsule
        fetch(`/api/news/rag/review/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                if(!container) return;
                
                if (data.message) {
                    container.innerHTML = `<p style="text-align:center; color:#636e72; padding: 20px;">${data.message}</p>`;
                    return;
                }
                
                const targetId = data.article ? data.article.id : null;
                const targetUrl = data.article ? data.article.url : data.url;
                // Time Capsule은 클릭 시 모달 띄우기 (리뷰니까 상세히 보기 위함)
                const clickAction = targetId ? `DashboardUI.openModal(${targetId}, '${targetUrl}')` : `window.open('${targetUrl}', '_blank')`;

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
                    <button class="btn-link" style="margin-top:15px; width:100%; text-align:center; background:none; border:none; color:#74b9ff; cursor:pointer; font-weight:bold;" onclick="${clickAction}">
                        ${this.textPack.readButton} →
                    </button>
                `;
            })
            .catch(err => console.log("Librarian sleeping..."));

        // (2) Recommendations (External / Vector)
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

    // 5. [Embedded] 대시보드 삽입용 Bridge 로더
    loadEmbeddedBridge: function(articleId) {
        // [안전장치] ID가 없으면 중단 (404 방지)
        if (!articleId) {
            console.error("❌ [Bridge] Article ID is missing/undefined.");
            return;
        }

        const section = document.getElementById('section-bridge-dashboard');
        const loadingState = document.getElementById('bridge-loading-state');
        const contentBox = document.getElementById('bridge-content-box');
        
        const slotA = document.getElementById('dash-slot-a');
        const slotB = document.getElementById('dash-slot-b');
        const anchorLabel = document.getElementById('dash-anchor-title');
        
        if (!section) return;

        // 로딩 상태 표시
        if (loadingState) {
            loadingState.style.display = 'block';
            loadingState.innerHTML = '<div class="loading-text" style="font-size: 13px;">Analyzing context connections...</div>';
        }
        if (contentBox) contentBox.style.display = 'none';

        // API 호출
        fetch(`/api/news/articles/${articleId}/bridge/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                // 데이터 없음
                if (!data.slot_a && !data.slot_b) {
                    if (loadingState) {
                        loadingState.style.display = 'block'; 
                        loadingState.innerHTML = `
                            <div style="padding: 10px 0;">
                                <div style="font-size: 20px; margin-bottom: 8px;">📭</div>
                                <div style="color: #b2bec3; font-weight: bold; font-size: 13px; margin-bottom: 4px;">
                                    No Context Found
                                </div>
                                <div style="color: #636e72; font-size: 11px;">
                                    Try reading more articles to build a knowledge graph.
                                </div>
                            </div>
                        `;
                    }
                    return;
                }

                // 데이터 있음 -> 렌더링
                if (loadingState) loadingState.style.display = 'none';
                if (contentBox) contentBox.style.display = 'block';

                if (data.anchor && anchorLabel) {
                    anchorLabel.innerText = `Connected to: "${data.anchor.title}"`;
                }

                if (data.slot_a) {
                    this.fillBridgeCard(slotA, data.slot_a);
                } else {
                    if(slotA) slotA.style.display = 'none';
                }

                if (data.slot_b) {
                    this.fillBridgeCard(slotB, data.slot_b);
                } else {
                    if(slotB) slotB.style.display = 'none';
                }
            })
            .catch(err => {
                console.error("[Bridge] Error:", err);
                if (loadingState) {
                    loadingState.style.display = 'block';
                    loadingState.innerHTML = `
                        <div style="color: #ff7675; font-size: 12px; padding: 10px;">
                            ⚠️ Failed to load context.<br>
                            <span style="font-size:10px; opacity:0.8;">Server connection error.</span>
                        </div>
                    `;
                }
            });
    },

    // [Helper] 대시보드 카드 채우기 -> 클릭 시 모달 Open
    fillBridgeCard: function(element, data) {
        if (!element || !data) return;
        const article = data.article;
        const matches = data.matches || [];
        const keywordsHtml = matches.map(k => `<span>#${k}</span>`).join('');
        
        element.querySelector('.bridge-keywords').innerHTML = keywordsHtml;
        element.querySelector('.bridge-title').innerText = article.title;
        element.querySelector('.bridge-comment').innerText = `"${data.comment}"`;
        
        element.onclick = () => DashboardUI.openModal(article.id, article.url);
        element.style.display = 'block';
    },

    // 6. [Modal] 모달 내부용 Bridge 로더
    loadBridgeData: function(articleId) {
        const slotA = document.getElementById('bridge-slot-a');
        const slotB = document.getElementById('bridge-slot-b');
        const container = document.getElementById('bridge-section');

        if(container) container.style.display = 'block';
        if(slotA) slotA.style.display = 'none';
        if(slotB) slotB.style.display = 'none';

        fetch(`/api/news/articles/${articleId}/bridge/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                if (data.anchor) {
                    const anchor = data.anchor;
                    document.getElementById('modal-title').innerText = anchor.title;
                    document.getElementById('modal-date').innerText = anchor.date;
                    
                    // 썸네일 처리
                    const thumbImg = document.getElementById('modal-thumb');
                    if(thumbImg) {
                         if(anchor.thumbnail) {
                             thumbImg.src = anchor.thumbnail;
                             thumbImg.style.display = 'block';
                         } else {
                             thumbImg.style.display = 'none';
                         }
                    }

                    const badge = document.getElementById('modal-category');
                    if (badge) {
                        badge.innerText = anchor.category;
                        badge.style.display = 'inline-block';
                    }
                    document.getElementById('modal-summary').innerText = anchor.summary;
                } else {
                    document.getElementById('modal-title').innerText = "Article Not Found";
                }

                if (!data.slot_a && !data.slot_b) {
                    if(container) container.style.display = 'none';
                    return;
                }

                if (data.slot_a) this.renderBridgeCard(slotA, data.slot_a);
                if (data.slot_b) this.renderBridgeCard(slotB, data.slot_b);
            })
            .catch(err => {
                if(container) container.style.display = 'none';
            });
    },

    // [Helper] 모달 내부 카드 채우기 -> 클릭 시 원문 이동
    renderBridgeCard: function(element, data) {
        if (!element || !data) return;
        const article = data.article;
        const matches = data.matches || [];
        const keywordsHtml = matches.map(k => `<span>#${k}</span>`).join('');
        
        element.querySelector('.bridge-keywords').innerHTML = keywordsHtml;
        element.querySelector('.bridge-title').innerText = article.title;
        element.querySelector('.bridge-comment').innerText = `"${data.comment}"`;
        
        element.onclick = () => window.open(article.url, '_blank');
        element.style.display = 'block';
    },

    // 7. [Common] 일반 카드 HTML 생성 (My Taste / Discovery)
    createCardHTML: function(item, type) {
        const title = (item.title || "No Title").replace(/<[^>]*>?/gm, '');
        const summary = item.summary || "No description.";
        const link = item.url || "#";
        const thumbnail = item.thumbnail || ""; 
        const date = item.date || "";
        const source = item.source || "Web";
        const reasonTag = item.reason_tag || "";
        const reasonDesc = item.reason_desc || "";

        let badgeClass = (type === 'vector') ? "badge-vector" : "badge-search";
        let metaRight = (type === 'vector' && item.similarity) 
            ? `<span class="lib-meta-text" style="color:#a29bfe;">${item.similarity}% Match</span>`
            : `<span class="lib-meta-text">${date}</span>`;

        let reasonHtml = "";
        if (type === 'vector' && reasonTag) {
            reasonHtml = `
                <div style="font-size:11px; color:#a29bfe; margin-bottom:4px; font-weight:600; display:flex; align-items:center; gap:6px;">
                    <span style="background:rgba(162,155,254,0.1); padding:2px 6px; border-radius:4px; border:1px solid rgba(162,155,254,0.2);">${reasonTag}</span>
                    <span style="color:#b2bec3; font-weight:400; font-size:11px;">${reasonDesc}</span>
                </div>
            `;
        }

        const imgHtml = thumbnail 
            ? `<img src="${thumbnail}" class="lib-card-thumb" onerror="this.parentNode.innerHTML='<div class=\'lib-card-no-img\'>📰</div>'">`
            : `<div class="lib-card-no-img">📰</div>`;

        const clickAction = `window.open('${link}', '_blank')`;

        return `
            <div class="lib-card" onclick="${clickAction}">
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
        
    renderVectorRecs: function(items) {
        const container = document.getElementById('vector-list');
        if (!container) return;
        if (items.length === 0) {
            container.innerHTML = `<div style="padding:15px; color:#636e72; font-size:13px; text-align:center;">Read more articles to get personalized recommendations.</div>`;
            return;
        }
        container.innerHTML = items.map(item => this.createCardHTML(item, 'vector')).join('');
    },

    renderSearchRecs: function(data) {
        const container = document.getElementById('external-list');
        const keywordContainer = document.getElementById('discovery-keywords');
        if (!container) return;
        const items = data.articles || [];
        
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

    // 8. 차트 렌더링
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