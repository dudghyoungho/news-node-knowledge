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

    def create(self, request, *args, **kwargs):
        print(f"\n>>> [DEBUG] Incoming Log Data: {request.data}")
        # title이나 category가 들어있는지 터미널에서 확인하세요!
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)