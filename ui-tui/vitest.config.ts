import { defineConfig } from 'vitest/config'

export default defineConfig({
  // Exercise this checkout's renderer rather than a reused dependency's stale build.
  resolve: {
    alias: { '@hermes/ink': new URL('./packages/hermes-ink/src/entry-exports.ts', import.meta.url).pathname }
  },
  test: {
    exclude: ['dist/**', 'node_modules/**']
  }
})
