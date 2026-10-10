import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { Config } from '../../src/mcp/config.ts';

export const CONFIG: Config = {
  http: { user_agent: 'test-agent/1.0', timeout_seconds: 5 },
  algolia: {
    application_id: 'TESTAPP',
    api_key: 'test-key',
    index: 'Item_dev',
    params: { hitsPerPage: 1000, tagFilters: ['story'], queryType: 'prefixNone' },
  },
  discussions: { item_url: 'https://hacker-news.firebaseio.com/v0/item/{id}.json', max_concurrent_requests: 4 },
};

function fixture(name: string): unknown {
  return JSON.parse(readFileSync(join(import.meta.dirname, '..', 'fixtures', `${name}.json`), 'utf8'));
}

/** A real Algolia response from tests/fixtures/<name>.json. */
export function recordedResponse(name: string): { hits: Record<string, unknown>[] } & Record<string, unknown> {
  return fixture(name) as { hits: Record<string, unknown>[] } & Record<string, unknown>;
}

export const POSTS = 'forward_deployed_engineers_response';
export const POST_COMMENTS = 'forward_deployed_engineers_comments_response';

/** Post 47542553 and its 7 comments, by id, as the official Hacker News API served them. */
export function recordedItems(): Record<string, Record<string, unknown>> {
  return fixture('ask_hn_forward_deployed_engineers_items') as Record<string, Record<string, unknown>>;
}

export interface RecordedRequest {
  url: string;
  method: string | undefined;
  headers: Headers;
  body: unknown;
}

/** A fetch that records each request and answers it with respond(). */
export function fakeFetch(respond: (url: string, init: RequestInit) => Promise<Response>): { fetch: typeof fetch; requests: RecordedRequest[] } {
  const requests: RecordedRequest[] = [];
  const fetchFn = async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    if (init === undefined) {
      throw new Error('fakeFetch expects request options');
    }
    const url = String(input);
    const body = init.body === undefined ? undefined : JSON.parse(String(init.body));
    requests.push({ url, method: init.method, headers: new Headers(init.headers), body });
    return respond(url, init);
  };
  return { fetch: fetchFn, requests };
}

/** A fetch that answers every request with the recorded response. */
export function recordedFetch(name: string): { fetch: typeof fetch; requests: RecordedRequest[] } {
  return fakeFetch(async () => Response.json(recordedResponse(name)));
}

/** The item id in an official Hacker News API URL. */
export function itemId(url: string): string {
  const match = /\/v0\/item\/(\d+)\.json$/.exec(url);
  if (match?.[1] === undefined) {
    throw new Error(`Not an item URL: ${url}`);
  }
  return match[1];
}

/** A fetch that serves items by id like the official Hacker News API, which answers null for unknown ids. */
export function itemsFetch(items: Record<string, unknown>): { fetch: typeof fetch; requests: RecordedRequest[] } {
  return fakeFetch(async (url) => Response.json(items[itemId(url)] ?? null));
}
