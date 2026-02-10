from .auth_views import google_login
from .article_views import summarize, save_article
from .data_views import get_knowledge_graph, get_reading_statistics
from .page_views import dashboard_page, graph_page, privacy_policy
from .stats_views import get_dashboard_stats
from .rag_views import context_recommendation, review_recommendation, external_recommendation, article_bridge_view
from .log_views import LogCreateView