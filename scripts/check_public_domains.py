"""Check public DNS, TLS and expected HTTP routes outside local networks."""

from __future__ import annotations

import json
import socket
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


CHECKS = (
    ("https://masterclassio.com/", 200),
    ("https://masterclassio.com/classio-health-missing-page", 404),
    ("https://app.masterclassio.com/sign-in", 200),
)

USER_AGENT = "Classio-Health/1.0 (+https://masterclassio.com/)"
PUBLIC_DNS = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
)
DNS_HOSTS = ("masterclassio.com", "app.masterclassio.com")
SECURITY_TXT_HOSTS = DNS_HOSTS


def check_public_dns(host: str, *, open_url=urlopen) -> list[str]:
    """Compare independent public resolvers; report a filtered/local DNS answer separately."""
    observations = []
    for endpoint in PUBLIC_DNS:
        request = Request(
            f"{endpoint}?name={host}&type=A",
            headers={"User-Agent": USER_AGENT, "Accept": "application/dns-json"},
        )
        with open_url(request, timeout=15) as response:
            payload = json.load(response)
        status = payload.get("Status")
        answers = payload.get("Answer") or []
        addresses = [str(row.get("data")) for row in answers if row.get("type") == 1 and row.get("data")]
        # A CNAME-only response can be valid when the resolver does not flatten it.
        aliases = [str(row.get("data")) for row in answers if row.get("type") == 5 and row.get("data")]
        if status != 0 or not (addresses or aliases):
            raise RuntimeError(f"{host}: {endpoint} returned DNS status {status} without an A/CNAME answer")
        observations.append(f"{endpoint}: {', '.join(addresses or aliases)}")
    return observations


def check_url(url: str, expected_status: int, *, resolve=socket.getaddrinfo, open_url=urlopen) -> None:
    host = urlparse(url).hostname
    if not host:
        raise ValueError("Health URL has no hostname")
    if not resolve(host, 443, type=socket.SOCK_STREAM):
        raise RuntimeError(f"DNS returned no address for {host}")
    try:
        response = open_url(Request(url, headers={"User-Agent": USER_AGENT}), timeout=15)
    except HTTPError as error:
        response = error
    with response:
        actual_status = response.status
        final_host = urlparse(response.geturl()).hostname
        if actual_status != expected_status:
            raise RuntimeError(f"{host}: expected HTTP {expected_status}, got {actual_status}")
        if final_host != host:
            raise RuntimeError(f"{host}: unexpected redirect to {final_host}")


def check_security_txt(host: str, *, open_url=urlopen, now: datetime | None = None) -> None:
    """Catch a missing, HTML-fallback, misdirected or soon-expiring security contact."""
    url = f"https://{host}/.well-known/security.txt"
    with open_url(Request(url, headers={"User-Agent": USER_AGENT}), timeout=15) as response:
        if response.status != 200 or urlparse(response.geturl()).hostname != host:
            raise RuntimeError(f"{host}: security.txt did not return HTTP 200 on its own host")
        if not response.headers.get("Content-Type", "").lower().startswith("text/plain"):
            raise RuntimeError(f"{host}: security.txt must be served as text/plain")
        raw = response.read(16385)
    if len(raw) > 16384:
        raise RuntimeError(f"{host}: security.txt exceeds 16 KiB")
    try:
        fields = dict(line.split(":", 1) for line in raw.decode("utf-8").splitlines() if line and not line.startswith("#") and ":" in line)
        expires = datetime.fromisoformat(fields["Expires"].strip().replace("Z", "+00:00"))
    except (UnicodeDecodeError, ValueError, KeyError) as error:
        raise RuntimeError(f"{host}: security.txt has no valid Expires field") from error
    if expires.tzinfo is None or expires <= (now or datetime.now(timezone.utc)) + timedelta(days=30):
        raise RuntimeError(f"{host}: security.txt expires within 30 days")
    if fields.get("Canonical", "").strip() != url or not fields.get("Contact", "").strip():
        raise RuntimeError(f"{host}: security.txt lacks its canonical URL or contact")


def main() -> int:
    failures = []
    for host in DNS_HOSTS:
        for attempt in range(3):
            try:
                observations = check_public_dns(host)
                print(f"OK public DNS {host}: {' | '.join(observations)}")
                break
            except Exception as error:
                if attempt == 2:
                    failures.append(f"public DNS {host}: {type(error).__name__}: {error}")
                else:
                    time.sleep(3)
    for url, status in CHECKS:
        for attempt in range(3):
            try:
                check_url(url, status)
                print(f"OK {url}: HTTP {status}")
                break
            except Exception as error:
                if attempt == 2:
                    failures.append(f"{url}: {type(error).__name__}: {error}")
                else:
                    time.sleep(3)
    for host in SECURITY_TXT_HOSTS:
        for attempt in range(3):
            try:
                check_security_txt(host)
                print(f"OK security.txt {host}: contact published and expiry over 30 days away")
                break
            except Exception as error:
                if attempt == 2:
                    failures.append(f"security.txt {host}: {type(error).__name__}: {error}")
                else:
                    time.sleep(3)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
