document.addEventListener("DOMContentLoaded", function() {
    
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

            if (targetId === 'view-librarian' && !isLibrarianLoaded) {
                loadLibrarianData();
                isLibrarianLoaded = true;
            }
        });
    });

    // ============================================
    // 2. Load Knowledge Stats
    // ============================================
    loadStatsData();

    // ============================================
    // 3. Load RAG Data (My Librarian)
    // ============================================
    function loadLibrarianData() {
        // (1) Knowledge Time Capsule (Review)
        fetch('/api/news/api/rag/review/')
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                
                if (data.message) {
                    container.innerHTML = `<p style="text-align:center; color:#636e72;">${data.message}</p>`;
                    return;
                }

                container.innerHTML = `
                    <div style="font-size:12px; color:#00b894; margin-bottom:5px; font-weight:bold;">
                        📅 Memory from ${data.date}
                    </div>
                    <div style="font-size:16px; font-weight:bold; color:#2d3436; margin-bottom:10px;">
                        ${data.title}
                    </div>
                    <div class="ai-comment" style="background:#f1f2f6; padding:15px; border-radius:8px; color:#2d3436;">
                        ${data.comment.replace(/\n/g, '<br>')}
                    </div>
                    <button class="btn-link" style="margin-top:15px; width:100%; text-align:center;" onclick="window.open('${data.url}', '_blank')">
                        🔗 Read Original Article
                    </button>
                `;
            })
            .catch(err => {
                const container = document.getElementById('review-card');
                if(container) container.innerHTML = `<p style="color:#b2bec3;">Failed to connect to AI.</p>`;
            });

        // (2) Knowledge Expansion (External)
        fetch('/api/news/api/rag/external/')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('external-list');
            const items = data.articles || []; 
            const keyword = data.keyword || "General News";

            if (items.length === 0) {
                container.innerHTML = "<div style='padding:10px; color:#b2bec3; text-align:center;'>No recommendations found at the moment.</div>";
                return;
            }

            let html = `<div style="margin-bottom:15px; font-weight:bold; color:#0984e3; font-size:15px;">
                            🛰️ AI Keyword: <span style="color:#2d3436;">#${keyword}</span>
                        </div>`;
            
            items.forEach(item => {
                const link = item.url || item.link || '#';
                const title = item.title;
                const summary = item.summary || item.snippet || "No summary available.";
                const source = item.source || "News Source";
                
                let dateStr = "Recent";
                if (item.date) {
                    try {
                        const d = new Date(item.date);
                        dateStr = `${d.getFullYear()}.${d.getMonth()+1}.${d.getDate()}`;
                    } catch(e) {}
                }

                html += `
                    <div class="reco-item" onclick="window.open('${link}', '_blank')" 
                         style="cursor:pointer; margin-bottom:12px; padding:15px; background:#fff; border-radius:10px; border:1px solid #dfe6e9; box-shadow: 0 2px 5px rgba(0,0,0,0.03);">
                        
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <span style="font-size:10px; background:#ffeaa7; color:#d63031; padding:2px 8px; border-radius:4px; font-weight:bold;">HOT</span>
                            <span style="font-size:11px; color:#b2bec3;">${source} | ${dateStr}</span>
                        </div>
                        
                        <div style="font-weight:bold; margin-bottom: 8px; color:#2d3436; font-size:16px; line-height:1.4;">
                            ${title}
                        </div>
                        
                        <div style="font-size:13px; color:#636e72; line-height:1.5;">
                            ${summary}
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        })
        .catch(err => {
            console.error("Recommendation Error:", err);
            const container = document.getElementById('external-list');
            if (container) container.innerHTML = `<div style="color:#ff7675;">Failed to load data.</div>`;
        });
    }

    // ============================================
    // Load Stats Function
    // ============================================
    function loadStatsData() {
        if (!document.getElementById('weeklyChart')) return; 

        fetch('/api/news/api/stats/')
            .then(res => res.json())
            .then(data => {
                document.getElementById('user-persona').innerText = data.persona || "Knowledge Explorer";

                const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
                new Chart(weeklyCtx, {
                    type: 'bar', 
                    data: {
                        labels: data.daily_activity.map(d => d.date),
                        datasets: [{
                            label: 'Articles Read',
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
                            x: { grid: { display: false }, ticks: { color: '#636e72' } } 
                        }
                    }
                });

                const categoryCtx = document.getElementById('categoryChart').getContext('2d');
                const categories = data.category_distribution;
                
                new Chart(categoryCtx, {
                    type: 'doughnut',
                    data: {
                        labels: categories.map(c => c.category || 'Others'),
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
                        plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: { size: 11 }, padding: 15, color: '#2d3436' } } },
                        cutout: '70%'
                    }
                });
            })
            .catch(err => console.error("Error loading stats:", err));
    }
});