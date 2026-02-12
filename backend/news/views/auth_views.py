import requests
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt # [필수] CSRF 면제
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status

from django.shortcuts import render, redirect
from django.contrib.auth import login

User = get_user_model()

# =============================================================
# 1. 기존 구글 로그인 (유지)
# =============================================================
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def google_login(request):
    """
    구글 액세스 토큰을 받아 유저를 생성/조회하고 DRF 토큰을 발급합니다.
    """
    access_token = request.data.get('access_token')
    
    verify_url = f"https://www.googleapis.com/oauth2/v3/userinfo?access_token={access_token}"
    response = requests.get(verify_url)
    
    if response.status_code != 200:
        return Response({'error': '유효하지 않은 구글 토큰입니다.'}, status=status.HTTP_400_BAD_REQUEST)
    
    user_info = response.json()
    email = user_info.get('email')
    name = user_info.get('name', '')
    
    if not email:
        return Response({'error': '이메일 정보를 가져올 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    user, created = User.objects.get_or_create(
        username=email, 
        defaults={'first_name': name, 'email': email}
    )
    
    token, _ = Token.objects.get_or_create(user=user)
    
    return Response({
        'token': token.key,
        'username': user.username,
        'message': '로그인 성공'
    })

# =============================================================
# 2. [NEW] 데모 유저 로그인 (추가됨)
# =============================================================

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])     # 1. 누구나 접근 가능
@authentication_classes([])         # 2. 세션/토큰 인증 과정 생략 (CSRF 유발 방지)
def demo_login(request):
    """
    크롬 익스텐션용 데모 로그인 API
    호출 시 'demo_guest' 계정의 토큰을 반환합니다.
    """
    username = 'demo_guest'

    # 1. 데모 유저 확인 (없으면 생성, 있으면 가져오기)
    user, created = User.objects.get_or_create(username=username)
    
    if created:
        # 처음 생성될 때만 비밀번호 설정 (사실 API로만 로그인하므로 몰라도 됨)
        user.set_password('demo_password_1234')
        user.email = 'demo@guest.com'
        user.save()

    # 2. 토큰 가져오기 (없으면 생성)
    token, _ = Token.objects.get_or_create(user=user)

    # 3. 토큰과 유저명 반환
    return Response({
        'token': token.key,       # 이 값을 익스텐션이 저장해서 씁니다.
        'username': user.username,
        'message': '데모 계정으로 로그인되었습니다.'
    }, status=status.HTTP_200_OK)