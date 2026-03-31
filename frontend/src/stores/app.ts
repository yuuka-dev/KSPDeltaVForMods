import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { SupportedLocale } from '@/i18n'

export const useAppStore = defineStore('app', () => {
  const isLoaded = ref(false)
  const locale = ref<SupportedLocale>(
    (localStorage.getItem('locale') as SupportedLocale) ?? 'ja',
  )

  watch(locale, (newLocale) => {
    localStorage.setItem('locale', newLocale)
  })

  function setLoaded(value: boolean): void {
    isLoaded.value = value
  }

  function setLocale(newLocale: SupportedLocale): void {
    locale.value = newLocale
  }

  return { isLoaded, locale, setLoaded, setLocale }
})
