# backend/news/serializers.py

from rest_framework import serializers
from .models import Article, UserActionLog # UserActionLog import 필수

# (기존 ArticleSerializer가 있다면 그 아래에 추가)

class UserActionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActionLog
        fields = [
            'article_url', 
            'dwell_time', 
            'scroll_depth', 
            'click_count', 
            'is_valid_view',
            'region' # 호주/한국 구분용
        ]
        # user는 request에서 자동으로 가져오므로 fields에 넣지 않거나 read_only로 뺍니다.