document.addEventListener("DOMContentLoaded", function() {
    // 통계 데이터 가져오기
    fetch('/api/news/api/stats/')
        .then(res => {
            if (!res.ok) throw new Error(`서버 에러 (${res.status})`);
            const contentType = res.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                return res.json();
            } else {
                throw new Error("HTML 응답을 받았습니다.");
            }
        })
        .then(data => {
            const labels = data.map(item => item.date);
            const counts = data.map(item => item.count);

            const ctx = document.getElementById('activityChart').getContext('2d');
            
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: '읽은 기사 수',
                        data: counts,
                        backgroundColor: '#0984e3',
                        borderRadius: 5,
                        barThickness: 30
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, ticks: { stepSize: 1 } },
                        x: { grid: { display: false } }
                    }
                }
            });
        })
        .catch(err => {
            console.error("통계 로딩 실패:", err);
            const container = document.getElementById('activityChart').parentElement;
            container.innerHTML = `<p style="color:red; text-align:center; padding-top:50px;">데이터 로딩 실패<br><small>${err.message}</small></p>`;
        });
});