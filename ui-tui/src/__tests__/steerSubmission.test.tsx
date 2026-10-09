import { PassThrough } from 'stream'

import { renderSync } from '@hermes/ink'
import React from 'react'
import { beforeEach, expect, it, vi } from 'vitest'

import { turnController } from '../app/turnController.js'
import { resetTurnState } from '../app/turnStore.js'
import { patchUiState, resetUiState } from '../app/uiStore.js'
import { useSubmission, type UseSubmissionOptions } from '../app/useSubmission.js'

beforeEach(() => {
  resetUiState()
  resetTurnState()
  turnController.fullReset()
  patchUiState({ sid: 'test', busy: true, busyInputMode: 'steer' })
})
it.each(['queued', 'rejected', 'error'])(
  'typed busy steering handles %s through the mounted submission hook',
  async status => {
    const request =
      status === 'error' ? vi.fn().mockRejectedValue(new Error('offline')) : vi.fn().mockResolvedValue({ status })
    const appendMessage = vi.fn(),
      enqueue = vi.fn(),
      sys = vi.fn()
    const opts = {
      appendMessage,
      gw: { request },
      sys,
      composerActions: { enqueue, clearIn: vi.fn(), pushHistory: vi.fn() },
      composerRefs: {
        tokensRef: { current: [{ kind: 'paste', label: '[[ paste ]]', text: 'full correction' }] },
        queueEditRef: { current: null }
      },
      composerState: { input: '', inputBuf: [] },
      submitRef: { current: vi.fn() },
      slashRef: { current: vi.fn() },
      setLastUserMsg: vi.fn()
    } as unknown as UseSubmissionOptions
    let submit: (text: string) => void = () => {}
    function Harness() {
      submit = useSubmission(opts).dispatchSubmission
      return null
    }
    const stdout = Object.assign(new PassThrough(), { columns: 80, rows: 24, isTTY: false })
    stdout.resume()
    const instance = renderSync(<Harness />, {
      stdout: stdout as unknown as NodeJS.WriteStream,
      stdin: new PassThrough() as unknown as NodeJS.ReadStream,
      patchConsole: false
    })
    try {
      submit('[[ paste ]]')
      await new Promise(resolve => setTimeout(resolve, 30))
      expect(request).toHaveBeenCalledExactlyOnceWith('session.steer', { session_id: 'test', text: 'full correction' })
      if (status === 'queued') {
        expect(appendMessage).toHaveBeenCalledExactlyOnceWith({ role: 'user', text: '[[ paste ]]', steered: true })
        expect(enqueue).not.toHaveBeenCalled()
        expect(sys).not.toHaveBeenCalled()
      } else {
        expect(appendMessage).not.toHaveBeenCalled()
        expect(enqueue).toHaveBeenCalledExactlyOnceWith('full correction', '[[ paste ]]')
        expect(sys).toHaveBeenCalledWith(
          expect.stringContaining(status === 'error' ? 'steer failed' : 'steer rejected')
        )
      }
    } finally {
      instance.unmount()
      instance.cleanup()
    }
  }
)
