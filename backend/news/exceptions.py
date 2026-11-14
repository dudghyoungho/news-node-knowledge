# backend/news/exceptions.py
"""
API 예외 응답 형식.

확장 프로그램과 대시보드는 실패 시 응답의 `error`(데모 로그인은 `message`) 키를 화면에 보여 준다.
DRF 기본 429 응답은 `detail` 키만 있으므로, 호출 제한에 걸렸을 때는 같은 문구를
`error` / `message` / `detail`에 모두 넣는다. 다른 예외 응답은 바꾸지 않는다.
"""
import math

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler


class RateLimited(Throttled):
    default_detail = "요청이 너무 많습니다."


class DemoLimitReached(Throttled):
    default_detail = "데모 체험 한도에 도달했습니다. 구글 로그인 후 계속 사용할 수 있습니다."


def _wait_text(seconds):
    seconds = int(math.ceil(seconds))
    if seconds >= 3600:
        return f"약 {math.ceil(seconds / 3600)}시간"
    if seconds >= 60:
        return f"약 {math.ceil(seconds / 60)}분"
    return f"{seconds}초"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None or not isinstance(exc, Throttled):
        return response

    message = str(exc.default_detail) if isinstance(exc, (RateLimited, DemoLimitReached)) else str(RateLimited.default_detail)
    if exc.wait:
        message = f"{message} {_wait_text(exc.wait)} 후 다시 시도해 주세요."

    response.data = {
        'error': message,
        'message': message,
        'detail': message,
        'retry_after': int(math.ceil(exc.wait)) if exc.wait else None,
    }
    return response
