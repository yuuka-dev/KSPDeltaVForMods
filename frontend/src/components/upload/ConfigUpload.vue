<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import FileUpload, { type FileUploadSelectEvent } from 'primevue/fileupload'
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

async function onFileSelect(event: FileUploadSelectEvent): Promise<void> {
  const file = event.files[0]
  if (!file) return

  uploading.value = true
  try {
    const uploadResult = await api.uploadConfig(file)
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
      detail: t('upload.success', { count: uploadResult.count }),
      life: 4000,
    })
    await router.push({ name: 'bodies' })
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

.upload-progress {
  margin-top: 1.5rem;
}

.upload-scanning {
  margin-top: 0.75rem;
  color: var(--p-text-muted-color, #9ca3af);
}
</style>
