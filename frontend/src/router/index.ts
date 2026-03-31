import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore } from '@/stores/app'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'upload',
      component: () => import('@/components/upload/ConfigUpload.vue'),
    },
    {
      path: '/bodies',
      name: 'bodies',
      component: () => import('@/components/bodies/BodyList.vue'),
      meta: { requiresConfig: true },
    },
    {
      path: '/bodies/:name',
      name: 'body-detail',
      component: () => import('@/components/bodies/BodyDetail.vue'),
      meta: { requiresConfig: true },
    },
    {
      path: '/calc/launch',
      name: 'calc-launch',
      component: () => import('@/components/calc/LaunchCalc.vue'),
      meta: { requiresConfig: true },
    },
    {
      path: '/calc/hohmann',
      name: 'calc-hohmann',
      component: () => import('@/components/calc/HohmannCalc.vue'),
      meta: { requiresConfig: true },
    },
    {
      path: '/calc/tsiolkovsky',
      name: 'calc-tsiolkovsky',
      component: () => import('@/components/calc/TsiolkovskyCalc.vue'),
      meta: { requiresConfig: true },
    },
    {
      path: '/map',
      name: 'map',
      component: () => import('@/components/map/DvRouteMap.vue'),
      meta: { requiresConfig: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/components/settings/SettingsPage.vue'),
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresConfig) {
    const appStore = useAppStore()
    if (!appStore.isLoaded) {
      return { name: 'upload' }
    }
  }
  return true
})

export default router
