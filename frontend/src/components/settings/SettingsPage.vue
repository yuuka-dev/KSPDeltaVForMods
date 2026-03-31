<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Select from 'primevue/select'
import { useAppStore } from '@/stores/app'
import { SUPPORTED_LOCALES, LOCALE_LABELS, type SupportedLocale } from '@/i18n'

const { t, locale: i18nLocale } = useI18n()
const appStore = useAppStore()

interface LocaleOption {
  label: string
  value: SupportedLocale
}

const localeOptions = computed<LocaleOption[]>(() =>
  SUPPORTED_LOCALES.map((code) => ({
    label: LOCALE_LABELS[code],
    value: code,
  })),
)

const selectedLocale = computed<SupportedLocale>({
  get: () => appStore.locale,
  set: (newLocale: SupportedLocale) => {
    appStore.setLocale(newLocale)
    i18nLocale.value = newLocale
  },
})
</script>

<template>
  <div class="settings-page">
    <h1>{{ t('settings.title') }}</h1>

    <div class="settings-section">
      <label class="settings-label">{{ t('settings.language') }}</label>
      <p class="settings-description">{{ t('settings.languageDescription') }}</p>
      <Select
        v-model="selectedLocale"
        :options="localeOptions"
        option-label="label"
        option-value="value"
        style="width: 220px"
      />
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 600px;
}

.settings-section {
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.settings-label {
  font-weight: 600;
  font-size: 1rem;
}

.settings-description {
  color: var(--p-text-muted-color, #9ca3af);
  margin: 0;
  font-size: 0.875rem;
}
</style>
