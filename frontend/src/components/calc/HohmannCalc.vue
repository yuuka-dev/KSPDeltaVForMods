<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useApi } from '@/composables/useApi'
import { useBodiesStore } from '@/stores/bodies'
import { useCalcStore } from '@/stores/calc'
import type { HohmannResponse } from '@/types/api'

const { t } = useI18n()
const toast = useToast()
const api = useApi()
const bodiesStore = useBodiesStore()
const calcStore = useCalcStore()

const selectedBody = ref<string | null>(null)
const parkingAltitude = ref<number>(80000)
const targetSma = ref<number>(1000000)
const calculating = ref(false)
const inward = ref(false)

interface ResultRow {
  label: string
  value: string
}

const resultRows = ref<ResultRow[]>([])

const bodyOptions = bodiesStore.bodies.map((b) => ({ label: b.display_name, value: b.name }))

function formatTime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

async function calculate(): Promise<void> {
  if (!selectedBody.value) {
    toast.add({ severity: 'warn', summary: t('hohmann.title'), detail: t('hohmann.bodyName'), life: 3000 })
    return
  }

  calculating.value = true
  try {
    const result: HohmannResponse = await api.calcHohmann({
      body_name: selectedBody.value,
      parking_altitude: parkingAltitude.value,
      target_sma: targetSma.value,
    })
    calcStore.setHohmannResult(result)
    inward.value = result.inward

    resultRows.value = [
      { label: t('hohmann.departureDv'), value: `${result.departure_dv.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('hohmann.arrivalDv'), value: `${result.arrival_dv.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('hohmann.totalDv'), value: `${result.total_dv.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('hohmann.transferTime'), value: formatTime(result.transfer_time) },
    ]
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: err instanceof Error ? err.message : String(err),
      life: 5000,
    })
  } finally {
    calculating.value = false
  }
}
</script>

<template>
  <div class="calc-page">
    <h1>{{ t('hohmann.title') }}</h1>

    <div class="calc-form">
      <div class="form-row">
        <label>{{ t('hohmann.bodyName') }}</label>
        <Select
          v-model="selectedBody"
          :options="bodyOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('hohmann.bodyName')"
          style="width: 260px"
        />
      </div>

      <div class="form-row">
        <label>{{ t('hohmann.parkingAltitude') }}</label>
        <InputNumber
          v-model="parkingAltitude"
          :min="0"
          :step="1000"
          style="width: 200px"
        />
      </div>

      <div class="form-row">
        <label>{{ t('hohmann.targetSma') }}</label>
        <InputNumber
          v-model="targetSma"
          :min="0"
          :step="10000"
          style="width: 200px"
        />
      </div>

      <Button
        :label="t('hohmann.calculate')"
        icon="pi pi-sync"
        :loading="calculating"
        @click="calculate"
      />
    </div>

    <template v-if="resultRows.length > 0">
      <Tag v-if="inward" severity="warn" :value="t('hohmann.inward')" style="margin-bottom: 0.75rem" />

      <DataTable :value="resultRows" class="result-table">
        <Column field="label" header="" style="width: 50%" />
        <Column field="value" header="" style="width: 50%; text-align: right; font-family: monospace" />
      </DataTable>
    </template>
  </div>
</template>

<style scoped>
.calc-page {
  max-width: 700px;
}

.calc-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 2rem;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.form-row label {
  width: 260px;
  color: var(--p-text-muted-color, #9ca3af);
}

.result-table {
  margin-top: 1rem;
}
</style>
