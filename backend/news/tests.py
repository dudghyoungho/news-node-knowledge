"""
실행: docker compose -f docker-compose.dev.yml exec web python backend/manage.py test news

아래 테스트는 DB와 네트워크를 쓰지 않는다(SimpleTestCase + DNS/HTTP mock).
DB가 필요한 테스트는 pgvector 확장 마이그레이션([버-4]) 추가 후에 작성한다.
"""
import socket
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from news import crawler, url_safety
from news.url_safety import UnsafeURLError, safe_get, validate_public_url
from news.views.article_views import summarize


def fake_dns(mapping):
    """호스트명 → IP 목록으로 socket.getaddrinfo를 흉내 낸다."""
    def _getaddrinfo(host, port, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror("not found")
        return [
            (socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))
            for ip in mapping[host]
        ]
    return mock.patch.object(url_safety.socket, "getaddrinfo", side_effect=_getaddrinfo)


def fake_response(status=200, location=None, content_type="text/html"):
    headers = {"Content-Type": content_type}
    if location:
        headers["Location"] = location
    return SimpleNamespace(
        status_code=status,
        headers=headers,
        is_redirect=status in (301, 302, 303, 307, 308) and location is not None,
        is_permanent_redirect=status in (301, 308) and location is not None,
        close=lambda: None,
    )


PUBLIC = {"news.example.com": ["93.184.216.34"]}


class ValidatePublicUrlTests(SimpleTestCase):
    def test_public_https_url_is_allowed(self):
        with fake_dns(PUBLIC):
            self.assertEqual(
                validate_public_url(" https://news.example.com/a/1 "),
                "https://news.example.com/a/1",
            )

    def test_blocks_internal_and_reserved_addresses(self):
        cases = {
            "http://127.0.0.1/": ["127.0.0.1"],
            "http://localhost/": ["127.0.0.1"],
            "http://db/": ["172.18.0.3"],                      # docker 내부망
            "http://10.0.0.5/": ["10.0.0.5"],
            "http://192.168.1.1/": ["192.168.1.1"],
            "http://169.254.169.254/latest/meta-data/": ["169.254.169.254"],  # 클라우드 메타데이터
            "http://0.0.0.0/": ["0.0.0.0"],
            "http://[::1]/": ["::1"],
            "http://mapped.test/": ["::ffff:127.0.0.1"],     # IPv4-mapped IPv6
            "http://2130706433/": ["127.0.0.1"],             # 정수형 IP 표기
        }
        for url, ips in cases.items():
            from urllib.parse import urlsplit
            host = urlsplit(url).hostname
            with self.subTest(url=url), fake_dns({host: ips}):
                with self.assertRaises(UnsafeURLError):
                    validate_public_url(url)

    def test_blocks_if_any_resolved_address_is_internal(self):
        with fake_dns({"mixed.example.com": ["93.184.216.34", "10.0.0.1"]}):
            with self.assertRaises(UnsafeURLError):
                validate_public_url("https://mixed.example.com/")

    def test_blocks_bad_scheme_port_credentials_and_unknown_host(self):
        with fake_dns(PUBLIC):
            for url in [
                "file:///etc/passwd",
                "ftp://news.example.com/",
                "gopher://news.example.com/",
                "http://news.example.com:5432/",
                "http://news.example.com:6379/",
                "http://user:pw@news.example.com/",
                "http:///nohost",
                "https://unknown.example.com/",
                "",
            ]:
                with self.subTest(url=url):
                    with self.assertRaises(UnsafeURLError):
                        validate_public_url(url)


class SafeGetTests(SimpleTestCase):
    def test_follows_redirect_between_public_hosts(self):
        dns = {"a.example.com": ["93.184.216.34"], "b.example.com": ["93.184.216.35"]}
        responses = [fake_response(302, "https://b.example.com/final"), fake_response(200)]
        with fake_dns(dns), mock.patch.object(url_safety.requests, "get", side_effect=responses) as get:
            resp = safe_get("https://a.example.com/start", timeout=1, allow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(get.call_args_list[1].args[0], "https://b.example.com/final")
        for call in get.call_args_list:
            self.assertFalse(call.kwargs["allow_redirects"])

    def test_blocks_redirect_to_internal_address(self):
        dns = {"a.example.com": ["93.184.216.34"], "169.254.169.254": ["169.254.169.254"]}
        with fake_dns(dns), mock.patch.object(
            url_safety.requests, "get", return_value=fake_response(302, "http://169.254.169.254/latest/")
        ) as get:
            with self.assertRaises(UnsafeURLError):
                safe_get("https://a.example.com/start")
        self.assertEqual(get.call_count, 1)  # 내부 주소로는 요청하지 않음

    def test_relative_redirect_is_resolved_and_checked(self):
        responses = [fake_response(301, "/moved"), fake_response(200)]
        with fake_dns(PUBLIC), mock.patch.object(url_safety.requests, "get", side_effect=responses) as get:
            safe_get("https://news.example.com/old")
        self.assertEqual(get.call_args_list[1].args[0], "https://news.example.com/moved")

    def test_too_many_redirects(self):
        with fake_dns(PUBLIC), mock.patch.object(
            url_safety.requests, "get", return_value=fake_response(302, "https://news.example.com/loop")
        ):
            with self.assertRaises(UnsafeURLError):
                safe_get("https://news.example.com/loop")


class CrawlerGuardTests(SimpleTestCase):
    def test_extract_article_returns_none_for_internal_url_without_request(self):
        with fake_dns({"db": ["172.18.0.3"]}), mock.patch.object(url_safety.requests, "get") as get:
            self.assertIsNone(crawler.extract_article("http://db/"))
            self.assertIsNone(crawler.extract_article("http://db/?q=naver.com"))  # 네이버 분기도 보호
        get.assert_not_called()


class SummarizeViewGuardTests(SimpleTestCase):
    def _post(self, url):
        request = APIRequestFactory().post("/api/news/summarize/", {"url": url}, format="json")
        force_authenticate(request, user=SimpleNamespace(id=1, is_authenticated=True))
        return summarize(request)

    def test_internal_url_returns_400_before_crawling(self):
        with fake_dns({"169.254.169.254": ["169.254.169.254"]}), \
                mock.patch("news.views.article_views.extract_article") as extract:
            response = self._post("http://169.254.169.254/latest/meta-data/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        extract.assert_not_called()

    def test_non_http_scheme_returns_400(self):
        with mock.patch("news.views.article_views.extract_article") as extract:
            response = self._post("file:///etc/passwd")
        self.assertEqual(response.status_code, 400)
        extract.assert_not_called()


# ---------------------------------------------------------------------------
# [보-2] 구글 로그인: 토큰 발급 대상(aud/azp) 확인
# ---------------------------------------------------------------------------
from django.test import override_settings  # noqa: E402

from news.views import auth_views  # noqa: E402

OUR_CLIENT = "our-client.apps.googleusercontent.com"
OTHER_CLIENT = "evil-app.apps.googleusercontent.com"


def google_res(status=200, data=None):
    return SimpleNamespace(status_code=status, json=lambda: data or {})


@override_settings(GOOGLE_OAUTH_CLIENT_IDS=[OUR_CLIENT])
class GoogleLoginAudienceTests(SimpleTestCase):
    def _post(self, body):
        request = APIRequestFactory().post("/api/news/auth/google/", body, format="json")
        return auth_views.google_login(request)

    def _patch_db(self):
        user = SimpleNamespace(username="a@b.com")
        return (
            mock.patch.object(auth_views.User.objects, "get_or_create", return_value=(user, False)),
            mock.patch.object(auth_views.Token.objects, "get_or_create",
                              return_value=(SimpleNamespace(key="tok123"), False)),
        )

    def test_token_for_our_client_logs_in(self):
        info = {"aud": OUR_CLIENT, "azp": OUR_CLIENT, "email": "a@b.com", "email_verified": "true"}
        p_user, p_token = self._patch_db()
        with mock.patch.object(auth_views.requests, "get",
                               side_effect=[google_res(200, info), google_res(200, {"name": "A"})]) as get, \
                p_user as get_user, p_token:
            response = self._post({"access_token": "t"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["token"], "tok123")
        get_user.assert_called_once()
        self.assertEqual(get.call_args_list[0].args[0], auth_views.GOOGLE_TOKENINFO_URL)

    def test_token_issued_to_other_app_is_rejected(self):
        info = {"aud": OTHER_CLIENT, "azp": OTHER_CLIENT, "email": "victim@b.com", "email_verified": "true"}
        p_user, p_token = self._patch_db()
        with mock.patch.object(auth_views.requests, "get", return_value=google_res(200, info)), \
                p_user as get_user, p_token as get_token:
            response = self._post({"access_token": "t"})
        self.assertEqual(response.status_code, 400)
        get_user.assert_not_called()
        get_token.assert_not_called()

    def test_azp_match_is_accepted(self):
        info = {"aud": "something-else", "azp": OUR_CLIENT, "email": "a@b.com", "email_verified": True}
        p_user, p_token = self._patch_db()
        with mock.patch.object(auth_views.requests, "get",
                               side_effect=[google_res(200, info), google_res(500)]), p_user, p_token:
            response = self._post({"access_token": "t"})
        self.assertEqual(response.status_code, 200)  # 이름 조회 실패해도 로그인

    def test_unverified_email_is_rejected(self):
        info = {"aud": OUR_CLIENT, "email": "a@b.com", "email_verified": "false"}
        p_user, p_token = self._patch_db()
        with mock.patch.object(auth_views.requests, "get", return_value=google_res(200, info)), \
                p_user as get_user, p_token:
            response = self._post({"access_token": "t"})
        self.assertEqual(response.status_code, 400)
        get_user.assert_not_called()

    def test_invalid_or_missing_token(self):
        with mock.patch.object(auth_views.requests, "get", return_value=google_res(400, {"error": "invalid_token"})):
            self.assertEqual(self._post({"access_token": "bad"}).status_code, 400)
        with mock.patch.object(auth_views.requests, "get") as get:
            self.assertEqual(self._post({}).status_code, 400)
            get.assert_not_called()

    def test_google_unreachable_returns_502(self):
        with mock.patch.object(auth_views.requests, "get",
                               side_effect=auth_views.requests.ConnectionError("down")):
            self.assertEqual(self._post({"access_token": "t"}).status_code, 502)
