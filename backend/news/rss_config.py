# backend/news/rss_config.py
from .models import Article

RSS_FEEDS = [
    # --- 1. Base News (기본: 호주 & 한국) ---
    {
        'name': 'Guardian Top Stories',
        'url': 'https://www.theguardian.com/au/rss',
        'region': Article.Region.AU,
        'category_base': 'General'
    },
    {
        'name': 'News.com.au National',
        'url': 'https://www.news.com.au/content-feeds/latest-news-national/',
        'region': Article.Region.AU,
        'category_base': 'Society'
    },
    {
        'name': 'Naver Main News',
        'url': 'http://fs.news.naver.com/news/main.rss',
        'region': Article.Region.KR,
        'category_base': 'General'
    },

    # --- 2. Tech & Dev (개발자 취향 저격 - Google & Hacker News) ---
    {
        'name': 'Hacker News (Top)',
        'url': 'https://news.ycombinator.com/rss',
        'region': Article.Region.AU, # 영어권
        'category_base': 'Technology'
    },
    {
        'name': 'Google News - AI',
        # "Artificial Intelligence", 지난 1일, 호주 에디션
        'url': 'https://news.google.com/rss/search?q=Artificial+Intelligence+when:1d&ceid=AU:en&hl=en-AU&gl=AU',
        'region': Article.Region.AU,
        'category_base': 'Technology'
    },
    {
        'name': 'Google News - Software',
        'url': 'https://news.google.com/rss/search?q=Software+Engineering+when:1d&ceid=AU:en&hl=en-AU&gl=AU',
        'region': Article.Region.AU,
        'category_base': 'Technology'
    },

    # --- 3. Local Info (지역 정보) ---
    {
        'name': 'Google News - Melbourne',
        'url': 'https://news.google.com/rss/search?q=Melbourne+Australia+when:1d&ceid=AU:en&hl=en-AU&gl=AU',
        'region': Article.Region.AU,
        'category_base': 'Society'
    }
]