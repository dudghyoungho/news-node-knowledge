from django.shortcuts import render, redirect, resolve_url
from django.contrib.auth import login, logout
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.authtoken.models import Token

@xframe_options_exempt
def graph_page(request):
    return render(request, 'news/graph.html')

def dashboard_page(request):
    token_key = request.GET.get('token')
    # [수정] URL에서 region 파라미터 받기 (기본값 KR)
    region = request.GET.get('region', 'KR') 
    
    # 1. 토큰 기반 로그인 처리
    if token_key:
        print(f"🔍 대시보드 접근 - Token: {token_key}, Region: {region}")
        try:
            token = Token.objects.get(key=token_key)
            target_user = token.user
            
            if request.user.is_authenticated and request.user != target_user:
                print(f"👋 유저 교체: {request.user} -> {target_user}")
                logout(request)
            
            login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')
            print(f"✅ 로그인 성공: {target_user.username}")
            
            # [중요] 토큰만 지우고, region 정보는 유지한 채 리다이렉트
            # redirect('dashboard')만 하면 파라미터가 다 날아감
            redirect_url = resolve_url('dashboard')
            return redirect(f"{redirect_url}?region={region}")
            
        except Token.DoesNotExist:
            print("❌ 유효하지 않은 토큰")
        except Exception as e:
            print(f"❌ 로그인 에러: {e}")

    # 2. 비로그인 접근 차단
    if not request.user.is_authenticated:
        # 로그인 후 다시 돌아올 때도 region 유지
        return redirect(f'/admin/login/?next=/dashboard/?region={region}')

    # 3. 템플릿 렌더링 (region 정보를 컨텍스트로 전달)
    return render(request, 'news/dashboard.html', {'region': region})