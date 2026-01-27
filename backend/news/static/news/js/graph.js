document.addEventListener('DOMContentLoaded', () => {
    const elem = document.getElementById('graph-container');
    const emptyMsg = document.getElementById('empty-message');
    
    // 모달 관련 요소들
    const modal = document.getElementById('summary-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalImg = document.getElementById('modal-img');
    const modalSummary = document.getElementById('modal-summary');
    const btnGoArticle = document.getElementById('btn-go-article');
    let currentLink = "";
    let hoverNode = null;

    // [핵심] Force Graph 초기화
    // 사이드바 관련 로직(miniChart, graphWrapper)은 모두 삭제하고, window 크기 기준 설정
    const Graph = ForceGraph()(elem)
        .backgroundColor('rgba(0,0,0,0)') // CSS에서 투명 배경 처리함
        .width(window.innerWidth)         // 화면 전체 너비
        .height(window.innerHeight)       // 화면 전체 높이
        .nodeId('id')
        .nodeLabel('') 
        .nodeVal('val')
        
        // --------------------------------------------------
        // [디자인] 링크(선) 스타일링: 네온 효과
        // --------------------------------------------------
        .linkCanvasObject((link, ctx, globalScale) => {
            if (globalScale < 0.5 && link.type === 'category') return;

            const isConnectedToHover = hoverNode && (link.source === hoverNode || link.target === hoverNode);
            
            ctx.beginPath();
            ctx.moveTo(link.source.x, link.source.y);
            ctx.lineTo(link.target.x, link.target.y);
            
            ctx.lineWidth = (link.type === 'semantic' ? 2 : 1) / globalScale;
            ctx.shadowBlur = 0;

            if (link.type === 'category' || !link.type) {
                // 카테고리 연결선: 연한 파랑
                ctx.strokeStyle = 'rgba(116, 185, 255, 0.3)'; 
            } else if (link.type === 'semantic') {
                // 의미적 연결선: 붉은 계열 + 점선
                ctx.strokeStyle = isConnectedToHover ? '#fab1a0' : 'rgba(250, 177, 160, 0.4)';
                if(isConnectedToHover) {
                    ctx.shadowColor = '#fab1a0';
                    ctx.shadowBlur = 10; // 호버 시 발광
                }
                ctx.setLineDash([4 / globalScale, 3 / globalScale]);
            }
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.shadowBlur = 0;
        })

        // --------------------------------------------------
        // [디자인] 노드 스타일링: 발광 효과 + 이미지
        // --------------------------------------------------
        .nodeCanvasObject((node, ctx, globalScale) => {
            const SHOW_NODE_THRESHOLD = 0.6;
            const isCategory = (node.group === 2);
            const isHover = (node === hoverNode);
            const radius = Math.sqrt(node.val) * 6;

            if (!isCategory && !isHover && globalScale < SHOW_NODE_THRESHOLD) return;

            // 1. 발광(Glow) 효과 그리기
            if (isCategory || isHover) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI);
                ctx.fillStyle = isCategory ? 'rgba(116, 185, 255, 0.2)' : 'rgba(250, 177, 160, 0.2)';
                ctx.fill();
            }

            // 2. 노드 본체 그리기
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
            
            if (node.imgObj && (globalScale > SHOW_NODE_THRESHOLD || isHover)) {
                // [이미지 노드]
                ctx.save();
                ctx.clip();
                ctx.drawImage(node.imgObj, node.x - radius, node.y - radius, radius * 2, radius * 2);
                ctx.restore();
                
                // 테두리 링
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
                ctx.strokeStyle = isCategory ? '#74b9ff' : '#fab1a0';
                ctx.lineWidth = 2 / globalScale;
                ctx.stroke();
            } else {
                // [기본 노드] 그라데이션 원
                const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, radius);
                if (isCategory) {
                    gradient.addColorStop(0, '#74b9ff'); gradient.addColorStop(1, '#0984e3');
                } else {
                    gradient.addColorStop(0, '#fab1a0'); gradient.addColorStop(1, '#e17055');
                }
                ctx.fillStyle = gradient;
                ctx.fill();
            }

            // 3. 텍스트 라벨 그리기
            const shouldShowText = isCategory || isHover || (globalScale > 1.2);
            if (shouldShowText) {
                const label = node.name;
                const fontSize = (isHover ? 14 : 12) / globalScale;
                ctx.font = `${isCategory ? 'bold' : ''} ${fontSize}px Sans-Serif`;
                
                const textWidth = ctx.measureText(label).width;
                const bckgDimensions = [textWidth + fontSize, fontSize * 1.4];
                const textX = node.x; const textY = node.y + radius + fontSize/2 + 6;

                // 텍스트 배경 (가독성 확보)
                ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
                ctx.fillRect(textX - bckgDimensions[0]/2, textY - bckgDimensions[1]/2, bckgDimensions[0], bckgDimensions[1]);

                ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                ctx.fillStyle = isCategory ? '#74b9ff' : '#fff';
                ctx.fillText(label, textX, textY);
            }
        })
        .onNodeHover(node => {
            elem.style.cursor = node ? 'pointer' : null;
            hoverNode = node || null;
        })
        .onNodeClick(node => {
            if (node.group === 1) openModal(node); // 기사 노드 클릭 시 모달 오픈
            else {
                // 카테고리 노드 클릭 시 확대 및 중심 이동
                Graph.centerAt(node.x, node.y, 1000);
                Graph.zoom(4, 2000);
            }
        })
        // 물리 엔진 설정 (모여있게)
        .d3Force('link', d3.forceLink().id(d => d.id).distance(80))
        .d3Force('charge', d3.forceManyBody().strength(-70))
        .d3Force('center', d3.forceCenter(window.innerWidth / 2, window.innerHeight / 2)); // [수정] 화면 중앙 정렬

    // 데이터 로드
    const urlParams = new URLSearchParams(window.location.search);
    fetch(`/api/news/graph/data/${window.location.search}`) 
        .then(res => res.json())
        .then(data => {
            if (data.nodes.length === 0) emptyMsg.style.display = 'block';
            else {
                emptyMsg.style.display = 'none';
                data.nodes.forEach(node => {
                    // 이미지 프리로딩
                    if (node.img) {
                        const img = new Image();
                        img.src = node.img;
                        img.onload = () => { node.imgObj = img; }; 
                    }
                });
                Graph.graphData(data);
                // 초기 줌 아웃 (전체 보기)
                setTimeout(() => Graph.zoomToFit(1000, 50), 500);
            }
        })
        .catch(err => console.error(err));

    // 모달 제어 함수
    function openModal(node) {
        modalTitle.innerText = node.name;
        modalSummary.innerText = node.summary || "No summary available.";
        currentLink = node.url; 
        if (node.img) {
            modalImg.src = node.img; modalImg.style.display = 'block';
        } else {
            modalImg.style.display = 'none';
        }
        modal.style.display = 'flex'; 
    }
    const closeModal = () => { modal.style.display = 'none'; };
    
    document.querySelector('.close-btn').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
    btnGoArticle.addEventListener('click', () => { if (currentLink) window.open(currentLink, '_blank'); });

    // 리사이즈 이벤트: 브라우저 창 크기가 변하면 그래프 크기도 즉시 반영
    window.addEventListener('resize', () => {
        const newWidth = window.innerWidth;
        const newHeight = window.innerHeight;

        // 1. 캔버스 크기 변경
        Graph.width(newWidth);
        Graph.height(newHeight);

        // 2. 물리 엔진의 중심점을 새로운 화면 중앙으로 이동
        // (이게 없으면 창을 줄였을 때 노드들이 오른쪽 아래로 쏠려 보입니다)
        Graph.d3Force('center', d3.forceCenter(newWidth / 2, newHeight / 2));

        // 3. 모든 노드가 화면에 들어오도록 줌 레벨 자동 조정 (애니메이션 500ms)
        // 약간의 여백(padding) 50px을 둡니다.
        setTimeout(() => {
            Graph.zoomToFit(500, 50); 
        }, 100); // 0.1초 뒤 실행 (즉시 실행 시 렉 방지)
    });
});