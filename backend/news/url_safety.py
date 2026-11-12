# backend/news/url_safety.py
"""
외부에서 받은 URL을 서버가 대신 가져오기 전에 검사한다 (SSRF 방지).

- http/https, 기본 포트(80/443)만 허용
- 호스트를 IP로 풀어서 공인 IP가 아니면 거부 (사설·루프백·링크로컬·메타데이터 주소 등)
- 리다이렉트는 자동으로 따라가지 않고, 한 단계마다 다시 검사

남은 한계: 검사 시점과 실제 접속 시점 사이에 DNS 응답이 바뀌는 공격(DNS rebinding)은
막지 못한다. 완전히 막으려면 검사한 IP로 직접 접속하도록 연결 계층을 바꿔야 한다.
"""
import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlsplit

import requests

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {None, 80, 443}
MAX_REDIRECTS = 5


class UnsafeURLError(ValueError):
    """서버가 가져오면 안 되는 URL."""


def _is_public_ip(ip_str):
    ip = ipaddress.ip_address(ip_str.split("%", 1)[0])  # IPv6 zone id 제거
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def validate_public_url(url):
    """공인 인터넷 주소면 그대로 돌려주고, 아니면 UnsafeURLError를 던진다."""
    if not isinstance(url, str) or not url.strip():
        raise UnsafeURLError("URL이 비어 있습니다.")

    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("http 또는 https 주소만 허용됩니다.")
    if not parts.hostname:
        raise UnsafeURLError("호스트가 없는 주소입니다.")
    if parts.username or parts.password:
        raise UnsafeURLError("계정 정보가 포함된 주소는 허용되지 않습니다.")
    try:
        port = parts.port
    except ValueError:
        raise UnsafeURLError("포트 형식이 잘못되었습니다.")
    if port not in ALLOWED_PORTS:
        raise UnsafeURLError("기본 포트(80, 443)만 허용됩니다.")

    default_port = 443 if parts.scheme.lower() == "https" else 80
    try:
        infos = socket.getaddrinfo(parts.hostname, port or default_port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        raise UnsafeURLError("주소를 찾을 수 없습니다.")

    addresses = {info[4][0] for info in infos}
    if not addresses or not all(_is_public_ip(a) for a in addresses):
        raise UnsafeURLError("내부망 또는 예약된 주소는 허용되지 않습니다.")

    return url.strip()


def safe_get(url, **kwargs):
    """
    requests.get과 같지만, 첫 주소와 리다이렉트로 이동하는 모든 주소를 검사한다.
    위험한 주소면 UnsafeURLError를 던진다.
    """
    kwargs.pop("allow_redirects", None)
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_url(current)
        response = requests.get(current, allow_redirects=False, **kwargs)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise UnsafeURLError("리다이렉트 주소가 없습니다.")
            current = urljoin(current, location)
            continue
        return response
    raise UnsafeURLError("리다이렉트가 너무 많습니다.")
