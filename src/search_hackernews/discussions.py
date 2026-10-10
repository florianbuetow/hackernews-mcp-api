"""Download a story's full comment tree from the official Hacker News API."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial

import httpx
from pydantic import JsonValue, TypeAdapter

from search_hackernews.config import DiscussionsConfig

_ITEM: TypeAdapter[dict[str, JsonValue] | None] = TypeAdapter(dict[str, JsonValue] | None)
_KIDS: TypeAdapter[list[int]] = TypeAdapter(list[int])


@dataclass
class _Node:
    """An item and the comments that reply to it."""

    item: dict[str, JsonValue]
    comments: list["_Node"]

    def to_json(self) -> dict[str, JsonValue]:
        """The item with its replies, nested, under "comments"."""
        return {**self.item, "comments": [comment.to_json() for comment in self.comments]}


def fetch_discussion(client: httpx.Client, config: DiscussionsConfig, story_id: str) -> str:
    """Return the story with its nested comments, as indented JSON.

    The official API serves one item per request, so the comments are fetched a level of the
    thread at a time, at most config.max_concurrent_requests at once. Each item keeps the
    fields the API serves and lists its replies under "comments", in the API's order.
    """
    story = _Node(_fetch_item(client, config, int(story_id)), [])
    level: list[_Node] = [story]
    with ThreadPoolExecutor(max_workers=config.max_concurrent_requests) as pool:
        while level:
            replies = [(parent, kid) for parent in level for kid in _kids(parent.item)]
            items = pool.map(partial(_fetch_item, client, config), [kid for _, kid in replies])
            level = []
            for (parent, _), item in zip(replies, items, strict=True):
                node = _Node(item, [])
                parent.comments.append(node)
                level.append(node)
    return json.dumps(story.to_json(), indent=2, ensure_ascii=False) + "\n"


def _fetch_item(client: httpx.Client, config: DiscussionsConfig, item_id: int) -> dict[str, JsonValue]:
    """Download one item; the API answers null for an ID it does not know."""
    response = client.get(config.item_url.format(id=item_id))
    response.raise_for_status()
    item = _ITEM.validate_json(response.content)
    if item is None:
        raise ValueError(f"Hacker News has no item {item_id}")
    if item["id"] != item_id:
        raise ValueError(f"Requested item {item_id} but received item {item['id']}")
    return item


def _kids(item: dict[str, JsonValue]) -> list[int]:
    """The IDs of the item's replies; the API leaves "kids" out of items without any."""
    if "kids" not in item:
        return []
    return _KIDS.validate_python(item["kids"])
