<div align="center">

  <a href="https://github.com/your-username/news-node-knowledge">
    <img src="https://img.shields.io/badge/release-v1.1.2-blue.svg?style=for-the-badge" alt="version" />
  </a>
  <img src="https://img.shields.io/badge/django-092E20?style=for-the-badge&logo=django&logoColor=white" alt="django" />
  <img src="https://img.shields.io/badge/python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="docker" />
  <img src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white" alt="aws" />
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="postgres" />
  <img src="https://img.shields.io/badge/Chrome_Web_Store-4285F4?style=for-the-badge&logo=google-chrome&logoColor=white" alt="chrome-extension" />

  <br />
  <br />

  <img src="./extension/icon128.png" alt="Logo" width="100" height="100">

  <h3 align="center">News Node Knowledge</h3>

  <p align="center">
    <b>AI-Powered News Archiver & Knowledge Graph Generator</b>
    <br />
    <br />
    <a href="https://chrome.google.com/webstore/detail/YOUR_EXTENSION_ID"><strong>Download Extension »</strong></a>
    <br />
    <br />
    <a href="#demo">View Demo</a>
    ·
    <a href="#issues">Report Bug</a>
    ·
    <a href="#contact">Request Feature</a>
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#architecture">System Architecture</a></li>
    <li><a href="#built-with">Built With</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#project-structure">Project Structure</a></li>
    <li><a href="#features">Key Features</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

---

## 📖 About The Project

> **"Stop drowning in information. Start building your knowledge."**

**News Node Knowledge** is a comprehensive platform designed to revolutionize how we consume digital news. By combining a browser-based **Chrome Extension** with a robust **Django backend**, it bridges the gap between passive reading and active knowledge management.

Instead of fleeting news consumption, this tool allows users to:
1.  **Summarize** complex articles instantly using Generative AI (OpenAI GPT).
2.  **Archive** content securely into a personal database.
3.  **Visualize** the flow of events using a Knowledge Graph.
4.  **Search** through archived news using semantic understanding (Vector Search).

### 📸 Demo

| AI Summarization (Popup) | Dashboard & Graph |
|:-----------------------:|:-----------------:|
| <img width="1280" height="800" alt="1" src="https://github.com/user-attachments/assets/e43615f8-0b3d-4c46-b0be-43afa6332a9f" />
 | <img width="1280" height="800" alt="image" src="https://github.com/user-attachments/assets/4269ab0f-d951-498c-9cd0-2a53556c0a11" />
 |

---

## 🏗 System Architecture

The system utilizes a microservices-like architecture containerized with Docker.

```mermaid
graph LR
    User((User)) -->|Chrome Ext| Nginx[Nginx Proxy]
    Nginx -->|HTTPS / WSS| Django[Django Backend]
    Django -->|Auth| Google[Google OAuth2]
    Django -->|Summarize| OpenAI[OpenAI API]
    Django -->|Store & Vectorize| DB[(PostgreSQL + pgvector)]
```

* **Frontend**: A Manifest V3 Chrome Extension that interacts with the current tab.
* **Backend**: Django REST Framework serving APIs for auth, summarization, and data retrieval.
* **Database**: PostgreSQL with `pgvector` extension for storing vector embeddings of news articles.
* **Infrastructure**: Hosted on AWS Lightsail, orchestrated via Docker Compose with Nginx as a reverse proxy/SSL terminator.

---

## 🛠 Built With

### Frontend (Chrome Extension)
* ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black) **ES6+**
* ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat-square&logo=html5&logoColor=white) **HTML5 & CSS3**
* **Manifest V3**
* **Google Identity Services (OAuth2)**

### Backend (Server)
* ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) **Python 3.11**
* ![Django](https://img.shields.io/badge/Django-092E20?style=flat-square&logo=django&logoColor=white) **Django REST Framework**
* ![Gunicorn](https://img.shields.io/badge/Gunicorn-499848?style=flat-square&logo=gunicorn&logoColor=white) **Gunicorn**

### Database & AI
* ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat-square&logo=postgresql&logoColor=white) **PostgreSQL**
* **pgvector** (Vector Similarity Search)
* ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white) **GPT-4o-mini**

### Infrastructure
* ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) **Docker & Docker Compose**
* ![Nginx](https://img.shields.io/badge/Nginx-009639?style=flat-square&logo=nginx&logoColor=white) **Nginx Proxy Manager**
* ![AWS](https://img.shields.io/badge/AWS-232F3E?style=flat-square&logo=amazon-aws&logoColor=white) **AWS Lightsail**

---

## 🚀 Getting Started

To set up a local development environment, follow these steps.

### Prerequisites
* Docker & Docker Compose installed
* Git installed
* OpenAI API Key

### Installation

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/your-username/news-node-knowledge.git](https://github.com/your-username/news-node-knowledge.git)
    cd news-node-knowledge
    ```

2.  **Configure Environment Variables**
    Create a `.env` file in the root directory based on the example.
    ```bash
    cp .env.example .env
    ```
    Then, edit the `.env` file with your credentials:
    ```ini
    # .env configuration
    DEBUG=1
    SECRET_KEY=your_secret_key_here
    ALLOWED_HOSTS=localhost 127.0.0.1
    
    DB_NAME=news_db
    DB_USER=postgres
    DB_PASSWORD=your_db_password
    DB_HOST=db
    
    OPENAI_API_KEY=sk-proj-your-openai-key
    ```

3.  **Run with Docker**
    ```bash
    docker-compose up -d --build
    ```

4.  **Load Extension (Developer Mode)**
    * Open Chrome and navigate to `chrome://extensions`.
    * Toggle **Developer mode** (top right corner).
    * Click **Load unpacked**.
    * Select the `extension` folder from this repository.

---

## 📂 Project Structure

```text
.
├── backend/                # Django Backend Application
│   ├── config/             # Project Settings (Settings, URLs)
│   ├── news/               # News App (Models, Views, Serializers)
│   ├── manage.py
│   └── Dockerfile
├── extension/              # Chrome Extension Source
│   ├── manifest.json       # Manifest V3 Configuration
│   ├── popup.html          # Extension UI
│   ├── popup.js            # Frontend Logic
│   └── icons/
├── nginx/                  # Nginx Configuration
├── docker-compose.prod.yml # Production Orchestration
├── requirements.txt        # Python Dependencies
└── README.md
```

---

## 🔥 Key Features

- [x] **Secure Authentication**: Seamless login via Google OAuth2 with secure token management.
- [x] **AI Summarization**: Extracts key points, keywords, and sentiment from any news article page.
- [x] **Knowledge Graph**: Visualizes relationships between archived news topics.
- [x] **Semantic Search**: Utilizes `pgvector` to find news articles based on context, not just keywords.
- [x] **Responsive Dashboard**: A dedicated web interface to manage and review archived news.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 📧 Contact

**Project Lead** - [Your Name]
<br />
**Email** - [Your Email]
<br />
**Project Link** - [https://github.com/your-username/news-node-knowledge](https://github.com/your-username/news-node-knowledge)

<p align="right">(<a href="#readme-top">back to top</a>)</p>
