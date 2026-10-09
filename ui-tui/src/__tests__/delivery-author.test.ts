import { expect, it } from 'vitest'
import { toTranscriptMessages } from '../domain/messages.js'

it('restores a delivery with a bot prefix while both messages keep the user role', () => {
  expect(toTranscriptMessages([
    { role: 'user', text: 'Brad request' },
    { role: 'user', text: '[Bot delivery: BOT Alpha; not the human user]\nwork order',
      display_metadata: { author: { id: 'bot:alpha', name: 'Alpha', is_bot: true } } }
  ]).map(({ role, text }) => [role, text])).toEqual([
    ['user', 'Brad request'], ['user', '[Bot delivery: BOT Alpha; not the human user]\nwork order']
  ])
})
