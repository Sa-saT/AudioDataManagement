// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  modules: ['@nuxtjs/tailwindcss', '@pinia/nuxt'],
  // Nuxt auto-overrides public.apiBaseUrl from NUXT_PUBLIC_API_BASE_URL env var
  runtimeConfig: {
    public: {
      apiBaseUrl: 'http://localhost:8000',
    },
  },
  tailwindcss: {
    cssPath: '~/assets/css/main.css',
    configPath: '~~/tailwind.config.ts',
  },
  app: {
    head: {
      title: 'Pathfinder',
      link: [
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap',
        },
      ],
    },
  },
})
