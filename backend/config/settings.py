"""
Django settings for config project.
Final Production Version for News Node
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# [Security]
# 프로덕션에서는 .env 파일의 SECRET_KEY를 사용합니다.
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-default-key-for-dev")

# 프로덕션에서는 반드시 False여야 합니다. (.env에서 DEBUG=0 설정)
DEBUG = os.environ.get("DEBUG", "False") == "True"

# 환경변수에서 호스트 목록을 가져오고, 없으면 기본값(로컬+서버IP+도메인)을 사용합니다.
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost 127.0.0.1 52.79.176.176 news.young-dev.link .young-dev.link").split()


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # admin social settings
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    
    # [3rd Party Apps]
    'rest_framework',           
    'rest_framework.authtoken',
    'corsheaders',  # CORS (크롬 익스텐션 연동 필수)
    'pgvector',
    
    # [Local Apps]
    'news',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', # [중요] 가능한 최상단에 위치
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # 정적 파일 서빙
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'news_db'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': '5432',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]


# Internationalization
LANGUAGE_CODE = 'ko-kr' 
TIME_ZONE = 'Asia/Seoul' 
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# [REST Framework]
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',   # 익스텐션용
        'rest_framework.authentication.SessionAuthentication', # 대시보드용
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}

# [API Keys]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")


# ------------------------------------------------------------------------------
# [보안 및 CORS/CSRF 설정]
# ------------------------------------------------------------------------------

# 1. CSRF 신뢰할 수 있는 출처
# HTTPS 도메인과 로컬 개발 주소를 모두 포함해야 합니다.
CSRF_TRUSTED_ORIGINS = [
    "https://news.young-dev.link",      # 운영 도메인
    "https://www.news.young-dev.link",
    "http://localhost:8000",            # 로컬 개발
    "http://127.0.0.1:8000",
    "http://52.79.176.176",             # 서버 IP (HTTP)
    "https://52.79.176.176",            # 서버 IP (HTTPS)
]

# 2. CORS 허용 출처 (크롬 익스텐션 & 프론트엔드)
CORS_ALLOWED_ORIGINS = [
    "https://news.young-dev.link",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "chrome-extension://onfldbkpmmcaepamcdfbkehekmpbmonj",
    "chrome-extension://flcnfkeekiohhhikkfkpihdmokopjgmc",
    "chrome-extension://ngpaediapbkndhliglmnmgogljneopfl",
]
CORS_ALLOW_CREDENTIALS = True

# 3. HTTPS 프록시 설정
# Nginx Proxy Manager가 넘겨주는 'X-Forwarded-Proto: https' 헤더를 신뢰합니다.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 4. 쿠키 보안 설정 (조건부 적용)
# 배포 환경(DEBUG=False)에서만 Secure 쿠키를 강제합니다.
# 로컬(DEBUG=True)에서는 False로 두어야 로그인 에러가 발생하지 않습니다.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SITE_ID = 1