from .models import Article

RSS_FEEDS = [
    # ==============================================================================
    # 🇦🇺 [AUSTRALIA] User Selected Feeds
    # ==============================================================================
    {
        'name': 'Business News AU',
        'url': 'https://www.businessnews.com.au/rssfeed/latest.rss',
        'region': Article.Region.AU,
        'category_base': 'Economy' # 비즈니스 전문지 -> Economy
    },
    {
        'name': 'News.com.au Tech',
        'url': 'https://www.news.com.au/content-feeds/latest-news-technology/',
        'region': Article.Region.AU,
        'category_base': 'Technology' # 테크 섹션 -> Technology
    },
    {
        'name': 'News.com.au Finance',
        'url': 'https://www.news.com.au/content-feeds/latest-news-finance/',
        'region': Article.Region.AU,
        'category_base': 'Economy' # 금융 섹션 -> Economy
    },
    {
        'name': 'The Conversation AU (Biz)',
        'url': 'https://theconversation.com/au/business/articles.atom',
        'region': Article.Region.AU,
        'category_base': 'Economy' # 전문가 기고/분석 -> Economy (Insight)
    },
    # [Local] 멜버른 로컬 뉴스는 'General/Society'로 분류
    {
        'name': 'ABC News AU (Just In)',
        'url': 'https://www.abc.net.au/news/feed/51120/rss.xml',
        'region': Article.Region.AU,
        'category_base': 'General' 
    },

    {
        'name': 'SBS News AU ',
        'url': 'https://www.sbs.com.au/news/topic/australia/feed',
        'region': Article.Region.AU,
        'category_base': 'General' 
    },

    {
        'name': 'The Guardians News AU ',
        'url': 'https://www.theguardian.com/au/rss',
        'region': Article.Region.AU,
        'category_base': 'General' 
    },
    {
        'name': 'ABC Sports ',
        'url': 'https://www.abc.net.au/news/feed/45924/rss.xml',
        'region': Article.Region.AU,
        'category_base': 'Sports' 
    },

    # ==============================================================================
    # 🇰🇷 [KOREA] Recommended Elite Feeds
    # ==============================================================================
    
    # 1. [Economy] 매일경제 (기업/증권 섹션 분리 수집)
    {
        'name': 'MK Enterprise (기업)',
        'url': 'https://www.mk.co.kr/rss/50100032/',
        'region': Article.Region.KR,
        'category_base': 'Economy'
    },
    {
        'name': 'MK Stock (증권)',
        'url': 'https://www.mk.co.kr/rss/50200011/',
        'region': Article.Region.KR,
        'category_base': 'Economy'
    },

    # 2. [Tech] 전자신문 & GeekNews
    {
        'name': 'ETNews SW (소프트웨어)',
        'url': 'http://rss.etnews.com/04.xml',
        'region': Article.Region.KR,
        'category_base': 'Technology'
    },
    {
        'name': 'GeekNews (Dev Trend)',
        'url': 'http://feeds.feedburner.com/geeknews-feed',
        'region': Article.Region.KR,
        'category_base': 'Technology'
    },

    # 3. [Society/Trend] 노컷뉴스 & SBS (종합)
    {
        'name': 'Nocut News Society',
        'url': 'https://rss.nocutnews.co.kr/news/society.xml',
        'region': Article.Region.KR,
        'category_base': 'Society'
    },
    {
        'name': 'SBS Life & Culture',
        'url': 'https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=08&plink=RSSREADER',
        'region': Article.Region.KR,
        'category_base': 'Life' # 라이프스타일/문화
    },

    #스포츠동아
    {
        'name': '스포츠동아',
        'url': 'https://rss.donga.com/sports.xml',
        'region': Article.Region.KR,
        'category_base': 'Sports' # 라이프스타일/문화
    },
]   