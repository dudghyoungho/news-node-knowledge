document.addEventListener("DOMContentLoaded", function() {
    
    // ============================================
    // 1. 사이드바 탭 전환 로직
    // ============================================
    const menuItems = document.querySelectorAll('.menu-item');
    const sections = document.querySelectorAll('.view-section');
    
    // RAG 데이터를 한 번만 로딩하기 위한 플래그
    let isLibrarianLoaded = false;

    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            // 1) 모든 버튼 활성화 해제
            menuItems.forEach(btn => btn.classList.remove('active'));
            // 2) 클릭한 버튼 활성화
            item.classList.add('active');

            // 3) 모든 섹션 숨기기
            sections.forEach(sec => sec.style.display = 'none');
            
            // 4) 타겟 섹션 보여주기
            const targetId = item.getAttribute('data-target');
            document.getElementById(targetId).style.display = 'flex';

            // 5) 만약 'My Librarian' 탭이라면 API 호출 (최초 1회)
            if (targetId === 'view-librarian' && !isLibrarianLoaded) {
                loadLibrarianData();
                isLibrarianLoaded = true;
            }
        });
    });

    // ============================================
    // 2. 기존 차트 로직 (My Knowledge)
    // ============================================
    loadStatsData(); // 페이지 로드 시 바로 실행

    // ============================================
    // 3. RAG 데이터 로딩 로직 (My Librarian)
    // ============================================
    function loadLibrarianData() {
        // (1) 지식 타임캡슐 (Review) API 호출
        fetch('/api/news/api/rag/review/')
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('review-card');
                
                if (data.message) { // 기사가 없을 때
                    container.innerHTML = `<p style="text-align:center;">${data.message}</p>`;
                    return;
                }

                // AI 응답 렌더링
                container.innerHTML = `
                    <div style="font-size:12px; color:#636e72; margin-bottom:5px;">
                        📅 ${data.date} 에 저장된 기억
                    </div>
                    <div style="font-size:16px; font-weight:bold; color:#2d3436;">
                        ${data.title}
                    </div>
                    <div class="ai-comment">
                        🤖 <b>AI 사서의 질문:</b><br>
                        ${data.comment.replace(/\n/g, '<br>')}
                    </div>
                    <button class="btn-link" style="margin-top:10px; font-size:12px;" onclick="window.location.href='/news/article/${data.id}'">
                        기사 다시 읽기 👉
                    </button>
                `;
            })
            .catch(err => {
                document.getElementById('review-card').innerHTML = `<p style="color:red;">AI 연결 실패: ${err.message}</p>`;
            });

        // (2) 지식 확장 (External) API 호출
        fetch('/api/news/api/rag/external/')
            .then(res => res.json())
            .then(data => {
                const container = document.getElementById('external-list');
                const keyword = data.keyword;
                const items = data.items || [];

                if (items.length === 0) {
                    container.innerHTML = "<p>추천할 만한 외부 기사를 찾지 못했습니다.</p>";
                    return;
                }

                let html = `<div style="margin-bottom:10px; font-weight:bold; color:#0984e3;">🔍 분석된 키워드: #${keyword}</div>`;
                
                items.forEach(item => {
                    html += `
                        <div class="reco-item" onclick="window.open('${item.url}', '_blank')">
                            <span class="reco-tag">외부 추천</span>
                            <div style="font-weight:bold; margin: 5px 0;">${item.title}</div>
                            <div style="font-size:13px; color:#636e72;">
                                💡 ${item.reason}
                            </div>
                        </div>
                    `;
                });
                
                container.innerHTML = html;
            })
            .catch(err => {
                document.getElementById('external-list').innerHTML = `<p style="color:red;">추천 로딩 실패</p>`;
            });
    }

    // ============================================
    // (기존) 통계 데이터 로드 함수
    // ============================================
    function loadStatsData() {
        fetch('/api/news/api/stats/')
            .then(res => res.json())
            .then(data => {
                // 페르소나
                document.getElementById('user-persona').innerText = data.persona;

                // 주간 차트
                const weeklyCtx = document.getElementById('weeklyChart').getContext('2d');
                new Chart(weeklyCtx, {
                    type: 'bar',
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
                        scales: { y: { display: false }, x: { grid: { display: false } } }
                    }
                });

                // 관심사 차트
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
                        plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: { size: 11 }, padding: 15 } } },
                        cutout: '70%'
                    }
                });
            })
            .catch(err => console.error("Error loading stats:", err));
    }
});