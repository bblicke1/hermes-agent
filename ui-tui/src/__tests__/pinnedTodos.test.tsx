import { PassThrough } from 'stream'

import { renderSync } from '@hermes/ink'
import React from 'react'
import { beforeEach, expect, it } from 'vitest'

import type { Frame } from '../../packages/hermes-ink/src/ink/frame.js'
import instances from '../../packages/hermes-ink/src/ink/instances.js'
import { cellAt } from '../../packages/hermes-ink/src/ink/screen.js'
import { GatewayProvider } from '../app/gatewayContext.js'
import { resetOverlayState } from '../app/overlayStore.js'
import { archiveTodosAtTurnEnd, patchTurnState, resetTurnState, toggleTodoCollapsed } from '../app/turnStore.js'
import { patchUiState, resetUiState } from '../app/uiStore.js'
import { AppLayout } from '../components/appLayout.js'
import { todoPanelRows } from '../lib/todo.js'
import type { TodoItem } from '../types.js'

import { gatewayStub, layoutProps } from './helpers/layoutFixture.js'

const settle = () => new Promise(resolve => setTimeout(resolve, 80))
const todos: TodoItem[] = Array.from({ length: 10 }, (_, i) => ({
  id: String(i),
  content: `task-${i} ${'long '.repeat(30)}`,
  status: 'pending'
}))
beforeEach(() => {
  resetTurnState()
  resetUiState()
  resetOverlayState()
})

it('pins a bounded checklist outside virtual history, reserves its viewport rows, collapses and hides only finished work', async () => {
  patchUiState({ busy: true, status: 'running', sid: 'test' })
  const stdout = Object.assign(new PassThrough(), { columns: 40, rows: 24, isTTY: false })
  stdout.resume()
  const stdin = Object.assign(new PassThrough(), { isTTY: true, setRawMode: () => {}, ref: () => {}, unref: () => {} })
  const props = {
    ...layoutProps,
    composer: { ...layoutProps.composer, cols: 40, input: 'composer-proof', empty: false }
  }
  const instance = renderSync(
    <GatewayProvider value={gatewayStub}>
      <AppLayout {...props} />
    </GatewayProvider>,
    {
      stdout: stdout as unknown as NodeJS.WriteStream,
      stdin: stdin as unknown as NodeJS.ReadStream,
      stderr: new PassThrough() as unknown as NodeJS.WriteStream,
      patchConsole: false
    }
  )
  const ink = instances.get(stdout as unknown as NodeJS.WriteStream)!
  const frame = () => {
    const { screen } = (ink as unknown as { frontFrame: Frame }).frontFrame
    return Array.from({ length: screen.height }, (_, y) =>
      Array.from({ length: screen.width }, (_, x) => cellAt(screen, x, y)?.char ?? '').join('')
    ).join('\n')
  }
  try {
    await settle()
    const base = props.transcript.scrollRef.current!.getViewportHeight()
    patchTurnState({ todos })
    await settle()
    expect(frame()).toContain('task-0')
    expect(frame()).toContain('+7 more')
    expect(frame().indexOf('task-0')).toBeLessThan(frame().indexOf('composer-proof'))
    expect(props.transcript.scrollRef.current!.getViewportHeight()).toBe(base - 6)
    expect(todoPanelRows(todos, false, 6)).toBe(6)
    toggleTodoCollapsed()
    await settle()
    expect(frame()).not.toContain('task-0')
    expect(props.transcript.scrollRef.current!.getViewportHeight()).toBe(base - 2)
    toggleTodoCollapsed()
    archiveTodosAtTurnEnd()
    patchUiState({ busy: false })
    await settle()
    expect(frame()).toContain('task-0')
    patchUiState({ busy: true })
    patchTurnState({ todos: todos.map(todo => ({ ...todo, status: 'completed' })) })
    await settle()
    expect(frame()).toContain('task-0')
    patchUiState({ busy: false })
    await settle()
    expect(frame()).not.toContain('task-0')
    expect(props.transcript.scrollRef.current!.getViewportHeight()).toBe(base)
    expect(archiveTodosAtTurnEnd()).toHaveLength(1)
  } finally {
    instance.unmount()
    instance.cleanup()
  }
})
