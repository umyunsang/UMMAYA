import { z } from 'zod/v4'
import { lazySchema } from '../../utils/lazySchema.js'
import { sourceVerificationSchema } from '../WebFetchTool/sourceVerification.js'

export const inputSchema = lazySchema(() =>
  z.strictObject({
    query: z.string().min(2).describe('The search query to use'),
    allowed_domains: z
      .array(z.string())
      .optional()
      .describe('Only include search results from these domains'),
    blocked_domains: z
      .array(z.string())
      .optional()
      .describe('Never include search results from these domains'),
  }),
)
export type InputSchema = ReturnType<typeof inputSchema>
export type Input = z.infer<InputSchema>

const searchHitSchema = z.object({
  title: z.string().describe('The title of the search result'),
  url: z.string().describe('The URL of the search result'),
})

export const searchResultSchema = lazySchema(() =>
  z.object({
    tool_use_id: z.string().describe('ID of the tool use'),
    content: z.array(searchHitSchema).describe('Array of search hits'),
  }),
)
export type SearchResult = z.infer<ReturnType<typeof searchResultSchema>>

export const outputSchema = lazySchema(() =>
  z.object({
    query: z.string().describe('The search query that was executed'),
    results: z
      .array(z.union([searchResultSchema(), z.string()]))
      .describe('Search results and/or text commentary from the model'),
    durationSeconds: z
      .number()
      .describe('Time taken to complete the search operation'),
    sourceVerification: sourceVerificationSchema.optional(),
  }),
)
export type OutputSchema = ReturnType<typeof outputSchema>
export type Output = z.infer<OutputSchema>
