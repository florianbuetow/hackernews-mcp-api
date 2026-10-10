/** What the search tools take and return, whichever Hacker News API answers them. */

const SECONDS_PER_DAY = 86_400;

export interface SearchRequest {
  query: string;
  min_date?: string | undefined; // YYYY-MM-DD, UTC, inclusive
  max_date?: string | undefined; // YYYY-MM-DD, UTC, inclusive
  page: number;
  hits_per_page: number;
}

export interface SearchPage<Hit> {
  total_matches: number;
  page: number;
  pages: number;
  hits: Hit[];
}

export interface Post {
  id: string;
  title: string;
  url: string | null;
  text: string | null; // HTML; only text posts have one
  hn_url: string;
  author: string;
  points: number;
  comments: number;
  created_at: string;
}

export interface Comment {
  id: string;
  hn_url: string;
  author: string;
  text: string; // HTML
  post_id: string;
  post_title: string;
  parent_id: string;
  created_at: string;
}

/** Seconds since the epoch: items created at or after `from` and before `until`; an absent bound does not limit. */
export interface CreatedRange {
  from: number | undefined;
  until: number | undefined;
}

/** The range of items created on minDate, maxDate, and the days between them. */
export function createdBetween(minDate: string | undefined, maxDate: string | undefined): CreatedRange {
  if (minDate !== undefined && maxDate !== undefined && minDate > maxDate) {
    throw new Error(`min_date ${minDate} is after max_date ${maxDate}`);
  }
  return {
    from: minDate === undefined ? undefined : startOfDay(minDate),
    until: maxDate === undefined ? undefined : startOfDay(maxDate) + SECONDS_PER_DAY,
  };
}

/** The item's page on Hacker News. */
export function hnUrl(id: string): string {
  return `https://news.ycombinator.com/item?id=${id}`;
}

/** Seconds since the epoch at midnight UTC of a YYYY-MM-DD date. */
function startOfDay(date: string): number {
  return Date.parse(`${date}T00:00:00Z`) / 1000;
}
