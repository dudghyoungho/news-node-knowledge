# backend/news/throttles.py
"""
API 호출 횟수 제한 (DRF throttle).

제한 숫자는 settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] 한 곳에서 관리한다.

- user                : 로그인 사용자의 전체 API (기본값, 모든 APIView에 적용)
- summarize_hour/day  : 요약 (GPT 분류 + 요약)
- ai                  : Bridge 코멘트, 복습 퀴즈, 외부 추천 (GPT 호출)
- auth                : 구글/데모 로그인 (IP별)
- demo_summarize_ip   : 데모 계정 요약 — 방문자 IP별
- demo_summarize_total: 데모 계정 요약 — 데모 전체 합계

데모 계정(demo_guest)은 여러 방문자가 같은 계정을 쓰므로, 사용자별 제한도
"데모 + IP" 단위로 센다. 그래야 한 방문자가 한도를 다 써도 다른 방문자는 쓸 수 있다.

횟수는 Django 기본 캐시(LocMem)에 저장된다. gunicorn 프로세스가 1개일 때만 정확하다.
프로세스를 늘리면 Redis 같은 공용 캐시로 옮겨야 한다.
"""
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

from .access import is_demo_user
from .exceptions import DemoLimitReached, RateLimited


class _StopOnFailure:
    """
    한도를 넘으면 그 자리에서 429를 낸다.

    DRF 기본 동작은 하나가 막혀도 나머지 throttle을 모두 계산해서, 시간당 한도에 막힌
    요청이 하루 한도까지 깎아 먹는다. 첫 실패에서 멈추면 막힌 요청은 뒤쪽 한도를 쓰지 않는다.
    """
    exception_class = RateLimited

    def throttle_failure(self):
        raise self.exception_class(wait=self.wait())


class UserThrottle(_StopOnFailure, UserRateThrottle):
    """사용자별 제한. 데모 계정은 방문자 IP별로 센다."""
    scope = 'user'

    def get_cache_key(self, request, view):
        user = request.user
        if is_demo_user(user):
            ident = f"demo-{self.get_ident(request)}"
        elif user and user.is_authenticated:
            ident = user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class SummarizeHourThrottle(UserThrottle):
    scope = 'summarize_hour'


class SummarizeDayThrottle(UserThrottle):
    scope = 'summarize_day'


class AIThrottle(UserThrottle):
    scope = 'ai'


class AuthIPThrottle(_StopOnFailure, AnonRateThrottle):
    """로그인 API: 아직 인증 전이므로 IP별로 센다."""
    scope = 'auth'


class DemoSummarizeIPThrottle(_StopOnFailure, SimpleRateThrottle):
    """데모 계정 요약: 방문자 IP별 하루 한도. 일반 사용자에게는 적용되지 않는다."""
    scope = 'demo_summarize_ip'
    exception_class = DemoLimitReached

    def get_cache_key(self, request, view):
        if not is_demo_user(request.user):
            return None
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class DemoSummarizeTotalThrottle(_StopOnFailure, SimpleRateThrottle):
    """데모 계정 요약: 모든 방문자 합계 하루 한도 (OpenAI 요금 상한)."""
    scope = 'demo_summarize_total'
    exception_class = DemoLimitReached

    def get_cache_key(self, request, view):
        if not is_demo_user(request.user):
            return None
        return self.cache_format % {'scope': self.scope, 'ident': 'all'}


# 요약 API에 붙는 순서: 데모 한도 → 시간당 → 하루
SUMMARIZE_THROTTLES = [
    DemoSummarizeIPThrottle,
    DemoSummarizeTotalThrottle,
    SummarizeHourThrottle,
    SummarizeDayThrottle,
]
