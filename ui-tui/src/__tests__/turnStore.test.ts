import { beforeEach, describe, expect, it } from 'vitest'

import {
  archiveDoneTodos,
  archiveTodosAtTurnEnd,
  getTurnState,
  patchTurnState,
  resetTurnState
} from '../app/turnStore.js'

describe('turnStore live progress helpers', () => {
  beforeEach(() => resetTurnState())

  it('archives completed todos into a transcript trail and clears the live anchor', () => {
    patchTurnState({
      todos: [
        { content: 'prep', id: 'prep', status: 'completed' },
        { content: 'serve', id: 'serve', status: 'completed' }
      ]
    })

    expect(archiveTodosAtTurnEnd()).toEqual([
      {
        kind: 'trail',
        role: 'system',
        text: '',
        todoCollapsedByDefault: true,
        todos: [
          { content: 'prep', id: 'prep', status: 'completed' },
          { content: 'serve', id: 'serve', status: 'completed' }
        ]
      }
    ])
    expect(getTurnState().todos).toEqual([])
  })

  it('keeps incomplete todos pinned between turns', () => {
    patchTurnState({
      todos: [
        { content: 'cook', id: 'cook', status: 'completed' },
        { content: 'serve', id: 'serve', status: 'in_progress' },
        { content: 'eat', id: 'eat', status: 'pending' }
      ]
    })

    const archived = archiveTodosAtTurnEnd()
    expect(archived).toEqual([])
    expect(getTurnState().todos.map(t => t.id)).toEqual(['cook', 'serve', 'eat'])
  })

  it('returns nothing when there are no todos at turn end', () => {
    expect(archiveTodosAtTurnEnd()).toEqual([])
    expect(archiveDoneTodos()).toEqual([])
  })
})
