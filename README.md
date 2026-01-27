# 🧠 News-Node: AI News Archiver & Knowledge Graph
> **AI 기반 뉴스 요약 및 개인화 지식 그래프 대시보드**

[![Stack](https://img.shields.io/badge/Tech-Django%20REST%20Framework-092E20?style=flat-square&logo=django)]()
[![Stack](https://img.shields.io/badge/Infra-AWS%20Lightsail-232F3E?style=flat-square&logo=amazon-aws)]()
[![Stack](https://img.shields.io/badge/Tool-Chrome%20Extension-4285F4?style=flat-square&logo=google-chrome)]()
[![Stack](https://img.shields.io/badge/AI-OpenAI%20GPT-412991?style=flat-square&logo=openai)]()

## 📖 Project Overview
인터넷상의 수많은 뉴스를 읽지만, 휘발되는 정보들을 체계적으로 관리하고 싶어 개발했습니다.
**Chrome Extension**을 통해 원클릭으로 뉴스를 요약/저장하고, **Web Dashboard**에서 나의 관심사 분석(페르소나)과 읽은 뉴스들의 연결 고리(지식 그래프)를 시각화하여 제공합니다.

- **개발 기간:** 202x.xx ~ 202x.xx (약 x주)
- **개발 인원:** 개인 프로젝트 (Full Stack)
- **배포 URL:** [크롬 웹 스토어 링크 (심사 중)] / [대시보드 데모 영상 링크]

## 🚀 Key Features
1.  **Chrome Extension 기반 접근성**
    - 브라우저 팝업에서 즉시 뉴스 본문 추출 및 AI 요약
    - OpenAI API를 활용한 자동 카테고리 분류 및 핵심 키워드 추출
2.  **개인화된 분석 대시보드 (Dashboard)**
    - **Weekly Rhythm:** 최근 7일간의 독서 패턴 시각화 (Chart.js)
    - **Persona System:** 읽은 기사 비중을 분석하여 '미래 설계자', '시장 분석가' 등 페르소나 부여
    - **Global Support:** 한국(KR) 및 호주(AU) 지역별 맞춤 페르소나/카테고리 매핑 지원
3.  **지식 그래프 (Knowledge Graph)**
    - 저장된 뉴스들 간의 연관성을 노드와 엣지로 시각화
    - D3.js (또는 사용한 라이브러리)를 활용한 인터랙티브 그래프 구현

## 🛠️ Tech Stack

### Frontend (Chrome Ext & Dashboard)
- **Core:** HTML5, CSS3, Vanilla JavaScript (ES6+)
- **Visualization:** Chart.js (통계), D3.js (지식 그래프)
- **Build:** Webpack (Extension 번들링)

### Backend (API Server)
- **Framework:** Django REST Framework (DRF)
- **Database:** PostgreSQL (pgvector를 활용한 벡터 유사도 검색 준비)
- **Authentication:** JWT / Session / Token Authentication
- **External API:** OpenAI API (GPT-3.5/4o), Naver Search API

### DevOps & Infrastructure
- **Server:** AWS Lightsail (Docker Environment)
- **Container:** Docker, Docker Compose
- **Web Server:** Nginx, Gunicorn
- **CI/CD:** Git, GitHub Actions (추후 도입 예정)

## 🏗️ System Architecture
*(여기에 아키텍처 다이어그램 이미지를 넣으면 베스트입니다. 아래 구조를 그림으로 그리면 됩니다)*
`User (Chrome Browser)` -> `Chrome Extension` -> `AWS Lightsail (Nginx -> Gunicorn -> Django)` -> `OpenAI API / DB`

## 🔥 Trouble Shooting (핵심!)
*기술 면접에서 가장 많이 물어보는 파트입니다. 우리가 해결한 문제들을 적으세요.*

### 1. Mixed Content (HTTPS/HTTP) 보안 이슈
- **문제:** 배포된 서버(AWS)가 HTTP 환경일 때, HTTPS 사이트(Chrome)에서 API 요청 시 차단되는 문제 발생.
- **해결:** Chrome Extension의 `manifest.json` 권한 설정 최적화 및 로컬 개발 시에는 localhost 루프백 주소를 명확히(`127.0.0.1`) 지정하여 CORS 및 보안 정책 우회. 추후 도메인 연결 및 SSL(LetsEncrypt) 적용으로 근본 해결 예정.

### 2. 다국어 페르소나 매핑 (Localization)
- **문제:** 한국 뉴스(Naver)와 해외 뉴스(NewsAPI)의 카테고리 체계가 달라 통계 분석이 어려움.
- **해결:** 백엔드에서 `region` 파라미터에 따른 **Cross Mapping Table**을 구축. 입력된 카테고리가 한글('경제')이든 영어('Business')든, 사용자의 설정 지역에 맞춰 일관된 페르소나(예: 'Market Analyst')로 변환하여 반환하는 로직 구현.

### 3. Docker 환경에서의 외부 API 통신 오류
- **문제:** 로컬 Docker 컨테이너 내부에서 OpenAI API 호출 시 DNS Resolution Error 발생.
- **해결:** `docker-compose` 설정에 구글 DNS(8.8.8.8)를 명시적으로 주입하여 컨테이너의 네트워크 고립 문제 해결.

## 💿 Installation & Run
```bash
# Clone the repository
git clone [https://github.com/your-username/news-node-knowledge.git](https://github.com/your-username/news-node-knowledge.git)

# Backend Setup (Docker)
cd backend
docker-compose -f docker-compose.prod.yml up -d --build

# Chrome Extension Load
1. Chrome 브라우저 주소창에 'chrome://extensions' 입력
2. '개발자 모드' 켜기
3. '압축해제된 확장 프로그램을 로드합니다' 클릭 -> /extension 폴더 선택
