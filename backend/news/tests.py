"""
실행: docker compose -f docker-compose.dev.yml exec web python backend/manage.py test news

아래 테스트는 DB와 네트워크를 쓰지 않는다(SimpleTestCase + DNS/HTTP mock).
DB가 필요한 테스트는 pgvector 확장 마이그레이션([버-4]) 추가 후에 작성한다.
"""
import socket
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
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
    def setUp(self):
        cache.clear()  # 호출 제한 횟수 초기화

    def _post(self, url):
        request = APIRequestFactory().post("/api/news/summarize/", {"url": url}, format="json")
        force_authenticate(request, user=SimpleNamespace(id=1, pk=1, username="tester", is_authenticated=True))
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
    def setUp(self):
        cache.clear()

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

    def setUp(self):
        cache.clear()

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


# ---------------------------------------------------------------------------
# [보-4] API 호출 제한 + 데모 계정 제한
# ---------------------------------------------------------------------------
from rest_framework.throttling import SimpleRateThrottle  # noqa: E402

from news.access import DEMO_USERNAME  # noqa: E402

# 검증 단계에서 바로 400으로 끝나는 주소. 크롤링·GPT 없이 호출 횟수만 센다.
BLOCKED_URL = "http://127.0.0.1/"


def set_rates(**rates):
    """settings의 제한 숫자를 테스트 동안만 바꾼다."""
    return mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, rates)


class ThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user("alice")
        cls.bob = User.objects.create_user("bob")
        cls.demo = User.objects.create_user(DEMO_USERNAME)

    def setUp(self):
        cache.clear()

    def client_for(self, user, ip="203.0.113.1"):
        # 운영처럼 프록시(NPM)가 붙인 X-Forwarded-For의 마지막 주소를 방문자 IP로 쓴다 (NUM_PROXIES=1)
        c = APIClient(HTTP_X_FORWARDED_FOR=ip)
        if user:
            c.force_authenticate(user)
        return c

    def summarize(self, client):
        return client.post("/api/news/summarize/", {"url": BLOCKED_URL}, format="json")

    # --- 응답 형식 ---------------------------------------------------------
    def test_throttled_response_has_error_key_and_retry_after(self):
        c = self.client_for(None)
        for _ in range(10):
            self.assertEqual(c.post("/api/news/auth/demo/").status_code, 200)
        r = c.post("/api/news/auth/demo/")
        self.assertEqual(r.status_code, 429)
        self.assertIn("요청이 너무 많습니다", r.data["error"])
        self.assertEqual(r.data["message"], r.data["error"])  # 확장 데모 로그인은 message를 읽음
        self.assertTrue(r.has_header("Retry-After"))

    # --- 로그인: IP별 ------------------------------------------------------
    def test_auth_limit_is_per_ip(self):
        for _ in range(10):
            self.client_for(None, ip="203.0.113.1").post("/api/news/auth/demo/")
        self.assertEqual(self.client_for(None, ip="203.0.113.1").post("/api/news/auth/demo/").status_code, 429)
        self.assertEqual(self.client_for(None, ip="203.0.113.2").post("/api/news/auth/demo/").status_code, 200)

    def test_spoofed_forwarded_for_prefix_does_not_bypass(self):
        # 클라이언트가 앞쪽에 가짜 주소를 넣어도, 프록시가 붙인 마지막 주소로 센다
        for i in range(10):
            self.client_for(None, ip=f"10.9.9.{i}, 203.0.113.7").post("/api/news/auth/demo/")
        r = self.client_for(None, ip="10.9.9.99, 203.0.113.7").post("/api/news/auth/demo/")
        self.assertEqual(r.status_code, 429)

    # --- 요약: 사용자별 ----------------------------------------------------
    def test_summarize_hourly_limit_per_user(self):
        alice = self.client_for(self.alice)
        for _ in range(30):
            self.assertEqual(self.summarize(alice).status_code, 400)
        self.assertEqual(self.summarize(alice).status_code, 429)
        # 다른 사용자는 영향 없음
        self.assertEqual(self.summarize(self.client_for(self.bob)).status_code, 400)

    def test_hourly_block_does_not_eat_daily_quota(self):
        with set_rates(summarize_hour="2/hour", summarize_day="3/day"):
            alice = self.client_for(self.alice)
            self.summarize(alice), self.summarize(alice)
            for _ in range(5):  # 시간당 한도에 막힌 요청들
                self.assertEqual(self.summarize(alice).status_code, 429)
            day_key = f"throttle_summarize_day_{self.alice.pk}"
            self.assertEqual(len(cache.get(day_key)), 2)

    # --- 데모 계정 ---------------------------------------------------------
    def test_demo_summarize_limit_per_ip(self):
        visitor_a = self.client_for(self.demo, ip="198.51.100.1")
        for _ in range(5):
            self.assertEqual(self.summarize(visitor_a).status_code, 400)
        r = self.summarize(visitor_a)
        self.assertEqual(r.status_code, 429)
        self.assertIn("데모 체험 한도", r.data["error"])
        # 다른 방문자는 아직 쓸 수 있음
        self.assertEqual(self.summarize(self.client_for(self.demo, ip="198.51.100.2")).status_code, 400)

    def test_demo_summarize_total_limit(self):
        with set_rates(demo_summarize_total="3/day"):
            for i in range(3):
                self.assertEqual(self.summarize(self.client_for(self.demo, ip=f"198.51.100.{i}")).status_code, 400)
            r = self.summarize(self.client_for(self.demo, ip="198.51.100.200"))
            self.assertEqual(r.status_code, 429)
            self.assertIn("데모 체험 한도", r.data["error"])
            # 일반 사용자는 데모 한도와 무관
            self.assertEqual(self.summarize(self.client_for(self.alice)).status_code, 400)

    def test_demo_visitors_have_separate_general_limits(self):
        with set_rates(user="2/hour"):
            a = self.client_for(self.demo, ip="198.51.100.1")
            a.get("/api/news/rag/context/999999/"), a.get("/api/news/rag/context/999999/")
            self.assertEqual(a.get("/api/news/rag/context/999999/").status_code, 429)
            b = self.client_for(self.demo, ip="198.51.100.2")
            self.assertEqual(b.get("/api/news/rag/context/999999/").status_code, 404)

    # --- GPT 호출 API ------------------------------------------------------
    def test_ai_endpoint_hourly_limit(self):
        with set_rates(ai="2/hour"):
            alice = self.client_for(self.alice)
            alice.get("/api/news/articles/999999/bridge/")
            alice.get("/api/news/articles/999999/bridge/")
            self.assertEqual(alice.get("/api/news/articles/999999/bridge/").status_code, 429)

    # --- 데모 비밀번호 -----------------------------------------------------
    def test_demo_login_makes_password_unusable(self):
        self.demo.set_password("old-known-password")
        self.demo.save()
        r = self.client_for(None).post("/api/news/auth/demo/")
        self.assertEqual(r.status_code, 200)
        self.demo.refresh_from_db()
        self.assertFalse(self.demo.has_usable_password())


# ---------------------------------------------------------------------------
# [버-1] "이미 본 기사 제외" — 저장값(READ/SAVE 대문자)과 조회값 일치, 추천에서 제외
# ---------------------------------------------------------------------------
from news.models import UserProfile  # noqa: E402


class SeenArticleExclusionTests(TestCase):
    """
    alice의 취향 벡터와 가장 가까운 RSS 기사(rss_read)를 alice가 이미 읽었다.
    추천 묶음(3칸)에는 읽은 기사와 alice 자신의 기사가 나오면 안 된다.
    무작위가 섞여 있어서 여러 번 돌려 확인한다.
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser("admin", "admin@test.local", "x")
        cls.alice = User.objects.create_user("alice")
        UserProfile.objects.create(user=cls.alice, embedding_user=vec(1))
        now = dj_tz.now()

        def mk(user, title, source, seed, category="IT/테크", days_ago=1):
            return Article.objects.create(
                user=user, title=title, url=f"https://news.example.com/{title}",
                source=source, region="KR", status=Article.Status.SAVED, summary=f"{title} 요약",
                category=category, article_type="INSIGHT", entities={}, embedding_pytorch=vec(seed),
                created_at=now - dj_tz.timedelta(days=days_ago),
            )

        rss = Article.Source.RSS_CRAWLED
        cls.alice_own = mk(cls.alice, "alice-own", Article.Source.USER_SAVED, seed=1)
        cls.rss_read = mk(cls.admin, "rss-read", rss, seed=1)   # 취향과 똑같은 벡터 = 1순위 후보
        cls.rss_fresh = [
            mk(cls.admin, f"rss-{i}", rss, seed=10 + i, category=cat, days_ago=i)
            for i, cat in enumerate(["IT/테크", "IT/테크", "경제", "경제", "사회", "스포츠"], start=2)
        ]
        UserActionLog.objects.create(
            user=cls.alice, article=cls.rss_read, article_url=cls.rss_read.url,
            action=UserActionLog.ActionType.READ, region="KR", dwell_time=40,
        )
        # 외부 사이트 로그 (DB에 없는 기사 → article 없음)도 섞어 둔다
        UserActionLog.objects.create(
            user=cls.alice, article=None, article_url="https://elsewhere.example.com/x",
            action=UserActionLog.ActionType.READ, region="KR", dwell_time=40,
        )

    def test_seen_ids_match_stored_action_values(self):
        seen = set(UserActionLog.seen_article_ids(self.alice))
        self.assertEqual(seen, {self.rss_read.id})

    def test_click_is_not_counted_as_seen(self):
        UserActionLog.objects.create(
            user=self.alice, article=self.rss_fresh[0], article_url=self.rss_fresh[0].url,
            action=UserActionLog.ActionType.CLICK, region="KR", dwell_time=8,
        )
        self.assertNotIn(self.rss_fresh[0].id, UserActionLog.seen_article_ids(self.alice))

    def test_portfolio_excludes_read_and_own_articles(self):
        for _ in range(30):
            ids = {a["id"] for a in recommend_mixed_portfolio(self.alice, region="KR")}
            self.assertTrue(ids)
            self.assertNotIn(self.rss_read.id, ids, "이미 읽은 기사가 추천됨")
            self.assertNotIn(self.alice_own.id, ids, "내가 저장한 기사가 추천됨")

    def test_portfolio_falls_back_to_seen_when_nothing_else(self):
        # 남은 후보가 하나도 없으면 본 기사라도 보여 준다 (빈 화면 방지, 원래 의도)
        for art in self.rss_fresh:
            UserActionLog.objects.create(
                user=self.alice, article=art, article_url=art.url,
                action=UserActionLog.ActionType.SAVE, region="KR", dwell_time=999,
            )
        self.assertTrue(recommend_mixed_portfolio(self.alice, region="KR"))
