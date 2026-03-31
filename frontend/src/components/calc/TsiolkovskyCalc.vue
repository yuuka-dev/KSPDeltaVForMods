<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>
<template>
  <div>
    <h1>{{ t('tsiolkovsky.title') }}</h1>
  </div>
</template>
