import { expect, it } from 'vitest'
import { toTranscriptMessages } from '../domain/messages.js'

it('restores a delivery with its author and a system glyph while Brad keeps the user role', () => {
  expect(toTranscriptMessages([
    { role: 'user', text: 'Brad request' },
    { role: 'system', text: 'Alpha: work order', display_kind: 'delivery',
      display_metadata: { author: { id: 'bot:alpha', name: 'Alpha', is_bot: true } } }
  ]).map(({ role, text }) => [role, text])).toEqual([
    ['user', 'Brad request'], ['system', 'Alpha: work order']
  ])
})
