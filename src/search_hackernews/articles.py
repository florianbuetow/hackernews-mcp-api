"""Download the web page a story links to and extract its main text."""

from dataclasses import dataclass

import httpx
import trafilatura


@dataclass(frozen=True)
class Article:
    """The main text of a linked web page, as Markdown."""

    markdown: str


@dataclass(frozen=True)
class ArticleUnavailable:
    """Why a linked web page gave no text to save."""

    reason: str


def fetch_article(client: httpx.Client, url: str) -> Article | ArticleUnavailable:
    """Download the page at url and extract its main text.

    Linked sites fail in ordinary ways: paywalls, rate limits, dead hosts, PDFs. Those
    outcomes are returned as ArticleUnavailable so the post records why its text is missing.
    """
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type")
            if content_type is None or "html" not in content_type:
                return ArticleUnavailable(f"not an HTML page ({content_type})")
            page = response.read()
    except httpx.HTTPStatusError as error:
        return ArticleUnavailable(f"HTTP {error.response.status_code} {error.response.reason_phrase}")
    except (httpx.HTTPError, httpx.InvalidURL) as error:
        return ArticleUnavailable(f"{type(error).__name__}: {error}")
    markdown = trafilatura.extract(page, url=url, output_format="markdown", include_comments=False)
    if markdown is None:
        return ArticleUnavailable("no article text found")
    return Article(markdown)
