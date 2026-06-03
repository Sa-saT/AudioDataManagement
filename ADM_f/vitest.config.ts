import path from 'node:path'
import { defineConfig } from 'vitest/config'

// import.meta.client / server はヌクト専用フラグ。
// vitest の define では置換されないため、Vite transform plugin で直接書き換える。
const nuxtCompatPlugin = {
  name: 'nuxt-meta-compat',
  transform(code: string, id: string) {
    if (!id.includes('node_modules') && (code.includes('import.meta.client') || code.includes('import.meta.server'))) {
      return code.replace(/import\.meta\.client/g, 'true').replace(/import\.meta\.server/g, 'false')
    }
  },
}

export default defineConfig({
  plugins: [nuxtCompatPlugin],
  test: {
    environment: 'happy-dom',
    include: ['app/__tests__/**/*.test.ts'],
    setupFiles: ['./app/__tests__/setup.ts'],
  },
  resolve: {
    alias: { '~': path.resolve(__dirname, 'app') },
  },
})
