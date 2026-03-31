import { createI18n } from 'vue-i18n'
import ja from './ja.json'
import en from './en.json'
import id from './id.json'

export type SupportedLocale = 'ja' | 'en' | 'id'

export const SUPPORTED_LOCALES: readonly SupportedLocale[] = ['ja', 'en', 'id'] as const

export const LOCALE_LABELS: Record<SupportedLocale, string> = {
  ja: '日本語',
  en: 'English',
  id: 'Bahasa Indonesia',
}

function detectLocale(): SupportedLocale {
  const stored = localStorage.getItem('locale')
  if (stored && SUPPORTED_LOCALES.includes(stored as SupportedLocale)) {
    return stored as SupportedLocale
  }
  const browserLang = navigator.language.split('-')[0]
  if (SUPPORTED_LOCALES.includes(browserLang as SupportedLocale)) {
    return browserLang as SupportedLocale
  }
  return 'ja'
}

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: { ja, en, id },
})

export default i18n
