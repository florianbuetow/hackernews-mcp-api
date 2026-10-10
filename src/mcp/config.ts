/** The settings the MCP server shares with `just search`, loaded from config/search.toml. */

import { readFileSync } from 'node:fs';

import { parse } from 'smol-toml';
import { z } from 'zod';

const ConfigSchema = z.object({
  http: z.strictObject({
    user_agent: z.string(),
    timeout_seconds: z.number().positive(),
  }),
  algolia: z.strictObject({
    application_id: z.string(),
    api_key: z.string(),
    index: z.string(),
    params: z.record(z.string(), z.json()),
  }),
  discussions: z.strictObject({
    item_url: z.string(),
    max_concurrent_requests: z.int().positive(),
  }),
});

export type Config = z.infer<typeof ConfigSchema>;

/** Load the [http], [algolia], and [discussions] settings, rejecting missing and unknown ones; [output] belongs to `just search`. */
export function loadConfig(path: string): Config {
  return ConfigSchema.parse(parse(readFileSync(path, 'utf8')));
}
