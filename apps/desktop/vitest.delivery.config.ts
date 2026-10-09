// Pure transcript conversion: no Electron, React transform, or browser required.
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: { environment: 'node', include: ['src/lib/chat-messages.delivery-author.test.ts'] }
})
