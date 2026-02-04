# backend/news/views/log_views.py

from rest_framework import generics, permissions
from ..models import UserActionLog
from ..serializers import UserActionLogSerializer

class LogCreateView(generics.CreateAPIView):
    """
    [기능] 사용자 행동 로그(UserActionLog) 생성
    [Method] POST
    [Access] 로그인한 유저만 가능 (Header에 Authorization: Bearer <Token> 필수)
    """
    queryset = UserActionLog.objects.all()
    serializer_class = UserActionLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        데이터 저장 시점(save)에 호출됩니다.
        Request를 보낸 유저(self.request.user) 정보를 
        모델의 user 필드에 강제로 주입합니다.
        """
        serializer.save(user=self.request.user)