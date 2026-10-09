import { expect, it, vi } from 'vitest'
import { toChatMessages } from './chat-messages/hydration'

// Filesystem/media UI dependencies are outside this transcript-only test.
vi.mock('@/lib/media', () => ({ mediaDisplayLabel: (value: string) => value, mediaMarkdownHref: (value: string) => value }))

vi.mock('@/lib/connector-tools', () => ({ TOOL_LABELS_ARG: '__tool_labels' }))

it.each([false, true])('restores bot provenance with metadata serialized=%s', serialized => {
  const metadata = { author: { id: 'bot:alpha', name: 'Alpha', is_bot: true } }
  const messages = toChatMessages([
    { role: 'user', content: 'Brad request', timestamp: 1 },
    { role: 'user', content: '[Bot delivery: BOT Alpha; not the human user]\nwork order', timestamp: 2,
      display_metadata: serialized ? JSON.stringify(metadata) : metadata }
  ])
  expect(messages.map(message => message.role)).toEqual(['user', 'user'])
  expect(messages[1].parts).toContainEqual({ type: 'text', text: '[Bot delivery: BOT Alpha; not the human user]\nwork order', timestamp: 2 })
})
