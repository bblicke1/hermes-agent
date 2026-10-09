import { PassThrough } from 'stream'

import { renderSync } from '@hermes/ink'
import React from 'react'
import { describe, expect, it } from 'vitest'

import type { Frame } from '../../packages/hermes-ink/src/ink/frame.js'
import { cellAt } from '../../packages/hermes-ink/src/ink/screen.js'
import instances from '../../packages/hermes-ink/src/ink/instances.js'
import { ToolTrail } from '../components/thinking.js'
import { mergeToolShelfInto } from '../lib/liveProgress.js'
import type { SubagentProgress } from '../types.js'
import { DEFAULT_THEME } from '../theme.js'

const settle = () => new Promise(resolve => setTimeout(resolve, 80))

describe('turn-scoped live sections', () => {
  it.each(['section', 'global'] as const)(
    'opens %s live panels until completion and allows reopening the diff',
    async mode => {
      const stdout = Object.assign(new PassThrough(), { columns: 80, rows: 30, isTTY: false })
      const stdin = Object.assign(new PassThrough(), { isTTY: false })
      const stderr = new PassThrough()
      stdout.resume()
      const props = {
        sections:
          mode === 'section' ? ({ tools: 'live', thinking: 'live', activity: 'live', subagents: 'live' } as const) : {},
        detailsMode: mode === 'global' ? ('live' as const) : ('collapsed' as const),
        reasoning: 'reasoning-proof',
        reasoningActive: false,
        activity: [{ id: 1, text: 'Synthetic activity', tone: 'info' as const }],
        subagents: [
          {
            id: 'child',
            depth: 0,
            goal: 'Helper goal',
            index: 0,
            parentId: null,
            status: 'completed',
            taskCount: 1,
            thinking: [],
            tools: [],
            toolCount: 0,
            notes: []
          }
        ] satisfies SubagentProgress[],
        trail: ['Write File("demo.txt") ✓'],
        inlineDiffs: [{ toolIndex: 0, body: '--- a/demo.txt\n+++ b/demo.txt\n-old\n+new' }],
        t: DEFAULT_THEME
      }
      const instance = renderSync(<ToolTrail {...props} turnRunning />, {
        stdout: stdout as unknown as NodeJS.WriteStream,
        stdin: stdin as unknown as NodeJS.ReadStream,
        stderr: stderr as unknown as NodeJS.WriteStream,
        patchConsole: false
      })
      const ink = instances.get(stdout as unknown as NodeJS.WriteStream)!
      const frame = () => {
        const { screen } = (ink as unknown as { frontFrame: Frame }).frontFrame
        return Array.from({ length: screen.height }, (_, y) =>
          Array.from({ length: screen.width }, (_, x) => cellAt(screen, x, y)?.char ?? '').join('')
        ).join('\n')
      }
      try {
        await settle()
        expect(frame()).toContain('+new')
        expect(frame()).toContain('reasoning-proof')
        expect(frame()).toContain('Synthetic activity')
        expect(frame()).toContain('Helper goal')
        instance.rerender(<ToolTrail {...props} turnRunning={false} />)
        await settle()
        expect(frame()).toContain('▸ ')
        expect(frame()).not.toContain('+new')
        expect(frame()).not.toContain('reasoning-proof')
        expect(frame()).not.toContain('Synthetic activity')
        expect(frame()).not.toContain('Helper goal')
        ink.setAltScreenActive(true)
        await settle()
        expect(
          ink.dispatchClick(
            8,
            frame()
              .split('\n')
              .findIndex(row => row.includes('Tool calls'))
          )
        ).toBe(true)
        await settle()
        expect(frame()).toContain('+new')
      } finally {
        instance.unmount()
        instance.cleanup()
      }
    }
  )

  it('preserves diff ownership when adjacent tool shelves merge', () => {
    const merged = mergeToolShelfInto(
      { kind: 'trail', role: 'system', text: '', tools: ['Read ✓'] },
      { kind: 'trail', role: 'system', text: '', tools: ['Write ✓'], inlineDiffs: [{ toolIndex: 0, body: '+new' }] }
    )
    expect(merged.tools).toEqual(['Read ✓', 'Write ✓'])
    expect(merged.inlineDiffs).toEqual([{ toolIndex: 1, body: '+new' }])
  })
})
