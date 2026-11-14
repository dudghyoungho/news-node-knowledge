import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt # [필수] CSRF 면제
from rest_framework.decorators import api_view, permission_classes, authentication_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status

from django.shortcuts import render, redirect
from django.contrib.auth import login

from ..access import DEMO_USERNAME
from ..throttles import AuthIPThrottle

User = get_user_model()
logger = logging.getLogger(__name__)

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# =============================================================
# 1. 기존 구글 로그인 (유지)
# =============================================================
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([AuthIPThrottle])
def google_login(request):
    """
    구글 액세스 토큰을 받아 유저를 생성/조회하고 DRF 토큰을 발급합니다.
    """
    access_token = request.data.get('access_token')
    if not access_token or not isinstance(access_token, str):
        return Response({'error': '구글 토큰이 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # 1) 토큰이 "우리 확장"용으로 발급됐는지 확인 (다른 앱의 토큰으로 로그인하는 것 차단)
    try:
        info_res = requests.get(GOOGLE_TOKENINFO_URL, params={'access_token': access_token}, timeout=10)
    except requests.RequestException:
        return Response({'error': '구글 인증 서버에 연결할 수 없습니다.'}, status=status.HTTP_502_BAD_GATEWAY)

    if info_res.status_code != 200:
        return Response({'error': '유효하지 않은 구글 토큰입니다.'}, status=status.HTTP_400_BAD_REQUEST)

    token_info = info_res.json()
    allowed_ids = set(settings.GOOGLE_OAUTH_CLIENT_IDS)
    if token_info.get('aud') not in allowed_ids and token_info.get('azp') not in allowed_ids:
        logger.warning(f"⛔ [Google Login] 허용되지 않은 client의 토큰: aud={token_info.get('aud')!r}")
        return Response({'error': '이 서비스용으로 발급된 구글 토큰이 아닙니다.'}, status=status.HTTP_400_BAD_REQUEST)

    email = token_info.get('email')
    if not email or str(token_info.get('email_verified')).lower() != 'true':
        return Response({'error': '인증된 이메일 정보를 가져올 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

    # 2) 이름은 userinfo에서 (실패해도 로그인은 진행)
    name = ''
    try:
        user_res = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        if user_res.status_code == 200:
            name = user_res.json().get('name', '') or ''
    except requests.RequestException:
        pass

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
@throttle_classes([AuthIPThrottle]) # 3. IP별 분당 호출 제한
def demo_login(request):
    """
    크롬 익스텐션용 데모 로그인 API
    호출 시 'demo_guest' 계정의 토큰을 반환합니다.
    """
    # 1. 데모 유저 확인 (없으면 생성, 있으면 가져오기)
    user, created = User.objects.get_or_create(
        username=DEMO_USERNAME,
        defaults={'email': 'demo@guest.com'},
    )

    # 비밀번호로는 로그인할 수 없는 계정으로 둔다 (토큰으로만 사용).
    # 예전 코드가 공개 저장소에 적힌 비밀번호를 설정했으므로, 기존 계정도 여기서 무효화한다.
    if user.has_usable_password():
        user.set_unusable_password()
        user.save(update_fields=['password'])

    # 2. 토큰 가져오기 (없으면 생성)
    token, _ = Token.objects.get_or_create(user=user)

    # 3. 토큰과 유저명 반환
    return Response({
        'token': token.key,       # 이 값을 익스텐션이 저장해서 씁니다.
        'username': user.username,
        'message': '데모 계정으로 로그인되었습니다.'
    }, status=status.HTTP_200_OK)