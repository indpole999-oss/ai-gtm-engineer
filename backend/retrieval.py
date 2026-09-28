"""Bounded public HTTPS retrieval with DNS pinning and no redirects or proxies."""
import hashlib
import http.client
import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from urllib.robotparser import RobotFileParser


class RetrievalError(Exception):
    pass


def public_target(url):
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.port not in (None, 443) or parts.fragment or len(url) > 2000):
            raise ValueError()
        host = parts.hostname.encode("idna").decode("ascii")
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast or ipaddress.ip_address(address).is_reserved for address in addresses):
            raise ValueError()
        return host, addresses[0], (parts.path or "/") + ("?" + parts.query if parts.query else "")
    except (ValueError, UnicodeError, OSError):
        raise RetrievalError("Only public HTTPS sources are supported") from None


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.in_title = False
        self.parts, self.title = [], []
        self.storage_disallowed = False

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            values = dict(attrs)
            if (values.get("name") or "").lower() in {"robots", "gapsevidence"}:
                if any(word in (values.get("content") or "").lower() for word in ("noarchive", "noai", "none")):
                    self.storage_disallowed = True
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())
            if self.in_title:
                self.title.append(data.strip())


def fetch_public(url, limit=1000000):
    host, address, path = public_target(url)
    connection = http.client.HTTPSConnection(host, 443, timeout=10)
    try:
        # Connect to the vetted numeric address; TLS still validates the original
        # hostname. A second DNS lookup cannot redirect this request internally.
        sock = socket.create_connection((address, 443), timeout=10)
        try:
            connection.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        except Exception:
            sock.close()
            raise
        connection.request("GET", path, headers={"Host": host, "Accept": "text/html,text/plain", "Accept-Encoding": "identity", "User-Agent": "GapsEvidence/2.0"})
        response = connection.getresponse()
        if response.getheader("Content-Encoding", "identity") != "identity":
            raise RetrievalError("Compressed responses are not accepted")
        mime = response.getheader("Content-Type", "").split(";")[0].lower()
        if response.status == 200 and mime not in {"text/html", "text/plain"}:
            raise RetrievalError("Source must be HTML or plain text")
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise RetrievalError("Source exceeds retrieval limit")
        text = raw.decode("utf-8", errors="replace")
        return response.status, mime, text, response.getheader("X-Robots-Tag", "")
    except RetrievalError:
        raise
    except (OSError, http.client.HTTPException, ValueError):
        raise RetrievalError("Source retrieval failed") from None
    finally:
        connection.close()


def check_robots(url):
    parts = urlsplit(url)
    robots_url = f"https://{parts.netloc}/robots.txt"
    status, mime, content, _ = fetch_public(robots_url, limit=65536)
    if status in {404, 410}:
        return
    if status != 200 or mime != "text/plain":
        raise RetrievalError("Robots policy unavailable; source not retrieved")
    # The stdlib parser does not implement wildcard/end-anchor extensions. Reject
    # those policies rather than silently interpreting them as permission.
    for line in content.splitlines():
        key, _, value = line.partition("#")[0].partition(":")
        key, value = key.strip().lower(), value.strip()
        if key in {"allow", "disallow"} and ("*" in value or "$" in value):
            raise RetrievalError("Robots policy requires unsupported pattern handling")
        if key in {"crawl-delay", "request-rate"} and value:
            raise RetrievalError("Robots policy requires a scheduled crawler")
        target = parts.path + ("?" + parts.query if parts.query else "")
        # Conservative across groups/Allow ordering: never override a matching
        # deny with a less-specific Allow in the stdlib's first-match parser.
        if key == "disallow" and value and unquote(target).startswith(unquote(value)):
            raise RetrievalError("Source disallowed by conservative robots policy")
    policy = RobotFileParser(robots_url)
    policy.parse(content.splitlines())
    if not policy.can_fetch("GapsEvidence", url):
        raise RetrievalError("Source disallowed by robots policy")


def retrieve(url):
    # Validate the requested destination before looking up its policy as well.
    host, _, _ = public_target(url)
    check_robots(url)
    status, mime, content, directives = fetch_public(url)
    if status != 200:
        raise RetrievalError("Source unavailable; redirects are not accepted")
    if any(word in directives.lower() for word in ("noarchive", "noai", "none")):
        raise RetrievalError("Source policy disallows evidence storage")
    parser = TextExtractor()
    if mime == "text/html":
        parser.feed(content)
        if parser.storage_disallowed:
            raise RetrievalError("Source policy disallows evidence storage")
        content = "\n".join(parser.parts)
    if not content.strip():
        raise RetrievalError("Source has no readable text")
    content = content[:100000]
    return {"url": url, "title": " ".join(parser.title)[:300] or host,
            "publisher": host, "content": content,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(), "extractor_version": "html-text-robots-v2"}
