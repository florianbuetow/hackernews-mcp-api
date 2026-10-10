/**
 * The comments on one post, read from the official Hacker News API
 * (https://github.com/HackerNews/API), which serves one item per request and has no search.
 */

import pLimit from 'p-limit';
import { z } from 'zod';

import type { Config } from './config.ts';
import { createdBetween, hnUrl } from './search.ts';
import type { Comment, CreatedRange, SearchPage, SearchRequest } from './search.ts';

// Loose, so the post and comment schemas below can read the fields this one leaves out.
const Item = z.looseObject({
  id: z.number(),
  type: z.enum(['job', 'story', 'comment', 'poll', 'pollopt']),
  time: z.number(),
  kids: z.array(z.number()).optional(), // the API leaves kids out of items without replies
  deleted: z.boolean().optional(),
  dead: z.boolean().optional(),
});

const PostItem = Item.extend({ title: z.string() });
const CommentItem = Item.extend({ by: z.string(), text: z.string(), parent: z.number() }); // HTML text

type Item = z.infer<typeof Item>;
type PostItem = z.infer<typeof PostItem>;
type CommentItem = z.infer<typeof CommentItem>;

/** Search the comments on one post by the words they contain and the day they were written, in thread order. */
export async function searchPostComments(
  fetchFn: typeof fetch,
  config: Config,
  postId: string,
  request: SearchRequest,
): Promise<SearchPage<Comment>> {
  const range = createdBetween(request.min_date, request.max_date);
  const limit = pLimit(config.discussions.max_concurrent_requests);
  const fetchItem = (id: number): Promise<Item> => limit(async () => Item.parse(await getItem(fetchFn, config, id)));
  const item = await fetchItem(Number(postId));
  if (item.type === 'comment') {
    throw new Error(`Item ${postId} is a comment, not a post`);
  }
  const post = PostItem.parse(item);
  const items = await descendants(post, fetchItem);
  const words = request.query.toLowerCase().split(/\s+/).filter((word) => word !== '');
  const matches = threadOrder(post, items)
    .filter((comment) => comment.deleted !== true && comment.dead !== true)
    .map((comment) => CommentItem.parse(comment))
    .filter((comment) => containsAll(comment.text, words) && createdIn(comment.time, range));
  const start = request.page * request.hits_per_page;
  return {
    total_matches: matches.length,
    page: request.page,
    pages: Math.ceil(matches.length / request.hits_per_page),
    hits: matches.slice(start, start + request.hits_per_page).map((comment) => asComment(comment, post)),
  };
}

/** One item; the API answers null for an id it does not know. */
async function getItem(fetchFn: typeof fetch, config: Config, id: number): Promise<unknown> {
  const response = await fetchFn(config.discussions.item_url.replace('{id}', String(id)), {
    headers: { 'User-Agent': config.http.user_agent },
    signal: AbortSignal.timeout(config.http.timeout_seconds * 1000),
  });
  if (!response.ok) {
    throw new Error(`Hacker News API failed for item ${id}: HTTP ${response.status} ${await response.text()}`);
  }
  const item: unknown = await response.json();
  if (item === null) {
    throw new Error(`Hacker News has no item ${id}`);
  }
  return item;
}

/** Every comment below the post, by id, fetched a level of the thread at a time. */
async function descendants(post: PostItem, fetchItem: (id: number) => Promise<Item>): Promise<Map<number, Item>> {
  const items = new Map<number, Item>();
  let level = kidsOf(post);
  while (level.length > 0) {
    const fetched = await Promise.all(level.map(fetchItem));
    for (const item of fetched) {
      items.set(item.id, item);
    }
    level = fetched.flatMap(kidsOf);
  }
  return items;
}

/** The comments as Hacker News shows them: each reply follows its parent, siblings in the API's order. */
function threadOrder(parent: Item, items: Map<number, Item>): Item[] {
  return kidsOf(parent).flatMap((id) => {
    const item = items.get(id);
    if (item === undefined) {
      throw new Error(`Comment ${id} was not fetched`);
    }
    return [item, ...threadOrder(item, items)];
  });
}

/** The ids of an item's replies. */
function kidsOf(item: Item): number[] {
  return item.kids === undefined ? [] : item.kids;
}

/** Whether the comment's text, without markup, contains every lowercase word. */
function containsAll(html: string, words: string[]): boolean {
  const text = plainText(html).toLowerCase();
  return words.every((word) => text.includes(word));
}

function createdIn(time: number, range: CreatedRange): boolean {
  return (range.from === undefined || time >= range.from) && (range.until === undefined || time < range.until);
}

const NAMED_ENTITIES = new Map([
  ['quot', '"'],
  ['amp', '&'],
  ['lt', '<'],
  ['gt', '>'],
  ['apos', "'"],
]);

/** HTML text without tags and with the character references Hacker News uses decoded. */
function plainText(html: string): string {
  return html.replace(/<[^>]*>/g, ' ').replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (reference, entity: string) => {
    if (entity.startsWith('#x') || entity.startsWith('#X')) {
      return String.fromCodePoint(Number.parseInt(entity.slice(2), 16));
    }
    if (entity.startsWith('#')) {
      return String.fromCodePoint(Number(entity.slice(1)));
    }
    const character = NAMED_ENTITIES.get(entity.toLowerCase());
    return character === undefined ? reference : character;
  });
}

function asComment(comment: CommentItem, post: PostItem): Comment {
  return {
    id: String(comment.id),
    hn_url: hnUrl(String(comment.id)),
    author: comment.by,
    text: comment.text,
    post_id: String(post.id),
    post_title: post.title,
    parent_id: String(comment.parent),
    created_at: new Date(comment.time * 1000).toISOString().replace('.000Z', 'Z'),
  };
}
