<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Breadcrumb from 'primevue/breadcrumb'

const { t } = useI18n()
const route = useRoute()

interface BreadcrumbItem {
  label: string
  route?: string
}

const home = computed<BreadcrumbItem>(() => ({
  label: t('nav.title'),
  route: '/',
}))

const routeLabelMap: Record<string, string> = {
  upload: 'nav.upload',
  bodies: 'nav.bodies',
  'body-detail': 'nav.bodies',
  'calc-launch': 'nav.launch',
  'calc-hohmann': 'nav.hohmann',
  'calc-tsiolkovsky': 'nav.tsiolkovsky',
  map: 'nav.map',
  settings: 'nav.settings',
}

const items = computed<BreadcrumbItem[]>(() => {
  const routeName = String(route.name ?? '')
  const key = routeLabelMap[routeName]
  if (!key) return []

  const crumbs: BreadcrumbItem[] = [{ label: t(key) }]

  if (routeName === 'body-detail' && route.params.name) {
    crumbs.push({ label: String(route.params.name) })
  }

  return crumbs
})
</script>

<template>
  <div class="app-header">
    <Breadcrumb :home="home" :model="items" class="app-breadcrumb" />
  </div>
</template>

<style scoped>
.app-header {
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--p-surface-border, #374151);
  background: var(--p-surface-800, #1f2937);
}

.app-breadcrumb {
  background: transparent;
  border: none;
  padding: 0;
}
</style>
