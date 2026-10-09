import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ComposerToken } from '../app/interfaces.js'
import { submitSteer } from '../app/submissionCore.js'
import { getUiState, patchUiState, resetUiState } from '../app/uiStore.js'
import type { GatewayClient } from '../gatewayClient.js'
import { prepareSubmission, shouldInterpolateSubmission } from '../app/useSubmission.js'

describe('prepareSubmission', () => {
  it('keeps the collapsed paste for display and expands the model payload', () => {
    const label = '[[ first.. [3 lines] .. last ]]'
    const tokens: ComposerToken[] = [{ kind: 'paste', label, text: 'first\nmiddle\nlast' }]

    expect(prepareSubmission(`review this: ${label}`, tokens)).toEqual({
      display: `review this: ${label}`,
      text: 'review this: first\nmiddle\nlast'
    })
  })

  it('does not execute interpolation syntax hidden inside pasted content', () => {
    const label = '[[ copied log [1 lines] ]]'
    const tokens: ComposerToken[] = [{ kind: 'paste', label, text: 'untrusted {!touch /tmp/pwned}' }]
    const submission = prepareSubmission(label, tokens)

    expect(shouldInterpolateSubmission(submission.display)).toBe(false)
    expect(submission.text).toContain('{!touch /tmp/pwned}')
  })
})

describe('visible interpolation combined with a collapsed paste', () => {
  it('routes to interpolation when {!...} is visible in the composer alongside a paste token', () => {
    const label = '[[ log [2 lines] ]]'

    expect(shouldInterpolateSubmission(`show {!date} for ${label}`)).toBe(true)
  })

  // The interpolation branch of dispatchSubmission submits
  //   send(prepareSubmission(text, tokens).text, true, text, identity)
  // where `text` is interpolate()'s output: the visible {!...} already resolved,
  // with the collapsed paste label still intact. This asserts both halves of
  // that composition so the transcript shows resolved interpolation + the
  // compact paste, while the model receives resolved interpolation + the full
  // expanded paste.
  it('display keeps resolved interpolation and the compact paste; payload expands the paste', () => {
    const label = '[[ log [2 lines] ]]'
    const tokens: ComposerToken[] = [{ kind: 'paste', label, text: 'line one\nline two' }]

    // interpolate() has resolved the visible {!date} -> "Tue" and left the paste label alone.
    const interpolated = `Tue for ${label}`
    const submission = prepareSubmission(interpolated, tokens)

    expect(submission.display).toBe(`Tue for ${label}`)
    expect(submission.display).not.toContain('{!')
    expect(submission.text).toBe('Tue for line one\nline two')
  })
})

describe('accepted steer transcript', () => {
  beforeEach(() => {
    resetUiState()
    patchUiState({ sid: 'test', busy: true })
  })
  it('appends the accepted display exactly once without clearing the live turn', async () => {
    const request = vi.fn().mockResolvedValue({ status: 'queued' })
    const appendMessage = vi.fn(),
      fallback = vi.fn()
    await submitSteer(
      'test',
      { text: 'expanded text', display: 'compact paste' },
      { gw: { request } as unknown as GatewayClient, appendMessage },
      fallback
    )
    expect(request).toHaveBeenCalledWith('session.steer', { session_id: 'test', text: 'expanded text' })
    expect(appendMessage).toHaveBeenCalledExactlyOnceWith({ role: 'user', text: 'compact paste', steered: true })
    expect(fallback).not.toHaveBeenCalled()
    expect(getUiState().busy).toBe(true)
  })
  it.each(['rejected', 'error'])('keeps the existing %s fallback and adds no steer row', async status => {
    const request =
      status === 'error' ? vi.fn().mockRejectedValue(new Error('offline')) : vi.fn().mockResolvedValue({ status })
    const appendMessage = vi.fn(),
      fallback = vi.fn()
    await submitSteer(
      'test',
      { text: 'correction', display: 'correction' },
      { gw: { request } as unknown as GatewayClient, appendMessage },
      fallback
    )
    expect(appendMessage).not.toHaveBeenCalled()
    expect(fallback).toHaveBeenCalledWith(
      status === 'error'
        ? 'steer failed — message queued for next turn'
        : 'steer rejected — message queued for next turn'
    )
  })
  it('does not append an old session acknowledgment to a new conversation', async () => {
    const request = vi.fn().mockImplementation(async () => {
      patchUiState({ sid: 'other' })
      return { status: 'queued' }
    })
    const appendMessage = vi.fn()
    await submitSteer(
      'test',
      { text: 'correction', display: 'correction' },
      { gw: { request } as unknown as GatewayClient, appendMessage },
      vi.fn()
    )
    expect(appendMessage).not.toHaveBeenCalled()
  })
})
