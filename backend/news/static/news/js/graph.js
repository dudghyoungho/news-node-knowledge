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

    // ★ [수정됨] 1. 호버 상태를 추적할 변수 선언
    let hoverNode = null;

    // 2. Force Graph 초기화
    const Graph = ForceGraph()(elem)
        .backgroundColor('#000011')
        .nodeId('id')
        .nodeLabel('') // ★ [수정됨] 기본 브라우저 툴팁 제거 (캔버스에 직접 그리므로)
        .nodeVal('val')
        .linkCanvasObject((link, ctx, globalScale) => {
            // 1. [카테고리 연결] (기본 뼈대)
            // 백엔드에서 type="category"로 보낸 링크들
            if (link.type === 'category' || !link.type) { // !link.type은 호환성용
                // 줌 아웃 시 카테고리 선 숨기기 (깔끔함 유지)
                if (globalScale < 0.6) return; 

                ctx.beginPath();
                ctx.moveTo(link.source.x, link.source.y);
                ctx.lineTo(link.target.x, link.target.y);
                
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)'; // 연한 흰색 실선
                ctx.lineWidth = 1.5 / globalScale;
                ctx.setLineDash([]); // 실선으로 초기화
                ctx.stroke();
                return;
            }

            // 2. [의미적 연결] (Semantic Linking)
            // 백엔드에서 type="semantic"으로 보낸 링크들
            // ★ 조건: "현재 마우스가 올라간 노드(hoverNode)"와 연결된 선일 때만 그림
            const isConnectedToHover = hoverNode && (link.source === hoverNode || link.target === hoverNode);
            
            if (link.type === 'semantic' && isConnectedToHover) {
                ctx.beginPath();
                ctx.moveTo(link.source.x, link.source.y);
                ctx.lineTo(link.target.x, link.target.y);

                // 강조 효과 (점선)
                ctx.strokeStyle = '#fab1a0'; // 살구색 (눈에 잘 띄는 색)
                ctx.lineWidth = 2.0 / globalScale; // 조금 더 두껍게
                ctx.setLineDash([4 / globalScale, 2 / globalScale]); // 점선 패턴 (줌 레벨 대응)
                ctx.stroke();
                
                // 다 그렸으면 점선 설정 초기화 (다른 그림에 영향 안 주게)
                ctx.setLineDash([]); 
            }
            // 그 외(호버 안 된 의미적 연결)는 그리지 않음 (투명 처리)
        })
        // .linkWidth(...) 설정은 linkCanvasObject가 있으면 무시되므로 삭제해도 됩니다.
        
        // ... (이후 코드: nodeCanvasObject 등)
        

        .nodeCanvasObject((node, ctx, globalScale) => {
            // [설정] 화면 배율에 따른 가시성 임계값
            const SHOW_NODE_THRESHOLD = 0.6; // 이보다 확대해야 '기사 점'이 보임
            const SHOW_TEXT_THRESHOLD = 1.2; // 이보다 확대해야 '기사 제목'이 보임 (너무 많으면 1.5로 올리세요)

            const isCategory = (node.group === 2);
            const isHover = (node === hoverNode);
            
            //숨김 처리 - 멀리 있을 때 기사는 아예 안 그림 (카테고리는 항상 그림)
            if (!isCategory && !isHover && globalScale < SHOW_NODE_THRESHOLD) {
                return;
            }

            // 2. 노드 그리기 (원/이미지)
            const radius = Math.sqrt(node.val) * 5; 
            
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);

            // 이미지가 있고, 어느 정도 확대되었거나 호버 상태일 때만 이미지 렌더링
            if (node.imgObj && (globalScale > SHOW_NODE_THRESHOLD || isHover)) {
                ctx.save();
                ctx.clip();
                ctx.drawImage(node.imgObj, node.x - radius, node.y - radius, radius * 2, radius * 2);
                ctx.restore();
                
                // 이미지 테두리
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 1.5 / globalScale;
                ctx.stroke();
            } else {
                // 이미지가 없거나 멀리 있을 때는 색상 원
                ctx.fillStyle = isCategory ? '#ff7675' : '#0984e3'; 
                ctx.fill();
            }

            // 호버 시 하이라이트 링 (선택됨 강조)
            if (isHover) {
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 3 / globalScale; // 두께감 있게
                ctx.stroke();
            }

            // 3. [텍스트 그리기] (스마트 라벨링)
            // 조건: 카테고리이거나 OR 호버중이거나 OR 충분히 확대되었을 때
            const shouldShowText = isCategory || isHover || (globalScale > SHOW_TEXT_THRESHOLD);

            if (shouldShowText) {
                const label = node.name;
                
                let fontSize = 12 / globalScale;
                if (isCategory && globalScale < SHOW_NODE_THRESHOLD) {
                    fontSize = 14 / globalScale; // 멀리서도 카테고리는 큼직하게
                } else if (isHover) {
                    fontSize = 14 / globalScale; // 호버 시 살짝 크게
                }

                ctx.font = `${isCategory ? 'bold' : ''} ${fontSize}px Sans-Serif`;
                
                // 텍스트 배경 박스 계산
                const textWidth = ctx.measureText(label).width;
                const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4); 

                const textX = node.x;
                const textY = node.y + radius + (fontSize / 2) + 6;

                // [배경 박스] 글씨가 배경에 묻히지 않도록 반투명 블랙 처리
                ctx.fillStyle = isHover ? 'rgba(0, 0, 0, 0.9)' : 'rgba(0, 0, 0, 0.6)';
                // 카테고리는 조금 더 연하게
                if (isCategory && !isHover) ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';

                ctx.fillRect(
                    textX - bckgDimensions[0] / 2, 
                    textY - bckgDimensions[1] / 2 - 2, 
                    bckgDimensions[0], 
                    bckgDimensions[1]
                );

                // [글씨 색상]
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = isCategory ? '#ff7675' : '#ffffff';
                
                // 호버 시엔 무조건 흰색/노란색 강조
                if (isHover) ctx.fillStyle = '#fab1a0'; 

                ctx.fillText(label, textX, textY);
            }
        })

        .nodePointerAreaPaint((node, color, ctx) => {
            const radius = Math.sqrt(node.val) * 5; 
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius + 2, 0, 2 * Math.PI, false); 
            ctx.fill();
        })
        // [수정됨] 호버 이벤트 추가
        .onNodeHover(node => {
            elem.style.cursor = node ? 'pointer' : null; // 마우스 커서 변경
            hoverNode = node || null;
        })
        .d3Force('charge', d3.forceManyBody().strength(-100)) 
        .d3Force('link', d3.forceLink().distance(80).id(d => d.id)) 
        .onNodeClick(node => {
            if (node.group === 1) { openModal(node); } 
            else { Graph.centerAt(node.x, node.y, 1000); Graph.zoom(4, 2000); }
        });

    // 3. 데이터 불러오기 (기존 동일)
    const urlParams = new URLSearchParams(window.location.search);
    fetch(`/api/news/graph/data/${window.location.search}`) 
    .then(res => res.json())
        .then(data => {
            if (data.nodes.length === 0) {
                emptyMsg.style.display = 'block';
            } else {
                emptyMsg.style.display = 'none';

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

    // 4. 모달 제어 함수 (기존 동일)
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