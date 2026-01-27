# 🧠 News-Node-Knowledge: AI News Archiver & Knowledge Graph
> **AI-Powered News Summarizer & Personalized Knowledge Graph Dashboard**

[![Stack](https://img.shields.io/badge/Tech-Django%20REST%20Framework-092E20?style=flat-square&logo=django)]()
[![Stack](https://img.shields.io/badge/Infra-AWS%20Lightsail-232F3E?style=flat-square&logo=amazon-aws)]()
[![Stack](https://img.shields.io/badge/Tool-Chrome%20Extension-4285F4?style=flat-square&logo=google-chrome)]()
[![Stack](https://img.shields.io/badge/AI-OpenAI%20GPT-412991?style=flat-square&logo=openai)]()

## 📖 Project Overview
Developed to systematically organize and visualize the vast amount of ephemeral news consumed daily on the web.
**News-Node** allows users to summarize and archive articles with a single click via a **Chrome Extension**, and visualize reading patterns and interests through a **Personalized Web Dashboard**.

- **Timeline:** 202x.xx - 202x.xx
- **Role:** Individual Project (Full Stack)
- **Deployment:** [Chrome Web Store Link (Under Review)] / [Dashboard Demo Video]

## 🚀 Key Features
1.  **Chrome Extension Accessibility**
    - Instant content extraction and AI-powered summarization via browser popup.
    - Automatic category classification and keyword extraction using OpenAI API.
2.  **Personalized Analytics Dashboard**
    - **Weekly Rhythm:** Visualization of reading habits over the last 7 days (Chart.js).
    - **Persona System:** Assigns user personas (e.g., "Future Architect", "Market Analyst") based on dominant reading categories.
    - **Global Support:** Supports multi-region (KR/AU) persona mapping and localization.
3.  **Knowledge Graph**
    - Interactive visualization of connections between archived articles using nodes and edges.
    - Implemented using D3.js (or relevant library) to discover hidden links in user knowledge.

## 🛠️ Tech Stack

### Frontend (Chrome Ext & Dashboard)
- **Core:** HTML5, CSS3, Vanilla JavaScript (ES6+)
- **Visualization:** Chart.js (Analytics), D3.js (Knowledge Graph)
- **Build:** Webpack (Extension Bundling)

### Backend (API Server)
- **Framework:** Django REST Framework (DRF)
- **Database:** PostgreSQL (Ready for vector similarity search with pgvector)
- **Authentication:** Token Authentication / Session Management
- **External API:** OpenAI API (GPT-3.5/4o), Naver Search API

### DevOps & Infrastructure
- **Server:** AWS Lightsail (Docker Environment)
- **Containerization:** Docker, Docker Compose
- **Web Server:** Nginx, Gunicorn
- **CI/CD:** Git, GitHub Actions (Planned)

## 🏗️ System Architecture
`User (Chrome Browser)` -> `Chrome Extension` -> `AWS Lightsail (Nginx -> Gunicorn -> Django)` -> `OpenAI API / DB`

## 🔥 Trouble Shooting
*Key technical challenges faced and resolved during development.*

### 1. Mixed Content & Security Policies
- **Issue:** API requests from the HTTPS-enforced Chrome Extension to the HTTP-based AWS server were blocked due to Mixed Content policies.
- **Solution:** Optimized `manifest.json` permissions and explicitly used the loopback address (`127.0.0.1`) during local development to bypass strict CORS/Security policies. Plan to implement full SSL (LetsEncrypt) and domain configuration for production.

### 2. Multi-language Persona Localization
- **Issue:** Discrepancies between Korean news categories (e.g., Naver) and Global news categories (e.g., NewsAPI) made unified statistical analysis difficult.
- **Solution:** Implemented a **Cross-Mapping Logic** on the backend. It dynamically maps input categories (whether Korean '경제' or English 'Business') to a unified Persona (e.g., 'Market Analyst') based on the user's `region` parameter.

### 3. Docker Container Network Resolution
- **Issue:** Encountered DNS resolution failures when calling the OpenAI API from within a local Docker container due to network isolation.
- **Solution:** Resolved by explicitly injecting Google DNS (`8.8.8.8`) into the `docker-compose` configuration to ensure stable external network connectivity.

## 💿 Installation & Run
```bash
# Clone the repository
git clone [https://github.com/your-username/news-node-knowledge.git](https://github.com/your-username/news-node-knowledge.git)

# Backend Setup (Docker)
cd backend
docker-compose -f docker-compose.prod.yml up -d --build

# Load Chrome Extension
1. Open 'chrome://extensions' in Chrome Browser.
2. Enable 'Developer mode'.
3. Click 'Load unpacked' -> Select the /extension folder.
