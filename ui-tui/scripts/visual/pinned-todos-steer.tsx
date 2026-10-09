// Actual AppLayout with synthetic history and a fake accepted steering RPC.
import { renderSync, useInput } from '@hermes/ink'
import React, { useState } from 'react'
import { GatewayProvider } from '../../src/app/gatewayContext.js'
import { submitSteer } from '../../src/app/submissionCore.js'
import { archiveTodosAtTurnEnd, patchTurnState, toggleTodoCollapsed } from '../../src/app/turnStore.js'
import { patchUiState } from '../../src/app/uiStore.js'
import { AppLayout } from '../../src/components/appLayout.js'
import { gatewayStub, layoutProps } from '../../src/__tests__/helpers/layoutFixture.js'
import type { Msg } from '../../src/types.js'

patchUiState({ busy: true, status: 'running', sid: 'synthetic' })
const todos = Array.from({ length: 10 }, (_, i) => ({
  id: String(i),
  content: `Synthetic task ${i}`,
  status: 'pending' as const
}))
patchTurnState({ todos })
function Proof() {
  const [messages, setMessages] = useState<Msg[]>(
    Array.from({ length: 180 }, (_, i) => ({ role: 'assistant', text: `Synthetic history ${i}` }))
  )
  useInput(input => {
    if (input === 'q') process.exit(0)
    if (input === 'x') toggleTodoCollapsed()
    if (input === 'u') layoutProps.transcript.scrollRef.current?.scrollTo(0)
    if (input === 'd') layoutProps.transcript.scrollRef.current?.scrollToBottom()
    if (input === 'c') patchTurnState({ todos: todos.map(todo => ({ ...todo, status: 'completed' })) })
    if (input === 'e') {
      archiveTodosAtTurnEnd()
      patchUiState({ busy: false, status: 'idle' })
    }
    if (input === 's')
      void submitSteer(
        'synthetic',
        { text: 'Synthetic correction', display: 'Synthetic correction' },
        {
          gw: { request: async () => ({ status: 'queued' }) } as never,
          appendMessage: msg => setMessages(rows => [...rows, msg])
        },
        () => {}
      ).then(() => setTimeout(() => layoutProps.transcript.scrollRef.current?.scrollToBottom(), 100))
  })
  const props = {
    ...layoutProps,
    composer: {
      ...layoutProps.composer,
      cols: process.stdout.columns ?? 80,
      empty: false,
      input: 'SYNTHETIC: u/d scroll; x collapse; s steer; c complete; e end; q quit'
    },
    transcript: {
      ...layoutProps.transcript,
      historyItems: messages,
      virtualRows: messages.map((msg, index) => ({ key: String(index), index, msg })),
      virtualHistory: { ...layoutProps.transcript.virtualHistory, end: messages.length }
    }
  }
  return (
    <GatewayProvider value={gatewayStub}>
      <AppLayout {...props} />
    </GatewayProvider>
  )
}
renderSync(<Proof />)
