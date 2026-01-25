from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.authtoken.models import Token

@xframe_options_exempt
def graph_page(request):
    return render(request, 'news/graph.html')

def dashboard_page(request):
    token_key = request.GET.get('token')
    
    # 디버깅용 로그 (서버 로그에서 확인 가능)
    if token_key:
        print(f"🔍 대시보드 접근 - Token: {token_key}")
        try:
            token = Token.objects.get(key=token_key)
            target_user = token.user
            
            # [중요] 이미 다른 아이디로 로그인된 경우 교체
            if request.user.is_authenticated and request.user != target_user:
                print(f"👋 유저 교체: {request.user} -> {target_user}")
                logout(request)
            
            # 로그인 수행 (Backend 명시)
            login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')
            print(f"✅ 로그인 성공: {target_user.username}")
            
            # 토큰을 URL에서 지우기 위해 리다이렉트
            return redirect('dashboard')
            
        except Token.DoesNotExist:
            print("❌ 유효하지 않은 토큰")
        except Exception as e:
            print(f"❌ 로그인 에러: {e}")

    # [수정] 비로그인 상태면 로그인 페이지로 '강제 이동' (401 에러 방지)
    if not request.user.is_authenticated:
        return redirect('/admin/login/?next=/dashboard/')

    return render(request, 'news/dashboard.html')