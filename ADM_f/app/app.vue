<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <SplashIntro />
</template>

<script setup lang="ts">
// 起動時にスプラッシュ画像を preload (フリッカー防止)
useHead({
  link: [
    { rel: 'preload', as: 'image', href: '/recoding_studio.png' },
  ],
})
</script>
