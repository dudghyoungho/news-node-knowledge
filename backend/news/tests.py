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


# ---------------------------------------------------------------------------
# [보-3] 다른 사용자의 기사 노출 차단 (실제 테스트 DB 사용)
# ---------------------------------------------------------------------------
from django.contrib.auth import get_user_model  # noqa: E402
from django.test import TestCase  # noqa: E402
from django.utils import timezone as dj_tz  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from news.access import visible_articles  # noqa: E402
from news.models import Article, UserActionLog  # noqa: E402
from news.rag_service import recommend_mixed_portfolio, recommend_random_recent  # noqa: E402


def vec(seed):
    """768차원 테스트 벡터. seed가 같으면 같은 벡터(=코사인 거리 0)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    v = rng.normal(size=768)
    return (v / np.linalg.norm(v)).tolist()


@mock.patch("news.knowledge_bridge.get_completion", return_value="(test comment)")
class CrossUserIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser("admin", "admin@test.local", "x")
        cls.alice = User.objects.create_user("alice")
        cls.bob = User.objects.create_user("bob")
        now = dj_tz.now()
        ent = {"PERSON": ["홍길동"], "ORG": ["뉴스노드"]}

        def mk(user, title, source, seed, days_ago=0, url=None):
            return Article.objects.create(
                user=user, title=title, url=url or f"https://news.example.com/{title}",
                source=source, region="KR", status=Article.Status.SAVED, summary=f"{title} 요약",
                category="IT/테크", entities=ent, embedding_pytorch=vec(seed),
                created_at=now - dj_tz.timedelta(days=days_ago),
            )

        cls.alice_art = mk(cls.alice, "alice-own", Article.Source.USER_SAVED, seed=1)
        # bob의 기사: alice 기사와 벡터가 똑같고 과거 기사 → 막지 않으면 Bridge 1순위 후보가 됨
        cls.bob_art = mk(cls.bob, "bob-private", Article.Source.USER_SAVED, seed=1, days_ago=3,
                         url="https://news.example.com/shared")
        cls.rss_old = mk(cls.admin, "rss-old", Article.Source.RSS_CRAWLED, seed=2, days_ago=5,
                         url="https://news.example.com/shared")
        cls.rss_new = mk(cls.admin, "rss-new", Article.Source.RSS_CRAWLED, seed=3, days_ago=1)

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_visible_articles_scope(self, _llm):
        ids = set(visible_articles(self.alice).values_list("id", flat=True))
        self.assertIn(self.alice_art.id, ids)
        self.assertIn(self.rss_old.id, ids)
        self.assertNotIn(self.bob_art.id, ids)

    def test_bridge_on_other_users_article_is_404(self, _llm):
        r = self.client_for(self.alice).get(f"/api/news/articles/{self.bob_art.id}/bridge/")
        self.assertEqual(r.status_code, 404)

    def test_bridge_candidates_exclude_other_users_articles(self, _llm):
        r = self.client_for(self.alice).get(f"/api/news/articles/{self.alice_art.id}/bridge/?region=KR")
        self.assertEqual(r.status_code, 200)
        body = str(r.data)
        self.assertNotIn("bob-private", body)

    def test_bridge_on_rss_article_is_allowed(self, _llm):
        r = self.client_for(self.alice).get(f"/api/news/articles/{self.rss_new.id}/bridge/")
        self.assertEqual(r.status_code, 200)

    def test_context_recommendation_on_other_users_article_is_404(self, _llm):
        r = self.client_for(self.alice).get(f"/api/news/rag/context/{self.bob_art.id}/")
        self.assertEqual(r.status_code, 404)

    def test_portfolio_and_fallback_never_return_other_users_articles(self, _llm):
        from news.models import UserProfile
        UserProfile.objects.create(user=self.alice, embedding_user=vec(1))
        for results in (recommend_mixed_portfolio(self.alice, region="KR"),
                        recommend_random_recent(self.alice, "KR", limit=10)):
            ids = {getattr(a, "id", None) or a.get("id") for a in results}
            self.assertNotIn(self.bob_art.id, ids)

    def test_stats_recent_fallback_excludes_other_users_articles(self, _llm):
        r = self.client_for(self.alice).get("/api/news/stats/?region=KR")
        self.assertEqual(r.status_code, 200)
        ids = {a["id"] for a in r.data.get("recent_articles", [])}
        self.assertNotIn(self.bob_art.id, ids)

    def test_log_links_to_rss_not_other_users_article(self, _llm):
        r = self.client_for(self.alice).post(
            "/api/news/logs/",
            {"article_url": "https://news.example.com/shared", "dwell_time": 10, "region": "KR"},
            format="json",
        )
        self.assertIn(r.status_code, (200, 201))
        log = UserActionLog.objects.filter(user=self.alice).latest("timestamp")
        self.assertEqual(log.article_id, self.rss_old.id)

    def test_log_prefers_own_article(self, _llm):
        self.client_for(self.bob).post(
            "/api/news/logs/",
            {"article_url": "https://news.example.com/shared", "dwell_time": 10, "region": "KR"},
            format="json",
        )
        log = UserActionLog.objects.filter(user=self.bob).latest("timestamp")
        self.assertEqual(log.article_id, self.bob_art.id)
