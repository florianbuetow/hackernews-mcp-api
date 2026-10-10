"""Tests for downloading linked pages and extracting their text."""

import httpx
import pytest

from search_hackernews.articles import Article, ArticleUnavailable, fetch_article
from tests.helpers import ARTICLE_PAGE

_URL = "https://news.example.com/fde"


def _fetch(handler: httpx.MockTransport) -> Article | ArticleUnavailable:
    with httpx.Client(transport=handler) as client:
        return fetch_article(client, _URL)


def test_fetch_article_returns_the_article_text_of_an_html_page() -> None:
    page = httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=ARTICLE_PAGE)

    result = _fetch(httpx.MockTransport(lambda request: page))

    assert isinstance(result, Article)
    assert "Forward deployed engineers sit with customers" in result.markdown
    assert "Today AI startups hire them" in result.markdown


def _raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Name or service not known", request=request)


_PDF = httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.7")
_EMPTY_PAGE = httpx.Response(200, headers={"content-type": "text/html"}, text="<html><body></body></html>")


@pytest.mark.parametrize(
    ("handler", "reason"),
    [
        (httpx.MockTransport(lambda request: httpx.Response(403)), "HTTP 403 Forbidden"),
        (httpx.MockTransport(lambda request: _PDF), "not an HTML page (application/pdf)"),
        (httpx.MockTransport(_raise_connect_error), "ConnectError: Name or service not known"),
        (httpx.MockTransport(lambda request: _EMPTY_PAGE), "no article text found"),
    ],
    ids=["http-error", "pdf", "unreachable", "no-text"],
)
def test_fetch_article_reports_why_a_page_has_no_text(handler: httpx.MockTransport, reason: str) -> None:
    assert _fetch(handler) == ArticleUnavailable(reason)
