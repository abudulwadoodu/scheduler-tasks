# error.py

class ScraperError(Exception):
    """Base class for all scraper-related errors."""
    pass


# ============================================================
# HTTP ERRORS
# ============================================================

class HttpError(ScraperError):
    """Any HTTP error (4xx or 5xx)."""
    def __init__(self, status: int, message: str = ""):
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


# ---------- 4xx Client Errors ----------
class HttpClientError(HttpError):
    """4xx errors. Usually NOT retried."""
    pass

class NotFoundError(HttpClientError):
    """404 Not Found / 410 Gone."""
    pass

class ForbiddenError(HttpClientError):
    """403 Forbidden (IP blocked)."""
    pass

class RateLimitError(HttpClientError):
    """429 Too Many Requests (SHOULD be retried)."""
    pass


# ---------- 5xx Server Errors ----------
class HttpServerError(HttpError):
    """5xx server error. SHOULD be retried."""
    pass



# ============================================================
# NETWORK ERRORS
# ============================================================

class NetworkError(ScraperError):
    """Base class for network-related problems."""
    pass

class NetworkTimeoutError(NetworkError):
    """Connection timed out / read timeout."""
    pass

class NetworkConnectionError(NetworkError):
    """DNS failure, internet down, connection refused."""
    pass



# ============================================================
# BROWSER / PLAYWRIGHT ERRORS
# ============================================================

class BrowserError(ScraperError):
    """Base class for browser/playwright errors."""
    pass

class BrowserOperationError(BrowserError):
    """Playwright failures: page.goto errors, JS exceptions, internal browser faults."""
    pass

class SelectorNotFoundError(BrowserError):
    """Expected elements missing → HTML changed."""
    pass

class CaptchaError(BrowserError):
    """Captcha detected."""
    pass



# ============================================================
# SCRAPER LOGIC / BUSINESS LOGIC ERRORS
# ============================================================

class PageStructureError(ScraperError):
    """Required structured data missing, unexpected HTML format."""
    pass

class ParsingError(ScraperError):
    """Regex/XPath/HTML parsing failed."""
    pass

class DataExtractionError(ScraperError):
    """Extracted data is invalid or empty."""
    pass
