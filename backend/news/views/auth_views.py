import requests
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status

from django.shortcuts import render, redirect
from django.contrib.auth import login

User = get_user_model()

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

