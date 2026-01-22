from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.authtoken.models import Token

@xframe_options_exempt
def graph_page(request):
    return render(request, 'news/graph.html')

def dashboard_page(request):
    token_key = request.GET.get('token')
    print(f"🔍 대시보드 접근 - User: {request.user}, Token: {token_key}")

    if token_key:
        try:
            token = Token.objects.get(key=token_key)
            target_user = token.user
            
            if request.user.is_authenticated and request.user != target_user:
                print(f"👋 기존 유저({request.user}) 로그아웃 -> 새 유저({target_user})로 교체")
                logout(request)
            
            login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')
            print(f"✅ 토큰 유저 로그인 성공: {target_user.username}")
            return redirect('dashboard')
            
        except Token.DoesNotExist:
            print("❌ 유효하지 않은 토큰입니다.")
        except Exception as e:
            print(f"❌ 로그인 처리 중 에러: {e}")

    if not request.user.is_authenticated:
        return render(request, 'news/dashboard.html', {'error': '로그인이 필요합니다.'})

    return render(request, 'news/dashboard.html')