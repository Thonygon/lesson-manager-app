import unittest
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


if __name__ == "__main__":
    unittest.main()
