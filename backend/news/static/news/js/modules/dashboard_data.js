// dashboard_data.js - API Fetching & Rendering
const DashboardData = {
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

    // 3. Librarian 데이터 (Time Capsule + Recommendations)
    loadLibrarianData: function() {
        // (1) Time Capsule
        fetch(`/api/news/rag/review/?region=${this.region}`)
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                if (data.message) {
                    container.innerHTML = `<p style="text-align:center; color:#636e72; padding: 20px;">${data.message}</p>`;
                    return;
                }
                container.innerHTML = `
                    <div style="font-size:12px; color:#55efc4; margin-bottom:5px; font-weight:bold;">
                        ${this.textPack.reviewTitle} ${data.date}
                    </div>
                    <div style="font-size:16px; font-weight:bold; color:#fff; margin-bottom:15px; line-height: 1.4;">
                        ${data.title}
                    </div>
                    <div class="ai-comment" style="background:rgba(255,255,255,0.05); padding:15px; border-radius:8px; color:#dfe6e9; font-style:italic; border-left: 3px solid #55efc4;">
                        "${data.comment.replace(/\n/g, '<br>')}"
                    </div>
                    <button class="btn-link" style="margin-top:15px; width:100%; text-align:center; background:none; border:none; color:#74b9ff; cursor:pointer; font-weight:bold;" onclick="window.open('${data.url}', '_blank')">
                        ${this.textPack.readButton} →
                    </button>
                `;
            })
            .catch(err => {
                const container = document.getElementById('review-card');
                if(container) container.innerHTML = `<p style="color:#636e72; text-align:center;">AI Librarian is sleeping...</p>`;
            });

        // (2) External & Vector Recommendations
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

    // --- Helper Render Functions ---
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
    },

    renderVectorRecs: function(items) {
        const container = document.getElementById('vector-list');
        if (items.length === 0) {
            container.innerHTML = `<div style="padding:15px; color:#636e72; font-size:13px; text-align:center;">Read more articles to get personalized vector recommendations.</div>`;
            return;
        }
        let html = '';
        items.forEach(item => {
            html += `
                <div class="rec-item">
                    <div style="flex: 1; margin-right: 15px;">
                        <div style="font-size:14px; font-weight:bold; color:#fff; margin-bottom:4px; line-height:1.4;">${item.title}</div>
                        <div class="meta-info">
                            <span style="color:#a29bfe;">● ${item.region}</span> 
                            <span style="margin-left:8px;">${item.summary ? item.summary.substring(0, 40)+'...' : ''}</span>
                        </div>
                    </div>
                    <div class="similarity-score">
                        ${item.similarity}%
                        <div style="font-size:9px; font-weight:normal; margin-top:2px; opacity:0.8;">${this.textPack.similarity}</div>
                    </div>
                </div>`;
        });
        container.innerHTML = html;
    },

    renderSearchRecs: function(data) {
        const container = document.getElementById('external-list');
        const keywordContainer = document.getElementById('discovery-keywords');
        const items = data.articles || [];
        const keywords = (data.keywords || data.keyword || "General").split(',');

        let kwHtml = '';
        keywords.forEach(k => { kwHtml += `<span class="keyword-tag">#${k.trim()}</span>`; });
        keywordContainer.innerHTML = kwHtml;

        if (items.length === 0) {
            container.innerHTML = `<div style='padding:20px; color:#636e72; text-align:center;'>${this.textPack.noExternal}</div>`;
            return;
        }

        let html = '';
        items.forEach(item => {
            const link = item.url || item.link || '#';
            const title = item.title.replace(/<[^>]*>?/gm, ''); 
            const summary = item.summary || item.snippet || "";
            const source = item.source || this.textPack.source;
            let dateStr = "";
            try { dateStr = (item.date || item.pubDate).substring(0, 10); } catch(e) {}

            html += `
                <div class="rec-item" onclick="window.open('${link}', '_blank')">
                    <div style="flex: 1;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <span style="font-size:10px; background:rgba(85, 239, 196, 0.15); color:#55efc4; padding:2px 6px; border-radius:4px; font-weight:bold;">${source}</span>
                            <span style="font-size:10px; color:#636e72;">${dateStr}</span>
                        </div>
                        <div style="font-weight:bold; margin-bottom: 6px; color:#dfe6e9; font-size:14px; line-height:1.4;">${title}</div>
                        ${summary ? `<div style="font-size:12px; color:#b2bec3; line-height:1.4; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:1; -webkit-box-orient:vertical;">${summary}</div>` : ''}
                    </div>
                </div>`;
        });
        container.innerHTML = html;
    }
};