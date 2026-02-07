import threading
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model

from datetime import timedelta # [추가] 시간 계산용
from django.utils import timezone # [추가] Django 시간대 처리

from ..models import Article, UserActionLog
from ..recommendation import update_user_vector
from ..ai_service import get_embedding

User = get_user_model()

class LogCreateView(APIView):
    """
    [기능] 사용자 로그 수집 및 실시간 취향 반영
    [특징]
      1. 내부 기사(RSS 등): 기존 벡터 활용하여 즉시 반영
      2. 외부 기사(BBC 등): 백그라운드에서 즉석 벡터 생성 후 반영
      3. Non-blocking: 사용자 응답 지연 없음
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        user = request.user
        url = data.get('article_url')

        if not url: 
            return Response({"error": "URL missing"}, status=status.HTTP_400_BAD_REQUEST)
        
        already_saved = UserActionLog.objects.filter(
            user=user,
            article_url=url,
            action=UserActionLog.ActionType.SAVE,
            timestamp__gte=timezone.now() - timedelta(hours=1) # 1시간 이내
        ).exists()

        if already_saved:
            print(f"🛑 [LogAPI] 중복 방지: 이미 저장(SAVE)된 기사이므로 READ 로그 무시함.")
            return Response({"status": "skipped", "reason": "already_saved"}, status=status.HTTP_200_OK)

        try:
            # 1. Action 및 데이터 정제
            # 프론트에서 문자열로 올 수도 있으므로 안전하게 int 변환
            dwell_time = int(data.get('dwell_time', 0))
            scroll_depth = int(data.get('scroll_depth', 0))
            click_count = int(data.get('click_count', 0))
            
            action_type = UserActionLog.ActionType.CLICK
            if dwell_time >= 30:
                action_type = UserActionLog.ActionType.READ

            # 2. 내부 기사 매칭 확인
            matched_article = Article.objects.filter(url=url).first()

            # 3. 로그 저장 (UserActionLog)
            UserActionLog.objects.create(
                user=user,
                article=matched_article, # 내부 기사면 연결, 아니면 Null
                article_url=url,
                action=action_type,
                
                # 메타 데이터 매핑
                region=data.get('region', 'KR'),
                dwell_time=dwell_time,
                scroll_depth=scroll_depth,
                click_count=click_count,
                is_valid_view=data.get('is_valid_view', False),
                
                # 길이 제한 방어 (DB 에러 방지)
                title=data.get('title', '')[:500],
                description=data.get('description', ''), # TextField라 제한 덜함
                image_url=data.get('image_url', '')[:1000],
                category=data.get('category', 'General')[:100]
            )
            print(f"📝 [Log] Saved: {action_type} ({dwell_time}s) - {user.username}")

            # 4. 벡터 업데이트 (User Tower Logic)
            # 조건: '정독(READ)'인 경우에만 취향에 반영
            if action_type == UserActionLog.ActionType.READ:
                
                # Case A: 내부 기사 (이미 벡터가 있음 -> 빠름)
                if matched_article and matched_article.embedding_pytorch:
                    update_user_vector(user, matched_article.embedding_pytorch, weight=0.05)
                    print(f"📈 [Rec] Internal Article Reflected (Weight: 0.05)")
                
                # Case B: 외부 기사 (벡터 없음 -> 만듦 -> 반영)
                else:
                    # 제목이나 설명이 너무 짧으면 벡터화 의미 없음
                    title = data.get('title', '')
                    desc = data.get('description', '')
                    
                    if len(title) > 2 or len(desc) > 10:
                        thread = threading.Thread(
                            target=process_external_article_vector, 
                            args=(user.id, title, desc)
                        )
                        thread.start()
                    else:
                        print("⚠️ [Rec] Skip external: Content too short")

            return Response({"status": "success"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"🔥 [Log Error] {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------
# 외부 기사 처리용 백그라운드 함수
# ---------------------------------------------------------
def process_external_article_vector(user_id, title, description):
    """
    외부 기사의 제목+설명을 이용해 즉석에서 벡터를 만들고 유저 취향에 반영함
    """
    try:
        # 스레드는 별도 컨텍스트이므로 User를 다시 가져오는 게 안전함
        user = User.objects.get(id=user_id)
        
        # NoneType 방지 처리
        title = title if title else ""
        description = description if description else ""
        
        text_to_embed = f"{title}. {description}"
        
        print(f"🔄 [External] Generating Vector... ({title[:20]}...)")

        # CPU 연산 (약 0.2~0.5초)
        vectors = get_embedding(text_to_embed, use_openai=False, use_pytorch=True)
        
        if vectors.get('pytorch'):
            # 외부 기사도 정독했으니 가중치 5% 반영
            update_user_vector(user, vectors['pytorch'], weight=0.05)
            print(f"📈 [Rec] External Article Reflected! (User: {user.username})")
            
    except Exception as e:
        print(f"🔥 [External Rec Error] {e}")