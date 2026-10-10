"""Tests for the folder name and the Markdown files of a saved search."""

from datetime import date

import pytest

from search_hackernews.algolia import SearchResult, Story
from search_hackernews.articles import Article, ArticleUnavailable
from search_hackernews.output import directory_name, render_post, render_query, render_results
from tests.helpers import recorded_hit


def _recorded_story(object_id: str) -> Story:
    return Story.model_validate(recorded_hit(object_id))


@pytest.mark.parametrize(
    ("query", "day", "expected"),
    [
        ("Forward deployed engineers", date(2026, 10, 10), "2026-10-10-Forward_deployed_engineers"),
        ("C++ & Rust: a/b?", date(2026, 1, 2), "2026-01-02-C_____Rust__a_b_"),
        ("Größe 2026", date(2026, 10, 10), "2026-10-10-Gr__e_2026"),
    ],
)
def test_directory_name_replaces_each_non_alphanumeric_character_with_an_underscore(query: str, day: date, expected: str) -> None:
    assert directory_name(query, day) == expected


def test_render_query_keeps_the_query_with_markdown_escaped() -> None:
    assert render_query("C++ *fast* [x]") == "# Query\n\nC++ \\*fast\\* \\[x\\]\n"


def test_render_results_lists_the_stories_in_ranking_order_with_their_saved_files() -> None:
    stories = [_recorded_story("48900432"), _recorded_story("47542553")]

    markdown = render_results("Forward deployed engineers", SearchResult(stories=stories, total_matches=2), True)

    assert markdown == (
        "# Results\n"
        "\n"
        '2 stories for "Forward deployed engineers".\n'
        "\n"
        "| # | Title | Points | Comments | Author | Date | Saved |\n"
        "|---:|---|---:|---:|---|---|---|\n"
        "| 1 | [What are Forward Deployed Engineers, and why are they so in demand? (2025)]"
        "(https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers) | 106 "
        "| [98](https://news.ycombinator.com/item?id=48900432) | saisrirampur | 2026-07-13 "
        "| [post](posts/48900432.md) · [discussion](discussions/48900432.json) |\n"
        "| 2 | [Ask HN: What's the Deal with Forward Deployed Engineers?](https://news.ycombinator.com/item?id=47542553) | 2 "
        "| [7](https://news.ycombinator.com/item?id=47542553) | rubyrenegade | 2026-03-27 "
        "| [post](posts/47542553.md) · [discussion](discussions/47542553.json) |\n"
    )


def test_render_results_without_discussions_links_only_the_posts() -> None:
    markdown = render_results("q", SearchResult(stories=[_recorded_story("48900432")], total_matches=1), False)

    assert markdown.endswith("| saisrirampur | 2026-07-13 | [post](posts/48900432.md) |\n")


def test_render_results_escapes_titles_and_urls_that_would_break_the_table() -> None:
    hit = recorded_hit("48900432") | {"title": "Show HN: <$2/hr | [pdf] *wow*", "url": "https://en.wikipedia.org/wiki/Foo_(bar) baz"}

    markdown = render_results("q", SearchResult(stories=[Story.model_validate(hit)], total_matches=1), True)

    assert "| 1 | [Show HN: \\<$2/hr \\| \\[pdf\\] \\*wow\\*](https://en.wikipedia.org/wiki/Foo_%28bar%29%20baz) | 106 |" in markdown


def test_render_results_says_when_the_search_matched_more_stories_than_it_returned() -> None:
    markdown = render_results("python", SearchResult(stories=[_recorded_story("48900432")], total_matches=546870), True)

    assert "1 of 546870 matching stories" in markdown


def test_render_post_shows_the_story_and_the_article_text() -> None:
    markdown = render_post(_recorded_story("48900432"), Article("Forward deployed engineers sit with customers."))

    assert markdown == (
        "# What are Forward Deployed Engineers, and why are they so in demand? (2025)\n"
        "\n"
        "- Link: <https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers>\n"
        "- Discussion: <https://news.ycombinator.com/item?id=48900432>\n"
        "- Points: 106\n"
        "- Comments: 98\n"
        "- Author: saisrirampur\n"
        "- Date: 2026-07-13\n"
        "\n"
        "## Article\n"
        "\n"
        "Forward deployed engineers sit with customers.\n"
    )


def test_render_post_converts_the_html_text_of_a_text_post_to_markdown() -> None:
    hn_html = (
        "We&#x27;re hiring <i>FDEs</i>.<p>"
        'See <a href="https:&#x2F;&#x2F;example.com&#x2F;jobs" rel="nofollow">https:&#x2F;&#x2F;example.com&#x2F;jobs</a>'
    )
    story = Story.model_validate(recorded_hit("47542553") | {"story_text": hn_html})

    markdown = render_post(story, None)

    assert markdown.endswith("- Date: 2026-03-27\n\n## Text\n\nWe're hiring *FDEs*.\n\nSee <https://example.com/jobs>\n")


def test_render_post_says_why_the_article_is_missing() -> None:
    markdown = render_post(_recorded_story("48900432"), ArticleUnavailable("HTTP 403 Forbidden"))

    assert markdown.endswith("- Date: 2026-07-13\n\n## Article\n\nNot downloaded: HTTP 403 Forbidden.\n")
