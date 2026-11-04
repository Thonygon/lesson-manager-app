import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.request import Request

import check_public_domains as health


class FakeResponse:
    def __init__(self, status, url):
        self.status = status
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeDnsResponse(BytesIO):
    pass


class PublicDomainHealthTest(unittest.TestCase):
    @staticmethod
    def open_request(request, timeout):
        assert isinstance(request, Request)
        assert request.get_header("User-agent") == health.USER_AGENT
        return FakeResponse(200, request.full_url)

    def test_expected_response(self):
        health.check_url("https://app.masterclassio.com/sign-in", 200, resolve=lambda *args, **kwargs: [(1,)], open_url=self.open_request)

    def test_wrong_status_fails(self):
        with self.assertRaisesRegex(RuntimeError, "expected HTTP 404"):
            health.check_url("https://masterclassio.com/missing", 404, resolve=lambda *args, **kwargs: [(1,)], open_url=self.open_request)

    def test_redirect_away_from_custom_domain_fails(self):
        with self.assertRaisesRegex(RuntimeError, "unexpected redirect"):
            health.check_url("https://app.masterclassio.com/sign-in", 200, resolve=lambda *args, **kwargs: [(1,)], open_url=lambda request, timeout: FakeResponse(200, "https://classio.expo.app/sign-in"))

    def test_public_dns_accepts_resolved_answers(self):
        requests = []

        def open_dns(request, timeout):
            requests.append(request.full_url)
            return FakeDnsResponse(b'{"Status":0,"Answer":[{"type":5,"data":"origin.expo.app."}]}')

        answers = health.check_public_dns("app.masterclassio.com", open_url=open_dns)
        self.assertEqual(len(answers), 2)
        self.assertEqual(len(requests), 2)

    def test_public_dns_rejects_nxdomain(self):
        with self.assertRaisesRegex(RuntimeError, "DNS status 3"):
            health.check_public_dns("masterclassio.com", open_url=lambda request, timeout: FakeDnsResponse(b'{"Status":3}'))

    def test_health_retries_transient_dns_failure(self):
        calls = []

        def sometimes_unavailable(host):
            calls.append(host)
            if len(calls) == 1:
                raise TimeoutError("resolver temporarily unavailable")
            return ["resolved"]

        with patch.object(health, "DNS_HOSTS", ("masterclassio.com",)), patch.object(health, "CHECKS", ()), patch.object(health, "check_public_dns", side_effect=sometimes_unavailable), patch.object(health.time, "sleep") as sleep:
            self.assertEqual(health.main(), 0)
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(3)


if __name__ == "__main__":
    unittest.main()
