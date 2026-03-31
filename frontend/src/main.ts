import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import ToastService from 'primevue/toastservice'
import 'primeicons/primeicons.css'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { waitForBackend } from './composables/useApi'
import './assets/styles/main.css'

async function bootstrap(): Promise<void> {
  // In production (Tauri), wait for the Python backend to start
  if (!import.meta.env.DEV) {
    const ready = await waitForBackend()
    if (!ready) {
      const el = document.getElementById('app')
      if (el) {
        el.textContent =
          'Failed to connect to Python backend. Ensure Python 3.10+ is installed and on PATH.'
        el.style.color = '#ef4444'
        el.style.padding = '2rem'
        el.style.fontFamily = 'sans-serif'
      }
      return
    }
  }

  const app = createApp(App)

  app.use(createPinia())
  app.use(router)
  app.use(i18n)
  app.use(PrimeVue, {
    theme: {
      preset: Aura,
      options: {
        darkModeSelector: '.app-dark',
      },
    },
  })
  app.use(ToastService)

  app.mount('#app')
}

bootstrap()
