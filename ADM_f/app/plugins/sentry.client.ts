import * as Sentry from '@sentry/vue'

export default defineNuxtPlugin((nuxtApp) => {
  const { sentryDsn, environment } = useRuntimeConfig().public
  if (!sentryDsn) return  // DSN 未設定 (開発環境) は何もしない

  Sentry.init({
    app: nuxtApp.vueApp,
    dsn: sentryDsn,
    environment,
    // 本番: ページ遷移の 5% をトレース
    tracesSampleRate: 0.05,
    // Vue コンポーネントのエラー境界を有効化
    attachProps: true,
    logErrors: true,
  })
})
