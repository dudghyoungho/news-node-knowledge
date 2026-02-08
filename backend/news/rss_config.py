# backend/news/rss_config.py

from .models import Article

RSS_FEEDS = [
    # ==============================================================================
    # 🇦🇺 [AUSTRALIA] Major News & Insight
    # ==============================================================================
    {
        'name': 'News.com.au Tech',
        'url': 'https://www.news.com.au/content-feeds/latest-news-technology/',
        'region': Article.Region.AU,
        'category_base': 'Technology'
    },
    {
        'name': 'News.com.au Finance',
        'url': 'https://www.news.com.au/content-feeds/latest-news-finance/',
        'region': Article.Region.AU,
        'category_base': 'Economy'
    },
    {
        'name': 'The Conversation AU (Biz)',
        'url': 'https://theconversation.com/au/business/articles.atom',
        'region': Article.Region.AU,
        'category_base': 'Economy' # 전문가 기고/분석 -> Insight 확률 높음
    },
    {
        'name': 'ABC News AU (Just In)',
        'url': 'https://www.abc.net.au/news/feed/51120/rss.xml',
        'region': Article.Region.AU,
        'category_base': 'General'
    },
    {
        'name': 'SBS News AU',
        'url': 'https://www.sbs.com.au/news/topic/australia/feed',
        'region': Article.Region.AU,
        'category_base': 'General'
    },
    {
        'name': 'The Guardian AU',
        'url': 'https://www.theguardian.com/au/rss',
        'region': Article.Region.AU,
        'category_base': 'General'
    },
    {
        'name': 'ABC Sports',
        'url': 'https://www.abc.net.au/news/feed/45924/rss.xml',
        'region': Article.Region.AU,
        'category_base': 'Sports'
    },

    # ==============================================================================
    # 🇰🇷 [KOREA] Economy & Society
    # ==============================================================================
    {
        'name': 'MK Enterprise (매경 기업)',
        'url': 'https://www.mk.co.kr/rss/50100032/',
        'region': Article.Region.KR,
        'category_base': 'Economy'
    },
    {
        'name': 'MK Stock (매경 증권)',
        'url': 'https://www.mk.co.kr/rss/50200011/',
        'region': Article.Region.KR,
        'category_base': 'Economy'
    },
    {
        'name': 'Nocut News (Society)',
        'url': 'https://rss.nocutnews.co.kr/news/society.xml',
        'region': Article.Region.KR,
        'category_base': 'Society'
    },
    {
        'name': 'SBS Life & Culture',
        'url': 'https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=08&plink=RSSREADER',
        'region': Article.Region.KR,
        'category_base': 'Life'
    },
    {
        'name': 'Sports Donga',
        'url': 'https://rss.donga.com/sports.xml',
        'region': Article.Region.KR,
        'category_base': 'Sports'
    },

    # ==============================================================================
    # 💻 [Tech & Dev] Engineering Blogs & Aggregators
    # ==============================================================================
    {
        'name': 'Hacker News',
        'url': 'http://news.ycombinator.com/rss',
        'region': Article.Region.AU, # 영어권 Tech (Global)
        'category_base': 'Technology'
    },
    {
        'name': 'George Hotz Blog',
        'url': 'https://geohot.github.io/blog/feed.xml',
        'region': Article.Region.AU, # 영어권 Insight
        'category_base': 'Technology' # Insight 성향 강함
    },
    {
        'name': 'ETNews SW',
        'url': 'http://rss.etnews.com/04.xml',
        'region': Article.Region.KR,
        'category_base': 'Technology'
    },
    {
        'name': 'GeekNews (Aggregator)',
        'url': 'http://feeds.feedburner.com/geeknews-feed',
        'region': Article.Region.KR,
        'category_base': 'Technology'
    },
    {
        'name': 'Woowa Bros Tech Blog',
        'url': 'https://techblog.woowahan.com/feed/',
        'region': Article.Region.KR,
        'category_base': 'Technology' # 기업 기술 블로그 -> Insight/Tutorial
    },

    # ==============================================================================
    # 🏛️ [Policy & Insight] Government & Deep Dive
    # ==============================================================================
    {
        'name': 'Korea Policy (News)',
        'url': 'https://www.korea.kr/rss/policy.xml',
        'region': Article.Region.KR,
        'category_base': 'Society' # 정책 뉴스 -> Fact 위주
    },
    {
        'name': 'Korea Policy (Insight)',
        'url': 'https://www.korea.kr/rss/insight.xml',
        'region': Article.Region.KR,
        'category_base': 'Society' # 정책 인사이트 -> Insight/Opinion
    },
    {
        'name': 'Korea Policy (Column)',
        'url': 'https://www.korea.kr/rss/column.xml',
        'region': Article.Region.KR,
        'category_base': 'Society' # 전문가 칼럼 -> Opinion
    },

    # ==============================================================================
    # 🔍 [Google News] Keyword-based Feeds (Decoded via googlenewsdecoder)
    # ==============================================================================
    {
        'name': 'Google News - Analysis (는가?)',
        # "는가" 검색: 의문형 제목을 가진 기사(분석, 전망, 의혹)를 타겟팅
        'url': 'https://news.google.com/rss/search?q=%EB%8A%94%EA%B0%80&hl=ko&gl=KR&ceid=KR%3Ako',
        'region': Article.Region.KR,
        'category_base': 'General' # 주제가 다양하므로 General -> AI가 재분류
    },
]