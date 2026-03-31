<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import FileUpload, { type FileUploadSelectEvent } from 'primevue/fileupload'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import { useToast } from 'primevue/usetoast'
import { useApi } from '@/composables/useApi'
import { useBodiesStore } from '@/stores/bodies'
import { useSystemStore } from '@/stores/system'
import { useAppStore } from '@/stores/app'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const api = useApi()
const bodiesStore = useBodiesStore()
const systemStore = useSystemStore()
const appStore = useAppStore()

const uploading = ref(false)
const scanning = ref(false)
const gamedataPath = ref('')

async function onFileSelect(event: FileUploadSelectEvent): Promise<void> {
  const file = event.files[0]
  if (!file) return

  uploading.value = true
  try {
    const uploadResult = await api.uploadConfig(file)
    await afterSuccess(uploadResult.count)
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: t('upload.error'),
      detail: err instanceof Error ? err.message : String(err),
      life: 6000,
    })
  } finally {
    uploading.value = false
  }
}

async function onScan(): Promise<void> {
  if (!gamedataPath.value.trim()) return

  scanning.value = true
  try {
    const scanResult = await api.scan({ gamedata_path: gamedataPath.value.trim(), exclude_dirs: [] })
    await afterSuccess(scanResult.count)
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: t('upload.error'),
      detail: err instanceof Error ? err.message : String(err),
      life: 6000,
    })
  } finally {
    scanning.value = false
  }
}

async function afterSuccess(count: number): Promise<void> {
  const bodies = await api.listBodies()
  bodiesStore.setBodies(bodies)

  try {
    const sys = await api.getSystem()
    systemStore.setSystem(sys)
  } catch {
    // system endpoint may not be available; non-fatal
  }

  appStore.setLoaded(true)
  toast.add({
    severity: 'success',
    summary: t('upload.title'),
    detail: t('upload.success', { count }),
    life: 4000,
  })
  await router.push({ name: 'bodies' })
}
</script>

<template>
  <div class="upload-page">
    <h1>{{ t('upload.title') }}</h1>

    <div class="upload-card">
      <FileUpload
        mode="basic"
        accept=".cfg"
        :auto="false"
        :max-file-size="10000000"
        :choose-label="t('upload.dropzone')"
        @select="onFileSelect"
      />
    </div>

    <ProgressBar v-if="uploading" mode="indeterminate" class="upload-progress" />
    <p v-if="uploading" class="upload-scanning">{{ t('upload.scanning') }}</p>

    <div class="upload-card scan-card">
      <h2>{{ t('upload.scanTitle') }}</h2>
      <div class="scan-row">
        <label class="scan-label" for="gamedata-path">{{ t('upload.scanPath') }}</label>
        <InputText
          id="gamedata-path"
          v-model="gamedataPath"
          class="scan-input"
          :placeholder="t('upload.scanPlaceholder')"
        />
        <Button
          :label="t('upload.scanButton')"
          :disabled="scanning || !gamedataPath.trim()"
          @click="onScan"
        />
      </div>
      <ProgressBar v-if="scanning" mode="indeterminate" class="upload-progress" />
      <p v-if="scanning" class="upload-scanning">{{ t('upload.scanning') }}</p>
    </div>
  </div>
</template>

<style scoped>
.upload-page {
  max-width: 600px;
  margin: 4rem auto;
  text-align: center;
}

.upload-card {
  margin: 2rem auto;
  display: flex;
  justify-content: center;
}

.scan-card {
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.scan-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  flex-wrap: wrap;
  justify-content: center;
}

.scan-label {
  white-space: nowrap;
  font-weight: 500;
}

.scan-input {
  flex: 1;
  min-width: 240px;
}

.upload-progress {
  margin-top: 1.5rem;
}

.upload-scanning {
  margin-top: 0.75rem;
  color: var(--p-text-muted-color, #9ca3af);
}
</style>
