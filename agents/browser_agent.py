"""
Browser Agent - Headless browser automation via Playwright

Responsibilities:
- Visit public company websites
- Extract visible company information
- Discover public contact/about/team/leadership/sales pages
- Continue discovery even when homepage is blocked
- Use direct HTTP fallback
- Use robots.txt / sitemap discovery
- Use Jina Reader as a public-page fallback
- Extract publicly visible business email addresses
- Extract publicly visible LinkedIn profile URLs
- Return structured contact candidates

Stage 9 Compatible
"""

import logging
import os
import re

from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse, quote

import httpx


logger = logging.getLogger(__name__)


PLAYWRIGHT_HEADLESS = (
    os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
)

BROWSER_TIMEOUT = int(
    os.getenv("BROWSER_TIMEOUT", "30000")
)

HTTP_TIMEOUT = float(
    os.getenv("HTTP_TIMEOUT", "20")
)

USER_AGENT = os.getenv(
    "BROWSER_USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
)

CHALLENGE_MARKERS = [
    "just a moment",
    "checking your browser",
    "verify you are human",
    "verify you are a human",
    "enable javascript and cookies",
    "attention required",
    "cf-chl-",
    "cloudflare",
]


class BrowserAgent:
    """Headless browser agent for public website extraction."""

    def __init__(self):
        self.headless = PLAYWRIGHT_HEADLESS
        self.timeout = BROWSER_TIMEOUT
        self._browser = None
        self._playwright = None

    # ============================================================
    # Browser lifecycle
    # ============================================================

    async def _get_browser(self):
        """Lazy-initialize Playwright browser."""

        if self._browser is None:

            try:
                from playwright.async_api import async_playwright

                self._playwright = (
                    await async_playwright().start()
                )

                self._browser = await (
                    self._playwright.chromium.launch(
                        headless=self.headless
                    )
                )

                logger.info(
                    "Playwright browser initialized"
                )

            except ImportError:

                logger.error(
                    "Playwright not installed. "
                    "Run: pip install playwright && "
                    "playwright install chromium"
                )

                raise

        return self._browser

    async def close(self):
        """Safely close browser and Playwright."""

        browser = self._browser
        playwright = self._playwright

        self._browser = None
        self._playwright = None

        if browser:

            try:
                await browser.close()
            except Exception as e:
                logger.warning(
                    f"Browser close warning: {e}"
                )

        if playwright:

            try:
                await playwright.stop()
            except Exception as e:
                logger.warning(
                    f"Playwright stop warning: {e}"
                )

    # ============================================================
    # URL helpers
    # ============================================================

    @staticmethod
    def _normalize_base_url(domain: str) -> str:
        """Convert domain into normalized HTTPS base URL."""

        value = (domain or "").strip()

        if not value:
            return ""

        if not value.startswith(
            ("http://", "https://")
        ):
            value = f"https://{value}"

        parsed = urlparse(value)

        scheme = parsed.scheme or "https"
        netloc = parsed.netloc

        if not netloc:
            netloc = parsed.path
            path = ""
        else:
            path = parsed.path

        return (
            f"{scheme}://{netloc}{path}"
        ).rstrip("/")

    @staticmethod
    def _clean_url(url: str) -> str:
        """Remove fragments and normalize trailing slash."""

        parsed = urlparse(url)

        return (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
            f"{parsed.path}"
        ).rstrip("/")

    @staticmethod
    def _is_challenge(
        title: str = "",
        text: str = "",
        html: str = ""
    ) -> bool:
        """Detect common anti-bot / Cloudflare pages."""

        combined = (
            f"{title} {text} {html}"
        ).lower()

        return any(
            marker in combined
            for marker in CHALLENGE_MARKERS
        )

    # ============================================================
    # Generic page extraction
    # ============================================================

    async def get_page_text(
        self,
        url: str
    ) -> Dict[str, Any]:
        """Visit URL and extract visible text."""

        browser = await self._get_browser()

        page = await browser.new_page()

        try:

            await page.goto(
                url,
                timeout=self.timeout,
                wait_until="domcontentloaded"
            )

            await page.wait_for_timeout(1200)

            title = await page.title()

            text = await page.inner_text(
                "body"
            )

            if self._is_challenge(
                title,
                text
            ):

                logger.warning(
                    f"Anti-bot challenge detected for {url}"
                )

                return {
                    "url": url,
                    "title": title,
                    "text": text[:10000],
                    "status": "blocked",
                    "reason": (
                        "Anti-bot or Cloudflare "
                        "challenge detected"
                    )
                }

            return {
                "url": url,
                "title": title,
                "text": text[:10000],
                "status": "success"
            }

        except Exception as e:

            logger.warning(
                f"Failed to load {url}: {e}"
            )

            return {
                "url": url,
                "status": "failed",
                "error": str(e)
            }

        finally:

            try:
                await page.close()
            except Exception:
                pass

    # ============================================================
    # Company extraction
    # ============================================================

    async def extract_company_info(
        self,
        domain: str
    ) -> Dict[str, Any]:
        """Extract publicly visible company information."""

        url = self._normalize_base_url(
            domain
        )

        result = await self.get_page_text(
            url
        )

        if result.get("status") != "success":

            return {
                "domain": domain,
                "url": url,
                "title": result.get("title"),
                "homepage_text": result.get(
                    "text",
                    ""
                ),
                "status": result.get(
                    "status",
                    "failed"
                ),
                "reason": result.get(
                    "reason",
                    result.get(
                        "error",
                        "Unable to access company website"
                    )
                )
            }

        return {
            "domain": domain,
            "url": url,
            "title": result.get("title"),
            "homepage_text": result.get(
                "text",
                ""
            ),
            "status": "success"
        }

    # ============================================================
    # LinkedIn extraction
    # ============================================================

    async def extract_linkedin_profile(
        self,
        linkedin_url: str
    ) -> Dict[str, Any]:
        """Extract publicly visible LinkedIn page content."""

        result = await self.get_page_text(
            linkedin_url
        )

        return {
            "url": linkedin_url,
            "content": result.get(
                "text",
                ""
            )[:5000],
            "status": result.get(
                "status"
            ),
            "reason": result.get(
                "reason",
                result.get("error")
            )
        }

    # ============================================================
    # Extraction helpers
    # ============================================================

    @staticmethod
    def _extract_emails(
        text: str
    ) -> List[str]:
        """Extract publicly visible email addresses."""

        if not text:
            return []

        pattern = (
            r"[A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        )

        matches = re.findall(
            pattern,
            text
        )

        emails = []

        ignored_prefixes = (
            "example@",
            "test@",
            "noreply@",
            "no-reply@",
            "donotreply@",
            "do-not-reply@",
        )

        ignored_domains = (
            "example.com",
            "example.org",
            "example.net",
        )

        for email in matches:

            normalized = email.strip().lower()

            if normalized.startswith(
                ignored_prefixes
            ):
                continue

            domain = normalized.split(
                "@",
                1
            )[-1]

            if domain in ignored_domains:
                continue

            if normalized not in emails:
                emails.append(
                    normalized
                )

        return emails[:20]

    @staticmethod
    def _extract_mailto_emails(
        html: str
    ) -> List[str]:
        """Extract emails from mailto links."""

        if not html:
            return []

        pattern = (
            r"mailto:"
            r"([A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
        )

        matches = re.findall(
            pattern,
            html,
            flags=re.IGNORECASE
        )

        emails = []

        for email in matches:

            normalized = email.strip().lower()

            if normalized.startswith(
                (
                    "example@",
                    "test@",
                    "noreply@",
                    "no-reply@",
                    "donotreply@",
                    "do-not-reply@",
                )
            ):
                continue

            if normalized not in emails:
                emails.append(
                    normalized
                )

        return emails[:20]

    @staticmethod
    def _extract_linkedin_urls(
        text: str
    ) -> List[str]:
        """Extract publicly visible LinkedIn URLs."""

        if not text:
            return []

        pattern = (
            r"https?://(?:www\.)?linkedin\.com/"
            r"(?:in|company)/"
            r"[A-Za-z0-9_%\-./]+"
        )

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        urls = []

        for url in matches:

            url = url.rstrip(
                ".,);]}>\"'"
            )

            if url not in urls:
                urls.append(
                    url
                )

        return urls[:20]

    @staticmethod
    def _guess_name_from_linkedin(
        linkedin_url: str
    ) -> Optional[str]:
        """Best-effort name candidate from LinkedIn slug."""

        if not linkedin_url:
            return None

        match = re.search(
            r"linkedin\.com/in/([^/?#]+)",
            linkedin_url,
            flags=re.IGNORECASE
        )

        if not match:
            return None

        slug = match.group(1)

        slug = re.sub(
            r"[-_]+",
            " ",
            slug
        )

        slug = re.sub(
            r"\d+$",
            "",
            slug
        ).strip()

        if not slug:
            return None

        return slug.title()

    @staticmethod
    def _infer_title_from_context(
        text: str,
        email: Optional[str] = None
    ) -> Optional[str]:
        """Best-effort title detection."""

        if not text:
            return None

        titles = [
            "Chief Executive Officer",
            "Chief Technology Officer",
            "Chief Financial Officer",
            "Chief Operating Officer",
            "Chief Marketing Officer",
            "Chief Revenue Officer",
            "Chief Sales Officer",
            "Vice President of Sales",
            "Vice President of Marketing",
            "Vice President of Engineering",
            "Head of Sales",
            "Head of Marketing",
            "Head of Engineering",
            "Head of Growth",
            "Director of Sales",
            "Director of Marketing",
            "Director of Engineering",
            "Business Development Manager",
            "Sales Director",
            "Founder",
            "Co-Founder",
            "CEO",
            "CTO",
            "CFO",
            "COO",
            "CMO",
            "CRO",
            "VP Sales",
            "VP Marketing",
            "VP Engineering",
        ]

        text_lower = text.lower()

        for title in titles:

            if title.lower() in text_lower:
                return title

        return None

    @staticmethod
    def _is_same_domain(
        base_url: str,
        candidate_url: str
    ) -> bool:
        """Check same-domain URLs."""

        try:

            base_host = (
                urlparse(base_url)
                .netloc
                .lower()
                .replace("www.", "")
            )

            candidate_host = (
                urlparse(candidate_url)
                .netloc
                .lower()
                .replace("www.", "")
            )

            return (
                base_host == candidate_host
                or candidate_host.endswith(
                    "." + base_host
                )
            )

        except Exception:

            return False

    @staticmethod
    def _score_internal_link(
        url: str,
        text: str
    ) -> int:
        """Score relevant internal pages."""

        value = (
            f"{url} {text}"
        ).lower()

        score = 0

        high_priority = [
            "contact",
            "contact-us",
            "contactus",
            "team",
            "leadership",
            "about",
            "about-us",
            "company",
            "sales",
            "business-development",
            "founders",
            "management",
        ]

        medium_priority = [
            "press",
            "media",
            "partners",
            "careers",
            "customers",
            "customer",
        ]

        for keyword in high_priority:

            if keyword in value:
                score += 10

        for keyword in medium_priority:

            if keyword in value:
                score += 3

        return score

    # ============================================================
    # Direct HTTP fallback
    # ============================================================

    async def _http_get(
        self,
        url: str
    ) -> Dict[str, Any]:
        """
        Fetch public page directly using HTTP.

        This is important because Playwright may receive a
        Cloudflare challenge while the underlying public page
        can still be accessed directly.
        """

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:

            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
                headers=headers,
            ) as client:

                response = await client.get(
                    url
                )

                content_type = (
                    response.headers.get(
                        "content-type",
                        ""
                    )
                ).lower()

                text = response.text

                return {
                    "url": str(
                        response.url
                    ),
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "text": text[:300000],
                    "ok": (
                        response.status_code < 400
                        and (
                            "text/html" in content_type
                            or "xml" in content_type
                            or "text/plain" in content_type
                            or not content_type
                        )
                    ),
                }

        except Exception as e:

            logger.warning(
                f"Direct HTTP request failed for "
                f"{url}: {e}"
            )

            return {
                "url": url,
                "status_code": None,
                "text": "",
                "ok": False,
                "error": str(e),
            }

    # ============================================================
    # HTTP contact extraction
    # ============================================================

    def _contacts_from_content(
        self,
        url: str,
        content: str
    ) -> Dict[str, Any]:
        """Extract contacts from raw HTML/text."""

        emails = self._extract_emails(
            content
        )

        for email in self._extract_mailto_emails(
            content
        ):

            if email not in emails:
                emails.append(
                    email
                )

        linkedin_urls = (
            self._extract_linkedin_urls(
                content
            )
        )

        title_candidate = (
            self._infer_title_from_context(
                content
            )
        )

        contacts = []

        for email in emails:

            contacts.append({
                "name": None,
                "title": title_candidate,
                "email": email,
                "linkedin": (
                    linkedin_urls[0]
                    if linkedin_urls
                    else None
                ),
                "source": "browser_http",
                "source_url": url,
                "confidence": "public",
            })

        for linkedin_url in linkedin_urls:

            candidate = {
                "name": self._guess_name_from_linkedin(
                    linkedin_url
                ),
                "title": title_candidate,
                "email": None,
                "linkedin": linkedin_url,
                "source": "browser_http",
                "source_url": url,
                "confidence": "public",
            }

            duplicate = any(
                existing.get("linkedin")
                == linkedin_url
                for existing in contacts
            )

            if not duplicate:
                contacts.append(
                    candidate
                )

        return {
            "url": url,
            "emails": emails[:20],
            "linkedin_urls": linkedin_urls[:20],
            "contacts": contacts[:20],
        }

    # ============================================================
    # Jina Reader fallback
    # ============================================================

    async def _jina_read(
        self,
        url: str
    ) -> Dict[str, Any]:
        """
        Read a public webpage through Jina Reader.

        This is a fallback only. No credentials are required.
        """

        reader_url = (
            "https://r.jina.ai/"
            + url
        )

        result = await self._http_get(
            reader_url
        )

        if not result.get("ok"):

            return {
                "status": "failed",
                "url": url,
                "text": "",
            }

        text = result.get(
            "text",
            ""
        )

        if not text:
            return {
                "status": "empty",
                "url": url,
                "text": "",
            }

        return {
            "status": "success",
            "url": url,
            "text": text[:300000],
        }

    # ============================================================
    # Robots / Sitemap discovery
    # ============================================================

    async def _discover_sitemap_urls(
        self,
        base: str,
        max_urls: int = 50
    ) -> List[str]:
        """Discover relevant URLs from robots.txt and sitemap."""

        parsed = urlparse(base)

        root = (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
        )

        sitemap_candidates = [
            f"{root}/sitemap.xml",
            f"{root}/sitemap_index.xml",
        ]

        robots = await self._http_get(
            f"{root}/robots.txt"
        )

        robots_text = robots.get(
            "text",
            ""
        )

        for line in robots_text.splitlines():

            if line.lower().startswith(
                "sitemap:"
            ):

                sitemap_url = line.split(
                    ":",
                    1
                )[1].strip()

                if sitemap_url:
                    sitemap_candidates.append(
                        sitemap_url
                    )

        discovered = []

        for sitemap_url in dict.fromkeys(
            sitemap_candidates
        ):

            result = await self._http_get(
                sitemap_url
            )

            if not result.get("ok"):
                continue

            text = result.get(
                "text",
                ""
            )

            urls = re.findall(
                r"<loc>\s*(.*?)\s*</loc>",
                text,
                flags=re.IGNORECASE
            )

            for candidate in urls:

                candidate = (
                    candidate
                    .replace("&amp;", "&")
                    .strip()
                )

                if not candidate:
                    continue

                if not self._is_same_domain(
                    base,
                    candidate
                ):
                    continue

                score = self._score_internal_link(
                    candidate,
                    candidate
                )

                if score <= 0:
                    continue

                clean = self._clean_url(
                    candidate
                )

                if clean not in discovered:
                    discovered.append(
                        clean
                    )

                if len(discovered) >= max_urls:
                    return discovered

        return discovered

    # ============================================================
    # Internal link discovery
    # ============================================================

    async def discover_internal_links(
        self,
        base_url: str,
        max_links: int = 25
    ) -> List[str]:
        """Discover relevant internal links."""

        browser = await self._get_browser()

        page = await browser.new_page()

        discovered = []

        try:

            await page.goto(
                base_url,
                timeout=self.timeout,
                wait_until="domcontentloaded"
            )

            await page.wait_for_timeout(
                1000
            )

            title = await page.title()

            text = await page.inner_text(
                "body"
            )

            if self._is_challenge(
                title,
                text
            ):

                logger.warning(
                    f"Internal link discovery blocked for "
                    f"{base_url}"
                )

                return []

            links = await page.locator(
                "a[href]"
            ).evaluate_all(
                """
                anchors => anchors.map(a => ({
                    href: a.href,
                    text: (a.innerText || a.textContent || '').trim()
                }))
                """
            )

            scored = []

            for item in links:

                href = item.get(
                    "href",
                    ""
                )

                link_text = item.get(
                    "text",
                    ""
                )

                if not href:
                    continue

                if not href.startswith(
                    ("http://", "https://")
                ):

                    href = urljoin(
                        base_url,
                        href
                    )

                if not self._is_same_domain(
                    base_url,
                    href
                ):
                    continue

                clean_url = self._clean_url(
                    href
                )

                score = self._score_internal_link(
                    clean_url,
                    link_text
                )

                if score <= 0:
                    continue

                scored.append(
                    (
                        score,
                        clean_url
                    )
                )

            scored.sort(
                key=lambda item: item[0],
                reverse=True
            )

            for _, url in scored:

                if url not in discovered:

                    discovered.append(
                        url
                    )

                if len(discovered) >= max_links:
                    break

            return discovered

        except Exception as e:

            logger.warning(
                f"Internal link discovery failed for "
                f"{base_url}: {e}"
            )

            return []

        finally:

            try:
                await page.close()
            except Exception:
                pass

    # ============================================================
    # Playwright contact extraction
    # ============================================================

    async def _extract_page_contacts(
        self,
        url: str
    ) -> Dict[str, Any]:
        """Extract public contacts from one page."""

        browser = await self._get_browser()

        page = await browser.new_page()

        try:

            await page.goto(
                url,
                timeout=self.timeout,
                wait_until="domcontentloaded"
            )

            await page.wait_for_timeout(
                1000
            )

            title = await page.title()

            text = await page.inner_text(
                "body"
            )

            html = await page.content()

            if self._is_challenge(
                title,
                text,
                html
            ):

                logger.warning(
                    f"Contact extraction blocked for {url}"
                )

                return {
                    "url": url,
                    "title": title,
                    "text": text[:5000],
                    "emails": [],
                    "linkedin_urls": [],
                    "contacts": [],
                    "status": "blocked",
                    "reason": (
                        "Anti-bot or Cloudflare "
                        "challenge detected"
                    ),
                }

            extracted = self._contacts_from_content(
                url,
                f"{text}\n{html}"
            )

            return {
                "url": url,
                "title": title,
                "text": text[:5000],
                "emails": extracted["emails"],
                "linkedin_urls": extracted[
                    "linkedin_urls"
                ],
                "contacts": extracted["contacts"],
                "status": "success",
            }

        except Exception as e:

            logger.warning(
                f"Contact extraction failed for "
                f"{url}: {e}"
            )

            return {
                "url": url,
                "status": "failed",
                "error": str(e),
            }

        finally:

            try:
                await page.close()
            except Exception:
                pass

    # ============================================================
    # Public contact discovery
    # ============================================================

    async def find_contact_page(
        self,
        domain: str
    ) -> Dict[str, Any]:
        """
        Discover public contact/team/leadership pages.

        IMPORTANT:
        Homepage Cloudflare block does NOT terminate discovery.
        Direct HTTP, common paths, sitemap and Jina fallback
        are still attempted.
        """

        base = self._normalize_base_url(
            domain
        )

        paths = [
            "/contact",
            "/contact-us",
            "/contactus",
            "/about",
            "/about-us",
            "/team",
            "/leadership",
            "/company",
            "/sales",
            "/founders",
            "/management",
        ]

        visited = set()

        all_contacts = []
        all_emails = []
        all_linkedin = []

        pages_checked = []

        def merge_result(
            result: Dict[str, Any]
        ):
            """Merge one extraction result."""

            for email in result.get(
                "emails",
                []
            ):

                if email not in all_emails:
                    all_emails.append(
                        email
                    )

            for linkedin_url in result.get(
                "linkedin_urls",
                []
            ):

                if linkedin_url not in all_linkedin:
                    all_linkedin.append(
                        linkedin_url
                    )

            for contact in result.get(
                "contacts",
                []
            ):

                duplicate = any(
                    (
                        contact.get("email")
                        and existing.get("email")
                        == contact.get("email")
                    )
                    or (
                        contact.get("linkedin")
                        and existing.get("linkedin")
                        == contact.get("linkedin")
                    )
                    for existing in all_contacts
                )

                if not duplicate:
                    all_contacts.append(
                        contact
                    )

        try:

            # ----------------------------------------------------
            # 1. Homepage via Playwright.
            # ----------------------------------------------------

            homepage_result = (
                await self._extract_page_contacts(
                    base
                )
            )

            pages_checked.append({
                "url": base,
                "status": homepage_result.get(
                    "status"
                ),
            })

            visited.add(
                base
            )

            merge_result(
                homepage_result
            )

            # ----------------------------------------------------
            # 2. ALWAYS try common paths.
            #
            # This is the main fix for Cloudflare.
            # ----------------------------------------------------

            candidate_urls = []

            for path in paths:

                candidate_url = (
                    base + path
                )

                if candidate_url not in candidate_urls:
                    candidate_urls.append(
                        candidate_url
                    )

            # ----------------------------------------------------
            # 3. Discover internal links when homepage works.
            # ----------------------------------------------------

            if homepage_result.get(
                "status"
            ) == "success":

                discovered_links = (
                    await self.discover_internal_links(
                        base,
                        max_links=25
                    )
                )

                for discovered_url in discovered_links:

                    if discovered_url not in candidate_urls:
                        candidate_urls.append(
                            discovered_url
                        )

            # ----------------------------------------------------
            # 4. Sitemap / robots discovery.
            #
            # Works independently of browser challenge.
            # ----------------------------------------------------

            sitemap_links = (
                await self._discover_sitemap_urls(
                    base,
                    max_urls=50
                )
            )

            for sitemap_url in sitemap_links:

                if sitemap_url not in candidate_urls:
                    candidate_urls.append(
                        sitemap_url
                    )

            # ----------------------------------------------------
            # 5. Direct HTTP first.
            # ----------------------------------------------------

            for url in candidate_urls:

                if url in visited:
                    continue

                visited.add(
                    url
                )

                http_result = await self._http_get(
                    url
                )

                status_code = (
                    http_result.get(
                        "status_code"
                    )
                )

                if not http_result.get("ok"):

                    pages_checked.append({
                        "url": url,
                        "status": (
                            "http_failed"
                            if status_code is None
                            else f"http_{status_code}"
                        ),
                    })

                    continue

                content = http_result.get(
                    "text",
                    ""
                )

                if not content:
                    continue

                if self._is_challenge(
                    text=content
                ):

                    pages_checked.append({
                        "url": url,
                        "status": "blocked",
                    })

                    continue

                extracted = (
                    self._contacts_from_content(
                        url,
                        content
                    )
                )

                merge_result(
                    extracted
                )

                pages_checked.append({
                    "url": url,
                    "status": "http_success",
                })

                # Stop early when we have actual public contacts.
                if all_contacts:
                    break

            # ----------------------------------------------------
            # 6. Jina Reader fallback.
            #
            # Only run if direct extraction found nothing.
            # ----------------------------------------------------

            if not all_contacts:

                jina_candidates = [
                    base
                ]

                for path in paths:

                    url = base + path

                    if url not in jina_candidates:
                        jina_candidates.append(
                            url
                        )

                for url in jina_candidates[:8]:

                    if url in visited:
                        continue

                    result = await self._jina_read(
                        url
                    )

                    pages_checked.append({
                        "url": (
                            "jina://"
                            + url
                        ),
                        "status": result.get(
                            "status"
                        ),
                    })

                    text = result.get(
                        "text",
                        ""
                    )

                    if not text:
                        continue

                    extracted = (
                        self._contacts_from_content(
                            url,
                            text
                        )
                    )

                    # Mark Jina as the actual source.
                    for contact in extracted.get(
                        "contacts",
                        []
                    ):

                        contact["source"] = (
                            "public_web_reader"
                        )

                    merge_result(
                        extracted
                    )

                    if all_contacts:
                        break

            # ----------------------------------------------------
            # 7. Final result.
            # ----------------------------------------------------

            if all_contacts:

                return {
                    "domain": domain,
                    "found_url": all_contacts[0].get(
                        "source_url"
                    ),
                    "contacts": all_contacts[:20],
                    "emails": all_emails[:20],
                    "linkedin_urls": all_linkedin[:20],
                    "pages_checked": pages_checked,
                    "status": "success",
                }

            return {
                "domain": domain,
                "found_url": None,
                "contacts": [],
                "emails": all_emails[:20],
                "linkedin_urls": all_linkedin[:20],
                "pages_checked": pages_checked,
                "status": "not_found",
                "reason": (
                    "No publicly visible business contact "
                    "information was found"
                ),
            }

        except Exception as e:

            logger.error(
                f"Browser contact discovery failed: {e}"
            )

            return {
                "domain": domain,
                "status": "error",
                "contacts": all_contacts[:20],
                "emails": all_emails[:20],
                "linkedin_urls": all_linkedin[:20],
                "pages_checked": pages_checked,
                "reason": str(e),
            }

        finally:

            await self.close()

    # ============================================================
    # Agent entry point
    # ============================================================

    async def run(
        self,
        task: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Entry point called by Manager Agent."""

        context = context or {}

        domain = context.get(
            "domain"
        )

        url = context.get(
            "url"
        )

        action = context.get(
            "action",
            "extract_company"
        )

        try:

            if action == "extract_company" and domain:

                return await self.extract_company_info(
                    domain
                )

            elif action == "get_page" and url:

                return await self.get_page_text(
                    url
                )

            elif action == "find_contact" and domain:

                return await self.find_contact_page(
                    domain
                )

            elif action == "linkedin" and url:

                return await self.extract_linkedin_profile(
                    url
                )

            return {
                "status": "error",
                "message": (
                    f"Unknown action '{action}' "
                    "or missing context"
                ),
            }

        finally:

            await self.close()


