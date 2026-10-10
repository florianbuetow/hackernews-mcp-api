import assert from 'node:assert/strict';
import { test } from 'node:test';

import { searchPostComments } from '../../src/mcp/hackernews.ts';
import type { SearchPage } from '../../src/mcp/search.ts';
import { CONFIG, fakeFetch, itemId, itemsFetch, recordedItems } from './helpers.ts';

const POST_ID = '47542553';
// The post's comments as Hacker News shows them: each reply follows its parent.
const THREAD_ORDER = ['47546447', '47548311', '47543168', '47545725', '47542672', '47545712', '47617904'];
const ALL = { query: '', page: 0, hits_per_page: 100 };

function ids(page: SearchPage<{ id: string }>): string[] {
  return page.hits.map((hit) => hit.id);
}

test('lists all comments on a post in thread order', async () => {
  const page = await searchPostComments(itemsFetch(recordedItems()).fetch, CONFIG, POST_ID, ALL);

  assert.deepEqual(ids(page), THREAD_ORDER);
  assert.equal(page.total_matches, 7);
  assert.equal(page.pages, 1);
});

test('requests the post and each comment once from the official API', async () => {
  const { fetch, requests } = itemsFetch(recordedItems());

  await searchPostComments(fetch, CONFIG, POST_ID, ALL);

  assert.deepEqual(
    requests.map((request) => request.url).toSorted(),
    [POST_ID, ...THREAD_ORDER].map((id) => `https://hacker-news.firebaseio.com/v0/item/${id}.json`).toSorted(),
  );
  assert.equal(requests[0]?.headers.get('User-Agent'), 'test-agent/1.0');
});

test('returns each comment with its author, text, post, and parent', async () => {
  const items = recordedItems();

  const page = await searchPostComments(itemsFetch(items).fetch, CONFIG, POST_ID, ALL);

  assert.deepEqual(page.hits[1], {
    id: '47548311',
    hn_url: 'https://news.ycombinator.com/item?id=47548311',
    author: 'rubyrenegade',
    text: items['47548311']?.['text'],
    post_id: '47542553',
    post_title: "Ask HN: What's the Deal with Forward Deployed Engineers?",
    parent_id: '47546447',
    created_at: '2026-03-27T21:12:37Z',
  });
});

for (const [query, expected] of [
  ['palantir', ['47543168', '47545725']],
  ["SALARY we've", ['47545712']],
  ['kubernetes', []],
] as const) {
  test(`query ${JSON.stringify(query)} keeps the comments containing every word, ignoring case and markup`, async () => {
    const page = await searchPostComments(itemsFetch(recordedItems()).fetch, CONFIG, POST_ID, { ...ALL, query });

    assert.deepEqual(ids(page), expected);
    assert.equal(page.total_matches, expected.length);
  });
}

for (const [dates, expected] of [
  [{ min_date: '2026-03-28' }, ['47617904']],
  [{ max_date: '2026-03-27' }, ['47546447', '47548311', '47543168', '47545725', '47542672', '47545712']],
  [{ min_date: '2026-03-28', max_date: '2026-04-01' }, []],
] as const) {
  test(`dates ${JSON.stringify(dates)} keep the comments written on and between those UTC days`, async () => {
    const page = await searchPostComments(itemsFetch(recordedItems()).fetch, CONFIG, POST_ID, { ...ALL, ...dates });

    assert.deepEqual(ids(page), expected);
  });
}

test('pages through the comments', async () => {
  const page = await searchPostComments(itemsFetch(recordedItems()).fetch, CONFIG, POST_ID, { query: '', page: 2, hits_per_page: 3 });

  assert.deepEqual(ids(page), ['47617904']);
  assert.equal(page.total_matches, 7);
  assert.equal(page.page, 2);
  assert.equal(page.pages, 3);
});

test('skips deleted and dead comments but keeps their replies', async () => {
  const items = recordedItems();
  items['47542672'] = { deleted: true, id: 47542672, kids: [47545712], parent: 47542553, time: 1774619548, type: 'comment' };
  items['47543168'] = { ...items['47543168'], dead: true };

  const page = await searchPostComments(itemsFetch(items).fetch, CONFIG, POST_ID, ALL);

  assert.deepEqual(ids(page), ['47546447', '47548311', '47545725', '47545712', '47617904']);
});

test('keeps at most max_concurrent_requests requests in flight', async () => {
  const items = recordedItems();
  let inFlight = 0;
  let mostInFlight = 0;
  const { fetch } = fakeFetch(async (url) => {
    inFlight += 1;
    mostInFlight = Math.max(mostInFlight, inFlight);
    await new Promise((resolve) => setTimeout(resolve, 5));
    inFlight -= 1;
    return Response.json(items[itemId(url)]);
  });
  const config = { ...CONFIG, discussions: { ...CONFIG.discussions, max_concurrent_requests: 2 } };

  await searchPostComments(fetch, config, POST_ID, ALL);

  assert.equal(mostInFlight, 2);
});

test('fails for an id that is not on Hacker News', async () => {
  await assert.rejects(searchPostComments(itemsFetch({}).fetch, CONFIG, '999999999', ALL), /Hacker News has no item 999999999/);
});

test('fails for the id of a comment', async () => {
  await assert.rejects(searchPostComments(itemsFetch(recordedItems()).fetch, CONFIG, '47542672', ALL), /47542672 is a comment, not a post/);
});

test('fails when the API answers with an HTTP error', async () => {
  const { fetch } = fakeFetch(async () => new Response('Service Unavailable', { status: 503 }));

  await assert.rejects(searchPostComments(fetch, CONFIG, POST_ID, ALL), /HTTP 503/);
});

test('rejects min_date after max_date, without requests', async () => {
  const { fetch, requests } = itemsFetch(recordedItems());

  await assert.rejects(
    searchPostComments(fetch, CONFIG, POST_ID, { ...ALL, min_date: '2026-04-02', max_date: '2026-03-27' }),
    /min_date 2026-04-02 is after max_date 2026-03-27/,
  );
  assert.equal(requests.length, 0);
});
