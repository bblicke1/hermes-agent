// Synthetic terminal proof for live sections; no gateway, credentials, or model calls.
import { AlternateScreen, Box, renderSync, Text, useInput } from '@hermes/ink'
import React, { useState } from 'react'

import { MessageLine } from '../../src/components/messageLine.js'
import { ToolTrail } from '../../src/components/thinking.js'
import { DEFAULT_THEME } from '../../src/theme.js'
import type { Msg, SectionVisibility, SubagentProgress } from '../../src/types.js'

const sections: SectionVisibility = { thinking: 'live', tools: 'live', subagents: 'live', activity: 'live' }
const msg: Msg = {
  kind: 'trail',
  role: 'system',
  text: '',
  thinking: 'Synthetic reasoning: write a demo file.',
  tools: ['Terminal("printf test") ✓', 'Write File("demo.txt") ✓'],
  inlineDiffs: [{ toolIndex: 1, body: '--- a/demo.txt\n+++ b/demo.txt\n@@ -1 +1 @@\n-old\n+new' }]
}
const subagents: SubagentProgress[] = [
  {
    id: 'synthetic-child',
    depth: 0,
    goal: 'Synthetic helper',
    index: 0,
    parentId: null,
    status: 'completed',
    taskCount: 1,
    thinking: ['Helper reasoning.'],
    tools: [],
    toolCount: 0,
    notes: ['Helper note.']
  }
]
function Proof() {
  const [running, setRunning] = useState(true)
  useInput(input => {
    if (input === 'c') setRunning(false)
    if (input === 'r') setRunning(true)
    if (input === 'q') process.exit(0)
  })
  return (
    <AlternateScreen>
      <Box flexDirection="column">
        <Text>
          SYNTHETIC PROOF — {running ? 'RUNNING' : 'COMPLETED'} (c: complete, r: restart, q: quit; click chevrons)
        </Text>
        <MessageLine
          cols={process.stdout.columns ?? 90}
          liveDetails={running}
          msg={msg}
          sections={sections}
          t={DEFAULT_THEME}
        />
        <ToolTrail
          activity={[{ id: 1, text: 'Synthetic activity stream', tone: 'info' }]}
          subagents={subagents}
          turnRunning={running}
          sections={sections}
          t={DEFAULT_THEME}
        />
      </Box>
    </AlternateScreen>
  )
}
renderSync(<Proof />)
