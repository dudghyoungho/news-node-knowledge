document.addEventListener('DOMContentLoaded', () => {
    const elem = document.getElementById('graph-container');
    const emptyMsg = document.getElementById('empty-message');
    
    // 모달 관련 요소
    const modal = document.getElementById('summary-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalImg = document.getElementById('modal-img');
    const modalSummary = document.getElementById('modal-summary');
    const btnGoArticle = document.getElementById('btn-go-article');
    let currentLink = "";

    // 1. Force Graph 초기화
    const Graph = ForceGraph()(elem)
        .backgroundColor('#000011')
        .nodeId('id')
        .nodeLabel('name')
        .nodeVal('val')
        .linkColor(() => 'rgba(255,255,255,0.2)')
        .linkWidth(1.5)
        
        // 커스텀 노드 렌더링
        .nodeCanvasObject((node, ctx, globalScale) => {
            const radius = Math.sqrt(node.val) * 5; 
            const fontSize = 12 / globalScale;

            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);

            if (node.imgObj) {
                ctx.save();
                ctx.clip();
                ctx.drawImage(node.imgObj, node.x - radius, node.y - radius, radius * 2, radius * 2);
                ctx.restore();
                
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 1.5 / globalScale;
                ctx.stroke();
            } else {
                const color = node.group === 2 ? '#ff7675' : '#0984e3'; 
                ctx.fillStyle = color;
                ctx.fill();
            }

            if (globalScale > 0.6) {
                ctx.font = `${fontSize}px Sans-Serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
                ctx.fillText(node.name, node.x, node.y + radius + (fontSize/2) + 4);
            }
        })
        .nodePointerAreaPaint((node, color, ctx) => {
            const radius = Math.sqrt(node.val) * 5; 
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius + 2, 0, 2 * Math.PI, false); 
            ctx.fill();
        })
        .d3Force('charge', d3.forceManyBody().strength(-100)) 
        .d3Force('link', d3.forceLink().distance(80).id(d => d.id)) 
        .onNodeClick(node => {
            if (node.group === 1) { openModal(node); } 
            else { Graph.centerAt(node.x, node.y, 1000); Graph.zoom(4, 2000); }
        });

    // 2. 데이터 불러오기
    fetch('/api/news/api/graph/')
        .then(res => res.json())
        .then(data => {
            if (data.nodes.length === 0) {
                emptyMsg.style.display = 'block';
            } else {
                emptyMsg.style.display = 'none';

                // 이미지 사전 로딩
                data.nodes.forEach(node => {
                    if (node.img) {
                        const img = new Image();
                        img.src = node.img;
                        img.onload = () => { node.imgObj = img; }; 
                    }
                });

                Graph.graphData(data);
                setTimeout(() => Graph.zoomToFit(500, 50), 200);
            }
        })
        .catch(err => console.error(err));

    // 3. 모달 제어 함수
    function openModal(node) {
        modalTitle.innerText = node.name;
        modalSummary.innerText = node.summary || "요약 내용이 없습니다.";
        currentLink = node.url; 
        
        if (node.img) {
            modalImg.src = node.img;
            modalImg.style.display = 'block';
        } else {
            modalImg.style.display = 'none';
        }

        modal.style.display = 'block';
    }

    const closeModal = () => { modal.style.display = 'none'; };

    // 이벤트 리스너 연결
    document.querySelector('.close-btn').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
    btnGoArticle.addEventListener('click', () => { if (currentLink) window.open(currentLink, '_blank'); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

    // 반응형 리사이즈
    window.addEventListener('resize',() => {
        Graph.width(window.innerWidth);
        Graph.height(window.innerHeight);
    }); 
});