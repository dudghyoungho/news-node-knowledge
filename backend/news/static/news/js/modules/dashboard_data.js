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
        // console.log("2. [DashboardData] loadRecentNews() 시작");
        const container = document.getElementById('recent-news-list');
        const bridgeLoading = document.getElementById('bridge-loading-state');
        const bridgeContent = document.getElementById('bridge-content-box');

        if (!container) return;

        fetch(`/api/news/stats/?region=${this.region}`) 
            .then(res => res.json())
            .then(data => {
                const articles = data.recent_articles || []; 
                
                // [CASE A] 최근 기사가 없는 경우
                if (articles.length === 0) {
                    container.innerHTML = `<div style="padding: 20px 0; text-align: center; color: #636e72; font-size: 12px;">No recent reading history.</div>`;
                    
                    // Bridge 섹션 (신문 디자인 내부)
                    if (bridgeLoading) {
                        bridgeLoading.style.display = 'block';
                        // [수정] 텍스트 색상을 Tailwind 클래스로 변경 (text-gray-500)
                        bridgeLoading.innerHTML = `
                            <div style="padding: 10px 0;">
                                <div style="font-size: 20px; margin-bottom: 8px;">📭</div>
                                <div class="text-gray-600" style="font-weight: bold; font-size: 13px; margin-bottom: 4px;">
                                    No Context Found
                                </div>
                                <div class="text-gray-500" style="font-size: 11px;">
                                    Read news to generate your knowledge map.
                                </div>
                            </div>
                        `;
                    }
                    if (bridgeContent) bridgeContent.style.display = 'none';
                    return; 
                }
                
                // [CASE B] 사이드바 리스트 (다크 테마 유지)
                let html = '';
                articles.slice(0, 5).forEach(art => {
                    let dateDisplay = art.date ? art.date.substring(5, 10) : 'Recent';
                    html += `
                        <div class="item" onclick="window.open('${art.url}', '_blank')" style="cursor: pointer;">
                            <div class="title">${art.title}</div>
                            <div class="date">${dateDisplay}</div>
                        </div>
                    `;
                });
                container.innerHTML = html;

                // [핵심] 가장 최신 기사 ID로 Bridge 로딩 시작
                if (articles.length > 0) {
                    this.loadEmbeddedBridge(articles[0].id);
                }
            })
            .catch(err => {
                // console.warn("Recent News Error:", err);
                if (bridgeLoading) bridgeLoading.innerHTML = "Failed to load data.";
            });
    },

    // 4. Librarian 데이터 로드 (Time Capsule + Recommendations)
    // 4. Librarian 데이터 로드 (Time Capsule) - [제목 undefined 수정 & 디자인 개선]
    loadLibrarianData: function() {
        // (1) Time Capsule
        fetch(`/api/news/rag/review/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                if(!container) return;
                
                if (data.message) {
                    container.innerHTML = `<p style="text-align:center; padding: 20px;" class="text-gray-500 italic">${data.message}</p>`;
                    return;
                }
                
                // [Undefined 해결] 데이터 구조가 { article: {...} } 인지 { title: ... } 인지 모두 대응
                const article = data.article || data; 
                const title = article.title || "Untitled Article"; 
                const targetId = article.id || null;
                const targetUrl = article.url || "#";
                
                const clickAction = targetId ? `DashboardUI.openModal(${targetId}, '${targetUrl}')` : `window.open('${targetUrl}', '_blank')`;

                container.innerHTML = `
                    <div class="flex justify-between items-end mb-3 border-b border-gray-200 pb-2">
                        <span class="text-xs font-bold text-red-800 tracking-widest uppercase flex items-center gap-1">
                            <span>📜</span> ${this.textPack.reviewTitle}
                        </span>
                        <span class="text-[10px] text-gray-400 font-serif-title italic">
                            ${data.date || "Memory"}
                        </span>
                    </div>
                    
                    <div class="mb-4">
                        <h3 class="text-lg md:text-xl font-black text-gray-900 leading-snug font-serif-title mb-2 hover:text-red-800 cursor-pointer transition" onclick="${clickAction}">
                            "${title}"
                        </h3>
                    </div>

                    <div class="bg-gray-50 p-3 border-l-4 border-red-800 rounded-r-md mb-3">
                        <p class="text-xs md:text-sm text-gray-700 italic font-medium leading-relaxed">
                            "${data.comment ? data.comment.replace(/\n/g, '<br>') : 'No comment'}"
                        </p>
                    </div>

                    <button class="w-full text-center py-2 text-xs font-bold uppercase tracking-widest text-blue-800 hover:text-red-800 hover:underline transition" onclick="${clickAction}">
                        ${this.textPack.readButton} &rarr;
                    </button>
                `;
            })
            .catch(err => {
                console.error("Librarian Error:", err);
            });

        // (2) Recommendations (이하는 동일)
        fetch(`/api/news/rag/external/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                this.renderVectorRecs(data.vector_recommendations || []);
                this.renderSearchRecs(data.search_recommendations || {});
            })
            .catch(err => {
                const container = document.getElementById('external-list');
                if (container) container.innerHTML = `<div style="color:#e74c3c; text-align:center;">Failed to connect.</div>`;
            });
    },


        // 5. [Embedded] 대시보드 삽입용 Bridge 로더
    // 5. [Embedded] 대시보드 삽입용 Bridge 로더
    loadEmbeddedBridge: function(articleId) {
        if (!articleId) return;

        const section = document.getElementById('section-bridge-dashboard');
        const loadingState = document.getElementById('bridge-loading-state');
        const contentBox = document.getElementById('bridge-content-box');
        
        const slotA = document.getElementById('dash-slot-a');
        const slotB = document.getElementById('dash-slot-b');
        const anchorLabel = document.getElementById('dash-anchor-title');
        
        if (!section) return;

        if (loadingState) {
            loadingState.style.display = 'block';
            loadingState.innerHTML = '<div class="loading-text" style="font-size: 13px;">Analyzing context connections...</div>';
        }
        if (contentBox) contentBox.style.display = 'none';

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
                                <div class="text-gray-600" style="font-weight: bold; font-size: 13px; margin-bottom: 4px;">
                                    No Context Found
                                </div>
                                <div class="text-gray-500" style="font-size: 11px;">
                                    Try reading more articles.
                                </div>
                            </div>
                        `;
                    }
                    return;
                }

                if (loadingState) loadingState.style.display = 'none';
                
                // [수정 1] 레이아웃 변경 (Grid 1단 강제 적용 -> 위/아래 배치)
                if (contentBox) {
                    contentBox.style.display = 'grid';
                    contentBox.classList.remove('md:grid-cols-2'); // 기존 2단 제거
                    contentBox.classList.add('grid-cols-1');      // 1단 적용
                    contentBox.style.gap = '24px';                  // 간격 넓힘
                }

                if (data.anchor && anchorLabel) {
                    anchorLabel.innerText = `Source: "${data.anchor.title.substring(0, 30)}..."`;
                }

                if (data.slot_a) {
                    this.fillBridgeCard(slotA, data.slot_a);
                    // [수정 2] 색깔 바 제거 (회색 테두리로 덮어쓰기)
                    slotA.style.borderLeft = '1px solid #e5e7eb';
                    slotA.style.borderRight = '1px solid #e5e7eb'; // 균형을 위해 양쪽 동일하게
                } else {
                    if(slotA) slotA.style.display = 'none';
                }

                if (data.slot_b) {
                    this.fillBridgeCard(slotB, data.slot_b);
                    // [수정 2] 색깔 바 제거 (회색 테두리로 덮어쓰기)
                    slotB.style.borderLeft = '1px solid #e5e7eb';
                    slotB.style.borderRight = '1px solid #e5e7eb';
                } else {
                    if(slotB) slotB.style.display = 'none';
                }
            })
            .catch(err => {
                if (loadingState) {
                    loadingState.style.display = 'block';
                    loadingState.innerHTML = `<div style="color: #e74c3c; font-size: 12px; padding: 10px;">⚠️ Connection Error</div>`;
                }
            });
    },

    // [Helper] 대시보드 카드 채우기 -> 클릭 시 모달 Open
    fillBridgeCard: function(element, data) {
        if (!element || !data) return;
        const article = data.article;
        const matches = data.matches || [];
        
        // [수정] span 태그에 인라인 스타일 제거 -> CSS가 처리함
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
        // [Undefined 해결] 제목 및 데이터 안전 추출
        // item 안에 article 객체가 있을 수도 있고, item 자체가 기사일 수도 있음
        const rawTitle = item.title || (item.article ? item.article.title : "No Title");
        const title = rawTitle.replace(/<[^>]*>?/gm, ''); // 태그 제거
        
        const summary = item.summary || (item.article ? item.article.summary : "No description available.");
        const link = item.url || (item.article ? item.article.url : "#");
        const thumbnail = item.thumbnail || (item.article ? item.article.thumbnail : "");
        const date = item.date || "";
        
        // 소스 (예: MY LIBRARY, BBC, CNN...)
        const source = item.source || "WEB"; 

        // 추천 이유 (Vector Only)
        const reasonTag = item.reason_tag || "RECOMMEND";
        const reasonDesc = item.reason_desc || "Relevant to your interests";
        const similarity = item.similarity ? Math.round(item.similarity) : null;

        // [디자인 1] 우측 상단 메타데이터 (유사도 or 날짜)
        let metaRight = "";
        if (type === 'vector' && similarity) {
            // 유사도: 보라색 강조 박스
            metaRight = `
                <span class="flex items-center justify-center px-2 py-1 rounded bg-indigo-50 text-indigo-700 border border-indigo-100 text-xs font-bold shadow-sm">
                    ${similarity}% Match
                </span>`;
        } else {
            // 날짜: 회색 텍스트
            metaRight = `<span class="text-[10px] text-gray-400">${date}</span>`;
        }

        // [디자인 2] 추천 이유 행 (Deep Dive 등)
        let reasonRow = "";
        if (type === 'vector' && reasonTag) {
            reasonRow = `
                <div class="flex items-center gap-2 mb-2 mt-1">
                    <span class="flex-shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide bg-red-50 text-red-700 border border-red-100">
                        🎯 ${reasonTag}
                    </span>
                    <span class="text-[10px] text-gray-400 truncate leading-none pt-0.5">
                        ${reasonDesc}
                    </span>
                </div>
            `;
        }

        // [디자인 3] 썸네일 처리
        const imgHtml = thumbnail 
            ? `<img src="${thumbnail}" class="w-full h-full object-cover transition duration-500 group-hover:scale-105" onerror="this.parentElement.innerHTML='<div class=\'w-full h-full flex items-center justify-center bg-gray-100 text-xl\'>📰</div>'">`
            : `<div class="w-full h-full flex items-center justify-center bg-gray-100 text-gray-300 text-xl">📰</div>`;

        const clickAction = `window.open('${link}', '_blank')`;

        // [최종 HTML 레이아웃]
        return `
            <div class="group relative flex gap-4 p-3 bg-white border border-gray-200 shadow-[0_2px_8px_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.08)] hover:border-gray-300 transition-all cursor-pointer rounded-lg mb-3" onclick="${clickAction}">
                
                <div class="w-20 h-20 md:w-24 md:h-24 flex-shrink-0 bg-gray-100 rounded-md overflow-hidden border border-gray-100 relative">
                    ${imgHtml}
                </div>

                <div class="flex-1 min-w-0 flex flex-col">
                    
                    <div class="flex justify-between items-start">
                        <span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-gray-100 text-gray-600 border border-gray-200 self-start">
                            ${source}
                        </span>
                        ${metaRight}
                    </div>

                    ${reasonRow}

                    <h4 class="text-sm md:text-[15px] font-bold text-gray-900 leading-snug group-hover:text-red-800 transition line-clamp-2 mt-1 mb-1">
                        ${title}
                    </h4>

                    <p class="text-xs text-gray-500 line-clamp-1 hidden md:block">
                        ${summary}
                    </p>
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