"""
Browser Agent - Headless browser automation via Playwright
Visits company websites, LinkedIn profiles, extracts structured data
"""
import asyncio
import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30000"))  # ms


class BrowserAgent:
  """Headless browser agent for website scraping and data extraction"""

  def __init__(self):
    self.headless = PLAYWRIGHT_HEADLESS
    self.timeout = BROWSER_TIMEOUT
    self._browser = None
    self._playwright = None

  async def _get_browser(self):
    """Lazy-initialize Playwright browser"""
    if self._browser is None:
      try:
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        logger.info("Playwright browser initialized")
      except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        raise
    return self._browser

  async def close(self):
    """Clean up browser resources"""
    if self._browser:
      await self._browser.close()
      self._browser = None
    if self._playwright:
      await self._playwright.stop()
      self._playwright = None

  async def get_page_text(self, url: str) -> Dict[str, Any]:
    """Visit a URL and extract visible text content"""
    browser = await self._get_browser()
    page = await browser.new_page()
    try:
      await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
      await page.wait_for_timeout(2000)  # let JS render
      title = await page.title()
      text = await page.inner_text("body")
      return {
        "url": url,
        "title": title,
        "text": text[:5000],  # cap at 5000 chars
        "status": "success"
      }
    except Exception as e:
      logger.warning(f"Failed to load {url}: {e}")
      return {"url": url, "status": "failed", "error": str(e)}
    finally:
      await page.close()

  async def extract_company_info(self, domain: str) -> Dict[str, Any]:
    """Visit company homepage and extract key info"""
    url = f"https://{domain}" if not domain.startswith("http") else domain
    result = await self.get_page_text(url)
    if result["status"] == "failed":
      return result
    text = result.get("text", "")
    return {
      "domain": domain,
      "title": result.get("title"),
      "homepage_text": text,
      "status": "success"
    }

  async def extract_linkedin_profile(self, linkedin_url: str) -> Dict[str, Any]:
    """Extract publicly visible LinkedIn profile/company page data"""
    result = await self.get_page_text(linkedin_url)
    return {
      "url": linkedin_url,
      "content": result.get("text", "")[:3000],
      "status": result.get("status")
    }

  async def find_contact_page(self, domain: str) -> Dict[str, Any]:
    """Try common contact page paths and return first found"""
    paths = ["/contact", "/contact-us", "/about", "/team", "/about-us"]
    base = f"https://{domain}" if not domain.startswith("http") else domain
    for path in paths:
      url = base.rstrip("/") + path
      result = await self.get_page_text(url)
      if result["status"] == "success" and len(result.get("text", "")) > 200:
        return {"found_url": url, "content": result["text"][:3000], "status": "success"}
    return {"domain": domain, "status": "not_found"}

  async def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """Entry point called by Manager Agent"""
    domain = context.get("domain") if context else None
    url = context.get("url") if context else None
    action = context.get("action", "extract_company") if context else "extract_company"

    try:
      if action == "extract_company" and domain:
        return await self.extract_company_info(domain)
      elif action == "get_page" and url:
        return await self.get_page_text(url)
      elif action == "find_contact" and domain:
        return await self.find_contact_page(domain)
      elif action == "linkedin" and url:
        return await self.extract_linkedin_profile(url)
      else:
        return {"status": "error", "message": f"Unknown action '{action}' or missing context"}
    finally:
      await self.close()
