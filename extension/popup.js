const SERVER_URL = "http://localhost:8000/api/news";

document.addEventListener('DOMContentLoaded', () => {
    const btnSummarize = document.getElementById('btn-summarize');
    const btnSave = document.getElementById('btn-save');
    const summaryBox = document.getElementById('summary-box');
    const statusMsg = document.getElementById('status');

    let currentUrl = "";

    // 1. [요약 시작] 버튼 클릭 시 실행
    btnSummarize.addEventListener('click', async () => {
        // UI 초기화
        btnSummarize.disabled = true;
        btnSummarize.textContent = "AI가 읽는 중...";
        summaryBox.textContent = ""; 
        statusMsg.textContent = "서버와 연결 중...";

        try {
            // 현재 탭의 URL 가져오기
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            currentUrl = tab.url;

            // 서버로 요청 보내기 (POST /summarize/)
            const response = await fetch(`${SERVER_URL}/summarize/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentUrl })
            });

            if (!response.ok) {
                // 이미 저장된 기사 등 에러 처리
                const errData = await response.json();
                if (errData.status === 'ALREADY_SAVED') {
                     summaryBox.textContent = "📚 이미 서재에 저장된 기사입니다.";
                     btnSummarize.textContent = "저장 완료됨";
                     return;
                }
                throw new Error(errData.message || "오류가 발생했습니다.");
            }

            // ★ 핵심: 스트리밍 데이터 읽기 (Reader)
            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            statusMsg.textContent = "작성 중...";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break; // 스트리밍 끝

                // 조각(Chunk)을 글자로 변환해서 화면에 붙이기
                const chunk = decoder.decode(value);
                summaryBox.textContent += chunk;
                
                // 스크롤 자동으로 아래로 내리기
                summaryBox.scrollTop = summaryBox.scrollHeight;
            }

            // 완료 처리
            btnSummarize.classList.add('hidden'); // 요약 버튼 숨기기
            btnSave.classList.remove('hidden');   // 저장 버튼 보이기
            statusMsg.textContent = "요약 완료! 저장하시겠습니까?";

        } catch (error) {
            summaryBox.textContent = "❌ 에러: " + error.message;
            btnSummarize.disabled = false;
            btnSummarize.textContent = "다시 시도";
            statusMsg.textContent = "";
        }
    });

    // 2. [저장] 버튼 클릭 시 실행
    btnSave.addEventListener('click', async () => {
        try {
            const response = await fetch(`${SERVER_URL}/save/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentUrl })
            });

            if (response.ok) {
                btnSave.textContent = "완료되었습니다! ✅";
                btnSave.disabled = true;
                statusMsg.textContent = "내 서재에 안전하게 보관되었습니다.";
                setTimeout(() => window.close(), 2000); // 2초 뒤 창 닫기
            } else {
                throw new Error("저장에 실패했습니다.");
            }
        } catch (error) {
            statusMsg.textContent = "저장 실패: " + error.message;
        }
    });
});