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
    const Graph = ForceGraph()(elem)
        .backgroundColor('rgba(0,0,0,0)') 
        .width(window.innerWidth)         
        .height(window.innerHeight)       
        .nodeId('id')
        .nodeLabel('') 
        .nodeVal('val')
        
        // --------------------------------------------------
        // [디자인] 링크(선) 스타일링: 굵기 증가 및 명확한 구분
        // --------------------------------------------------
        .linkCanvasObject((link, ctx, globalScale) => {
            if (globalScale < 0.5 && link.type === 'category') return;

            const isConnectedToHover = hoverNode && (link.source === hoverNode || link.target === hoverNode);
            
            ctx.beginPath();
            ctx.moveTo(link.source.x, link.source.y);
            ctx.lineTo(link.target.x, link.target.y);
            
            // 1. [수정] 선의 굵기(lineWidth)를 전체적으로 대폭 증가
            let baseWidth = 2;
            if (link.type === 'semantic') baseWidth = 4; // 벡터 유사도 (6 -> 4)
            else if (link.type === 'entity' || link.type === 'shared_entity') baseWidth = 2.5; // NER 연결선 (4 -> 2.5)
            else baseWidth = 2; // 카테고리 실선 (3 -> 2)

            ctx.lineWidth = baseWidth / globalScale;
            ctx.shadowBlur = 0;

            // 2. [수정] 선 타입별 색상, 불투명도, 점선 패턴 명확히 구분
            if (link.type === 'category' || !link.type) {
                // ① 카테고리 연결선: 연한 파랑 (실선)
                ctx.strokeStyle = isConnectedToHover ? '#74b9ff' : 'rgba(116, 185, 255, 0.4)'; 
                if(isConnectedToHover) { ctx.shadowColor = '#74b9ff'; ctx.shadowBlur = 8; }
                // 실선이므로 LineDash 설정 안 함
            } 
            else if (link.type === 'semantic') {
                // ② 벡터 유사도(Semantic): 붉은색 (길고 굵은 점선)
                ctx.strokeStyle = isConnectedToHover ? '#ff7675' : 'rgba(250, 177, 160, 0.7)'; // 불투명도 0.7로 진하게
                if(isConnectedToHover) { ctx.shadowColor = '#ff7675'; ctx.shadowBlur = 12; }
                // 굵직한 긴 점선 패턴 (Dash: 8, Gap: 6)
                ctx.setLineDash([8 / globalScale, 6 / globalScale]);
            }
            else if (link.type === 'entity' || link.type === 'shared_entity') {
                // ③ 개체명(NER): 밝은 초록/민트 (짧고 촘촘한 점선)
                ctx.strokeStyle = isConnectedToHover ? '#00b894' : 'rgba(85, 239, 196, 0.7)'; // 불투명도 0.7로 진하게
                if(isConnectedToHover) { ctx.shadowColor = '#00b894'; ctx.shadowBlur = 12; }
                // 촘촘한 도트 느낌의 패턴 (Dash: 3, Gap: 3)
                ctx.setLineDash([3 / globalScale, 3 / globalScale]); 
            }

            ctx.stroke();
            ctx.setLineDash([]); // 다른 선에 영향 주지 않게 점선 초기화
            ctx.shadowBlur = 0;

            // (만약 선 위에 라벨을 띄우는 shared_entity 방식을 사용 중이라면 아래 로직이 작동합니다)
            if (link.type === 'shared_entity' && link.label && globalScale > 0.8) {
                const midX = (link.source.x + link.target.x) / 2;
                const midY = (link.source.y + link.target.y) / 2;
                
                const fontSize = 10 / globalScale;
                ctx.font = `bold ${fontSize}px Sans-Serif`;
                const textWidth = ctx.measureText(link.label).width;
                
                ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                ctx.fillRect(midX - textWidth/2 - 4/globalScale, midY - fontSize/2 - 4/globalScale, textWidth + 8/globalScale, fontSize + 8/globalScale);
                
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = isConnectedToHover ? '#00b894' : '#55efc4';
                ctx.fillText(link.label, midX, midY);
            }
        })
        
        // --------------------------------------------------
        // [디자인] 노드 스타일링: 그룹별 색상 및 발광 효과
        // --------------------------------------------------
        .nodeCanvasObject((node, ctx, globalScale) => {
            const SHOW_NODE_THRESHOLD = 0.6;
            const isCategory = (node.group === 2);
            const isEntity = (node.group === 3); // 개체명 노드 판별
            const isHover = (node === hoverNode);
            const radius = Math.sqrt(node.val) * 6;

            if (!isCategory && !isEntity && !isHover && globalScale < SHOW_NODE_THRESHOLD) return;

            // 1. 발광(Glow) 효과 그리기
            if (isCategory || isEntity || isHover) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI);
                
                if (isCategory) ctx.fillStyle = 'rgba(116, 185, 255, 0.2)'; // 파랑
                else if (isEntity) ctx.fillStyle = 'rgba(85, 239, 196, 0.2)'; // 초록
                else ctx.fillStyle = 'rgba(250, 177, 160, 0.2)'; // 빨강(기사)
                
                ctx.fill();
            }

            // 2. 노드 본체 그리기
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
            
            if (node.imgObj && (globalScale > SHOW_NODE_THRESHOLD || isHover)) {
                // [이미지 노드 - 기사만 해당됨]
                ctx.save();
                ctx.clip();
                ctx.drawImage(node.imgObj, node.x - radius, node.y - radius, radius * 2, radius * 2);
                ctx.restore();
                
                // 테두리 링
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
                ctx.strokeStyle = '#fab1a0';
                ctx.lineWidth = 2 / globalScale;
                ctx.stroke();
            } else {
                // [기본 노드] 그라데이션 원형
                const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, radius);
                if (isCategory) {
                    gradient.addColorStop(0, '#74b9ff'); gradient.addColorStop(1, '#0984e3');
                } else if (isEntity) {
                    gradient.addColorStop(0, '#55efc4'); gradient.addColorStop(1, '#00b894'); // 민트/초록
                } else {
                    gradient.addColorStop(0, '#fab1a0'); gradient.addColorStop(1, '#e17055');
                }
                ctx.fillStyle = gradient;
                ctx.fill();
            }

            // 3. 텍스트 라벨 그리기
            const shouldShowText = isCategory || isEntity || isHover || (globalScale > 1.2);
            if (shouldShowText) {
                const label = node.name;
                const fontSize = (isHover ? 14 : (isEntity ? 10 : 12)) / globalScale; // 개체명은 글씨를 약간 작게
                ctx.font = `${(isCategory || isEntity) ? 'bold' : ''} ${fontSize}px Sans-Serif`;
                
                const textWidth = ctx.measureText(label).width;
                const bckgDimensions = [textWidth + fontSize, fontSize * 1.4];
                const textX = node.x; const textY = node.y + radius + fontSize/2 + 6;

                // 텍스트 배경 (가독성 확보)
                ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
                if (isEntity) ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'; // 개체명 배경은 살짝 투명하게

                ctx.fillRect(textX - bckgDimensions[0]/2, textY - bckgDimensions[1]/2, bckgDimensions[0], bckgDimensions[1]);

                ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                
                // 글씨 색상
                if (isCategory) ctx.fillStyle = '#74b9ff';
                else if (isEntity) ctx.fillStyle = '#55efc4';
                else ctx.fillStyle = '#fff';
                
                ctx.fillText(label, textX, textY);
            }
        })
        .onNodeHover(node => {
            elem.style.cursor = node ? 'pointer' : null;
            hoverNode = node || null;
        })
        .onNodeClick(node => {
            if (node.group === 1) {
                openModal(node); // 기사 노드 클릭 시 모달 오픈
            } else {
                // 카테고리/개체명 노드 클릭 시 해당 노드 중심으로 확대 이동
                Graph.centerAt(node.x, node.y, 1000);
                Graph.zoom(4, 2000);
            }
        })
        // --------------------------------------------------
        // [물리 엔진] 노드간 거리 최적화 (거미줄 방지)
        // --------------------------------------------------
        .d3Force('link', d3.forceLink().id(d => d.id).distance(link => {
            // 1. 벡터 유사도(Semantic) 거리
            // 서로 다른 카테고리 간의 연결이므로 거리를 멀리 둡니다. (기본 180)
            // 숫자를 키우면(예: 250) 빨간 점선이 팽팽해지며 두 노드가 더 멀어집니다.
            if (link.type === 'semantic') return 180; 

            // 2. 개체명(NER / shared_entity) 공유 거리
            // 같은 키워드를 공유하는 기사들이므로 비교적 가깝게 뭉치게 합니다. (기본 80)
            // 숫자를 줄이면(예: 50) 초록색 점선으로 연결된 기사들이 다닥다닥 붙습니다.
            if (link.type === 'entity' || link.type === 'shared_entity') return 80;    

            // 3. 카테고리 기본 거리
            // 중앙의 파란색 카테고리 노드와 기사들 사이의 거리입니다. (기본 100)
            return 100;                               
        }))
        .d3Force('charge', d3.forceManyBody().strength(-80))
        .d3Force('center', d3.forceCenter(window.innerWidth / 2, window.innerHeight / 2));

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

    // 리사이즈 이벤트
    window.addEventListener('resize', () => {
        const newWidth = window.innerWidth;
        const newHeight = window.innerHeight;

        Graph.width(newWidth);
        Graph.height(newHeight);
        Graph.d3Force('center', d3.forceCenter(newWidth / 2, newHeight / 2));   

        setTimeout(() => {
            Graph.zoomToFit(500, 50); 
        }, 100); 
    });
});