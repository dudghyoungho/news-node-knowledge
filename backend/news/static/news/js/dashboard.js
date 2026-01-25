document.addEventListener("DOMContentLoaded", function() {
    
    // ============================================
    // 1. 사이드바 탭 전환 로직
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
            if(targetSection) targetSection.style.display = 'flex'; // CSS에 맞춰 flex로

            if (targetId === 'view-librarian' && !isLibrarianLoaded) {
                loadLibrarianData();
                isLibrarianLoaded = true;
            }
        });
    });

    // ============================================
    // 2. 기존 차트 로직 (My Knowledge)
    // ============================================
    loadStatsData();

    // ============================================
    // 3. RAG 데이터 로딩 로직 (My Librarian)
    // ============================================
    function loadLibrarianData() {
        // (1) 지식 타임캡슐 (Review) API 호출
        fetch('/api/news/api/rag/review/')
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                
                if (data.message) {
                    container.innerHTML = `<p style="text-align:center; color:#636e72;">${data.message}</p>`;
                    return;
                }

                // [수정] 버튼 클릭 시 window.open으로 원문(data.url) 열기
                // [수정] 텍스트 색상을 진한 회색(#2d3436)으로 변경하여 가독성 확보
                container.innerHTML = `
                    <div style="font-size:12px; color:#00b894; margin-bottom:5px; font-weight:bold;">
                        📅 ${data.date} 에 저장된 기억
                    </div>
                    <div style="font-size:16px; font-weight:bold; color:#2d3436; margin-bottom:10px;">
                        ${data.title}
                    </div>
                    <div class="ai-comment" style="background:#f1f2f6; padding:15px; border-radius:8px; color:#2d3436;">
                        ${data.comment.replace(/\n/g, '<br>')}
                    </div>
                    <button class="btn-link" style="margin-top:15px; width:100%; text-align:center;" onclick="window.open('${data.url}', '_blank')">
                        🔗 기사 원문 다시 읽기
                    </button>
                `;
            })
            .catch(err => {
                const container = document.getElementById('review-card');
                if(container) container.innerHTML = `<p style="color:#b2bec3;">AI 연결 실패</p>`;
            });

        // (2) 지식 확장 (External) API 호출
        fetch('/api/news/api/rag/external/')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('external-list');
            const items = data.articles || []; 
            const keyword = data.keyword || "주요 뉴스";

            if (items.length === 0) {
                container.innerHTML = "<div style='padding:10px; color:#b2bec3; text-align:center;'>추천할 만한 기사를 찾지 못했습니다.</div>";
                return;
            }

            // [수정] 키워드 색상을 진하게 변경
            let html = `<div style="margin-bottom:15px; font-weight:bold; color:#0984e3; font-size:15px;">
                            🛰️ AI 분석 키워드: <span style="color:#2d3436;">#${keyword}</span>
                        </div>`;
            
            items.forEach(item => {
                const link = item.url || item.link || '#';
                const title = item.title;
                const summary = item.summary || item.snippet || "요약 내용이 없습니다.";
                const source = item.source || "Naver News";
                
                let dateStr = "최신";
                if (item.date) {
                    try {
                        const d = new Date(item.date);
                        dateStr = `${d.getFullYear()}.${d.getMonth()+1}.${d.getDate()}`;
                    } catch(e) {}
                }

                // [디자인 대폭 수정] 
                // 1. 배경을 흰색(#fff)으로 변경
                // 2. 글씨색을 진한 회색(#2d3436)으로 변경
                // 3. 테두리(border) 추가로 카드 느낌 강화
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
            console.error("추천 로딩 에러:", err);
            const container = document.getElementById('external-list');
            if (container) container.innerHTML = `<div style="color:#ff7675;">데이터를 불러오지 못했습니다.</div>`;
        });
    }

    // ============================================
    // (기존) 통계 데이터 로드 함수
    // ============================================
    function loadStatsData() {
        if (!document.getElementById('weeklyChart')) return; // 차트 없으면 패스

        fetch('/api/news/api/stats/')
            .then(res => res.json())
            .then(data => {
                document.getElementById('user-persona').innerText = data.persona || "지식 탐험가";

                const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
                new Chart(weeklyCtx, {
                    type: 'bar', // bar 차트 유지
                    data: {
                        labels: data.daily_activity.map(d => d.date),
                        datasets: [{
                            label: '읽은 기사',
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
                        labels: categories.map(c => c.category || '기타'),
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