"""Bounded public HTTPS retrieval with DNS pinning and no redirects or proxies."""
import hashlib
import http.client
import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urlsplit


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

    def handle_starttag(self, tag, attrs):
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


def retrieve(url):
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
        if response.status != 200 or response.getheader("Content-Encoding", "identity") != "identity":
            raise RetrievalError("Source unavailable; redirects and compressed responses are not accepted")
        mime = response.getheader("Content-Type", "").split(";")[0].lower()
        if mime not in {"text/html", "text/plain"}:
            raise RetrievalError("Source must be HTML or plain text")
        raw = response.read(1000001)
        if len(raw) > 1000000:
            raise RetrievalError("Source exceeds retrieval limit")
        text = raw.decode("utf-8", errors="replace")
        parser = TextExtractor()
        if mime == "text/html":
            parser.feed(text)
            text = "\n".join(parser.parts)
        if not text.strip():
            raise RetrievalError("Source has no readable text")
        text = text[:100000]
        return {"url": url, "title": " ".join(parser.title)[:300] or host,
                "publisher": host, "content": text,
                "content_hash": hashlib.sha256(text.encode()).hexdigest(), "extractor_version": "html-text-v1"}
    except RetrievalError:
        raise
    except (OSError, http.client.HTTPException, ValueError):
        raise RetrievalError("Source retrieval failed") from None
    finally:
        connection.close()
