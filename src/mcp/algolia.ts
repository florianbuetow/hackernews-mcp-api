/**
 * Hacker News post and comment search through the Algolia index behind hn.algolia.com, which
 * `just search` also uses. The official Hacker News API has no search.
 */

import { z } from 'zod';

import type { Config } from './config.ts';
import { createdBetween, hnUrl } from './search.ts';
import type { Comment, CreatedRange, Post, SearchPage, SearchRequest } from './search.ts';

/** Algolia returns only the first 1000 hits of a search; pages past them come back empty. */
const REACHABLE_HITS = 1000;

const PostHit = z
  .object({
    objectID: z.string(),
    title: z.string(),
    url: z.string().optional(), // text posts such as "Ask HN" have no url
    story_text: z.string().optional(), // HTML; only text posts have one
    author: z.string(),
    points: z.number(),
    num_comments: z.number(),
    created_at: z.string(),
  })
  .transform(
    (hit): Post => ({
      id: hit.objectID,
      title: hit.title,
      url: missingAsNull(hit.url),
      text: missingAsNull(hit.story_text),
      hn_url: hnUrl(hit.objectID),
      author: hit.author,
      points: hit.points,
      comments: hit.num_comments,
      created_at: hit.created_at,
    }),
  );

const CommentHit = z
  .object({
    objectID: z.string(),
    author: z.string(),
    comment_text: z.string(), // HTML
    story_id: z.number(),
    story_title: z.string(),
    parent_id: z.number(),
    created_at: z.string(),
  })
  .transform(
    (hit): Comment => ({
      id: hit.objectID,
      hn_url: hnUrl(hit.objectID),
      author: hit.author,
      text: hit.comment_text,
      post_id: String(hit.story_id),
      post_title: hit.story_title,
      parent_id: String(hit.parent_id),
      created_at: hit.created_at,
    }),
  );

/** Search posts (stories). */
export function searchPosts(fetchFn: typeof fetch, config: Config, request: SearchRequest): Promise<SearchPage<Post>> {
  return search(fetchFn, config, request, ['story'], PostHit);
}

/** Search the comments on all posts. */
export function searchComments(fetchFn: typeof fetch, config: Config, request: SearchRequest): Promise<SearchPage<Comment>> {
  return search(fetchFn, config, request, ['comment'], CommentHit);
}

/** Fetch one page of the items that carry all the tags, with the website's search parameters from the config. */
async function search<Hit>(
  fetchFn: typeof fetch,
  config: Config,
  request: SearchRequest,
  tags: string[],
  hit: z.ZodType<Hit>,
): Promise<SearchPage<Hit>> {
  if (request.page * request.hits_per_page >= REACHABLE_HITS) {
    throw new Error(
      `Page ${request.page} of ${request.hits_per_page} hits starts past the first ${REACHABLE_HITS} hits, ` +
        'the only ones Algolia returns; narrow the search, for example with min_date and max_date.',
    );
  }
  const numericFilters = createdAtFilters(createdBetween(request.min_date, request.max_date));
  const { application_id, api_key, index, params } = config.algolia;
  const response = await fetchFn(`https://${application_id}-dsn.algolia.net/1/indexes/${index}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': config.http.user_agent,
      'X-Algolia-Application-Id': application_id,
      'X-Algolia-API-Key': api_key,
    },
    body: JSON.stringify({
      ...params,
      query: request.query,
      page: request.page,
      hitsPerPage: request.hits_per_page,
      tagFilters: tags,
      numericFilters,
    }),
    signal: AbortSignal.timeout(config.http.timeout_seconds * 1000),
  });
  if (!response.ok) {
    throw new Error(`Algolia search failed: HTTP ${response.status} ${await response.text()}`);
  }
  const body = z
    .object({ hits: z.array(hit), nbHits: z.number(), nbPages: z.number(), page: z.number() })
    .parse(await response.json());
  return { total_matches: body.nbHits, page: body.page, pages: body.nbPages, hits: body.hits };
}

/** Algolia's filters for the creation time range. */
function createdAtFilters(range: CreatedRange): string[] {
  const filters: string[] = [];
  if (range.from !== undefined) {
    filters.push(`created_at_i>=${range.from}`);
  }
  if (range.until !== undefined) {
    filters.push(`created_at_i<${range.until}`);
  }
  return filters;
}

/** Algolia leaves some fields out, or sends an empty string, when an item has no value for them. */
function missingAsNull(value: string | undefined): string | null {
  return value === undefined || value === '' ? null : value;
}
