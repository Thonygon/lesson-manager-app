import unittest

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
    def test_expected_response(self):
        health.check_url("https://app.masterclassio.com/sign-in", 200, resolve=lambda *args, **kwargs: [(1,)], open_url=lambda url, timeout: FakeResponse(200, url))

    def test_wrong_status_fails(self):
        with self.assertRaisesRegex(RuntimeError, "expected HTTP 404"):
            health.check_url("https://masterclassio.com/missing", 404, resolve=lambda *args, **kwargs: [(1,)], open_url=lambda url, timeout: FakeResponse(200, url))

    def test_redirect_away_from_custom_domain_fails(self):
        with self.assertRaisesRegex(RuntimeError, "unexpected redirect"):
            health.check_url("https://app.masterclassio.com/sign-in", 200, resolve=lambda *args, **kwargs: [(1,)], open_url=lambda url, timeout: FakeResponse(200, "https://classio.expo.app/sign-in"))


if __name__ == "__main__":
    unittest.main()
