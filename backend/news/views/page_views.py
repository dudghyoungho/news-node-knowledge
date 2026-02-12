from django.shortcuts import render, redirect, resolve_url
from django.contrib.auth import login, logout, get_user_model
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.authtoken.models import Token

User = get_user_model()

@xframe_options_exempt
def graph_page(request):
    return render(request, 'news/graph.html')

def dashboard_page(request):
    # 1. URL 파라미터에서 정보 추출
    token_key = request.GET.get('token')
    region = request.GET.get('region', 'KR') 
    
    # 2. 토큰이 주소창에 포함된 경우 (최초 데모 접속 시)
    if token_key:
        try:
            token = Token.objects.get(key=token_key)
            target_user = token.user
            
            # 현재 로그인된 사람이 다른 유저라면 로그아웃
            if request.user.is_authenticated and request.user != target_user:
                logout(request)
            
            # [핵심] 세션 기반 로그인 수행
            login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')
            
            # [중요] 처음 방문하는 사람을 위해 세션을 강제로 즉시 저장
            # 리다이렉트 시 세션 쿠키가 누락되는 것을 방지합니다.
            if not request.session.session_key:
                request.session.create()
            request.session.save()
            
            # 토큰 파라미터를 제거하여 깔끔한 URL로 이동 (보안 및 UX)
            redirect_url = resolve_url('dashboard')
            return redirect(f"{redirect_url}?region={region}")
            
        except Token.DoesNotExist:
            print(f"❌ 유효하지 않은 토큰 접근: {token_key}")
        except Exception as e:
            print(f"❌ 로그인 처리 중 서버 에러: {e}")

    # 3. 비로그인 접근 처리 (세션 로그인에 실패했거나, 그냥 접속한 경우)
    if not request.user.is_authenticated:
        # [데모 배려] 만약 데모 버튼을 안 누르고 직접 왔다면, 
        # 로그인 페이지 대신 랜딩 페이지(또는 데모 안내)로 보내는 것이 사용자 경험에 좋습니다.
        return redirect('/') 

    # 4. 최종 렌더링 (인증 완료된 상태)
    # 이제 request.user는 'demo_guest'가 되어 있습니다.
    return render(request, 'news/dashboard.html', {'region': region})

def privacy_policy(request):
    return render(request, 'news/privacy.html')