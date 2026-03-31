<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Menu from 'primevue/menu'
import { useAppStore } from '@/stores/app'

const { t } = useI18n()
const router = useRouter()
const appStore = useAppStore()

interface MenuItem {
  label?: string
  icon?: string
  command?: () => void
  disabled?: boolean
  separator?: boolean
  class?: string
}

const items = computed<MenuItem[]>(() => [
  {
    label: t('nav.upload'),
    icon: 'pi pi-upload',
    command: () => router.push({ name: 'upload' }),
  },
  { separator: true },
  {
    label: t('nav.bodies'),
    icon: 'pi pi-globe',
    disabled: !appStore.isLoaded,
    command: () => appStore.isLoaded && router.push({ name: 'bodies' }),
  },
  {
    label: t('nav.map'),
    icon: 'pi pi-map',
    disabled: !appStore.isLoaded,
    command: () => appStore.isLoaded && router.push({ name: 'map' }),
  },
  { separator: true },
  {
    label: t('nav.launch'),
    icon: 'pi pi-arrow-up',
    disabled: !appStore.isLoaded,
    command: () => appStore.isLoaded && router.push({ name: 'calc-launch' }),
  },
  {
    label: t('nav.hohmann'),
    icon: 'pi pi-sync',
    disabled: !appStore.isLoaded,
    command: () => appStore.isLoaded && router.push({ name: 'calc-hohmann' }),
  },
  {
    label: t('nav.tsiolkovsky'),
    icon: 'pi pi-calculator',
    disabled: !appStore.isLoaded,
    command: () => appStore.isLoaded && router.push({ name: 'calc-tsiolkovsky' }),
  },
  { separator: true },
  {
    label: t('nav.settings'),
    icon: 'pi pi-cog',
    command: () => router.push({ name: 'settings' }),
  },
])
</script>

<template>
  <div class="app-sidebar">
    <div class="app-sidebar-title">
      <span class="pi pi-star-fill" style="margin-right: 0.5rem" />
      {{ t('nav.title') }}
    </div>
    <Menu :model="items" class="app-sidebar-menu" />
  </div>
</template>

<style scoped>
.app-sidebar {
  width: 220px;
  min-width: 220px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--p-surface-border, #374151);
  background: var(--p-surface-900, #111827);
}

.app-sidebar-title {
  padding: 1rem;
  font-weight: 700;
  font-size: 0.9rem;
  letter-spacing: 0.05em;
  color: var(--p-primary-400, #818cf8);
  border-bottom: 1px solid var(--p-surface-border, #374151);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.app-sidebar-menu {
  border: none;
  background: transparent;
  width: 100%;
  flex: 1;
}
</style>
