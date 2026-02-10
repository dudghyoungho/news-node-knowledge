import threading
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone

# 모델 및 로직 임포트
from ..models import Article, UserActionLog
from ..recommendation import update_user_vector
from ..ai_service import get_embedding

User = get_user_model()

class LogCreateView(APIView):
    """
    [기능] 사용자 로그 수집 및 실시간 취향 반영
    [로직 변경]
      - 999초(요약): READ + 가중치 0.5 (매우 높음)
      - 15초 초과: READ + 가중치 0.05 (보통)
      - 7~15초: CLICK + 가중치 0.0 (기록만 하고 추천엔 반영 안 함)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        user = request.user
        url = data.get('article_url')

        if not url: 
            return Response({"error": "URL missing"}, status=status.HTTP_400_BAD_REQUEST)
        
        # [중복 방지] 1시간 이내에 동일한 '저장(SAVE)' 기록이 있으면 READ 로그 무시
        # (저장이 더 강력한 시그널이므로 덮어쓰지 않기 위함)
        already_saved = UserActionLog.objects.filter(
            user=user,
            article_url=url,
            action=UserActionLog.ActionType.SAVE,
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).exists()

        if already_saved:
            print(f"🛑 [LogAPI] 중복 방지: 이미 저장(SAVE)된 기사이므로 로그 무시함.")
            return Response({"status": "skipped", "reason": "already_saved"}, status=status.HTTP_200_OK)

        try:
            # 1. 데이터 정제
            dwell_time = int(data.get('dwell_time', 0))
            scroll_depth = int(data.get('scroll_depth', 0))
            click_count = int(data.get('click_count', 0))
            
            # =========================================================
            # [핵심 로직 수정] 시간별 Action Type 및 가중치 결정
            # =========================================================
            action_type = UserActionLog.ActionType.CLICK # 기본값
            weight = 0.0 # 기본 가중치 (반영 안함)

            if dwell_time == 999:
                # [Case 1] 요약 버튼 클릭 -> 매우 강력한 관심
                action_type = UserActionLog.ActionType.READ
                weight = 0.5  # 가중치 매우 높게 부여
                print(f"🔥 [Log] 요약(Summary) 감지! (Weight: 0.5) - {user.username}")

            elif dwell_time > 15:
                # [Case 2] 15초 초과 -> 정독
                action_type = UserActionLog.ActionType.READ
                weight = 0.05 # 일반적인 정독 가중치
                print(f"📖 [Log] 정독(Read) 감지 ({dwell_time}s)")

            else:
                # [Case 3] 7~15초 -> 단순 클릭 (찍먹)
                # 프론트에서 7초 미만은 아예 안 보내므로, 여기 오는 건 7~15초 사이임
                action_type = UserActionLog.ActionType.CLICK
                weight = 0.0  # 클릭은 노이즈가 많으므로 벡터 업데이트 안 함 (기록만 남김)
                print(f"🖱️ [Log] 단순 클릭(Click) ({dwell_time}s)")

            # 2. 내부 기사 매칭 확인
            matched_article = Article.objects.filter(url=url).first()

            # 3. 로그 저장 (UserActionLog) - 기록은 무조건 남김
            UserActionLog.objects.create(
                user=user,
                article=matched_article, # 내부 기사면 연결
                article_url=url,
                action=action_type,
                
                # 메타 데이터 매핑
                region=data.get('region', 'KR'),
                dwell_time=dwell_time,
                scroll_depth=scroll_depth,
                click_count=click_count,
                # 프론트에서 주는 값보다 백엔드 시간 기준이 더 정확하므로 백엔드 판단 우선
                is_valid_view=(weight > 0), 
                
                title=data.get('title', '')[:500],
                description=data.get('description', ''), 
                image_url=data.get('image_url', '')[:1000],
                category=data.get('category', 'General')[:100]
            )

            # 4. 벡터 업데이트 (User Tower Logic)
            # 가중치가 0보다 클 때만 취향에 반영 (단순 클릭 제외)
            if weight > 0:
                # Case A: 내부 기사 (이미 벡터가 있음 -> 즉시 반영)
                if matched_article and matched_article.embedding_pytorch:
                    update_user_vector(user, matched_article.embedding_pytorch, weight=weight)
                    print(f"📈 [Rec] Internal Article Reflected (Weight: {weight})")
                
                # Case B: 외부 기사 (벡터 없음 -> 백그라운드 생성 -> 반영)
                else:
                    title_txt = data.get('title', '')
                    desc_txt = data.get('description', '')
                    
                    # 제목/내용이 너무 짧으면 벡터화 가치가 없음
                    if len(title_txt) > 2 or len(desc_txt) > 10:
                        thread = threading.Thread(
                            target=process_external_article_vector, 
                            args=(user.id, title_txt, desc_txt, weight) # weight 전달 추가
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
def process_external_article_vector(user_id, title, description, weight):
    """
    외부 기사의 제목+설명을 이용해 즉석에서 벡터를 만들고 유저 취향에 반영함
    """
    try:
        user = User.objects.get(id=user_id)
        
        title = title if title else ""
        description = description if description else ""
        text_to_embed = f"{title}. {description}"
        
        # print(f"🔄 [External] Generating Vector... (Weight: {weight})")

        # CPU 연산 (약 0.2~0.5초)
        vectors = get_embedding(text_to_embed, use_openai=False, use_pytorch=True)
        
        if vectors.get('pytorch'):
            # 전달받은 가중치(weight) 적용
            update_user_vector(user, vectors['pytorch'], weight=weight)
            print(f"📈 [Rec] External Article Reflected! (User: {user.username}, Weight: {weight})")
            
    except Exception as e:
        print(f"🔥 [External Rec Error] {e}")