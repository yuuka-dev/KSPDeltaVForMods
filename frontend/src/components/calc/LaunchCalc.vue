<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { useToast } from 'primevue/usetoast'
import { useApi } from '@/composables/useApi'
import { useBodiesStore } from '@/stores/bodies'
import { useCalcStore } from '@/stores/calc'
import type { LaunchResponse } from '@/types/api'

const { t } = useI18n()
const toast = useToast()
const api = useApi()
const bodiesStore = useBodiesStore()
const calcStore = useCalcStore()

const selectedBody = ref<string | null>(null)
const targetAltitude = ref<number>(80000)
const calculating = ref(false)

interface ResultRow {
  label: string
  value: string
}

const resultRows = ref<ResultRow[]>([])

const bodyOptions = bodiesStore.bodies.map((b) => ({ label: b.display_name, value: b.name }))

async function calculate(): Promise<void> {
  if (!selectedBody.value) {
    toast.add({ severity: 'warn', summary: t('launch.title'), detail: t('launch.bodyName'), life: 3000 })
    return
  }

  calculating.value = true
  try {
    const result: LaunchResponse = await api.calcLaunch({
      body_name: selectedBody.value,
      target_altitude: targetAltitude.value,
    })
    calcStore.setLaunchResult(result)

    resultRows.value = [
      { label: t('launch.orbitalVelocity'), value: `${result.orbital_velocity.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('launch.gravityLoss'), value: `${result.gravity_loss.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('launch.dragLoss'), value: `${result.drag_loss.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('launch.totalIdeal'), value: `${result.total_ideal.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('launch.totalRocket'), value: `${result.total_rocket.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('launch.jetSavings'), value: `${result.jet_savings.toFixed(1)} ${t('common.unit_ms')}` },
      { label: t('launch.totalWithJets'), value: `${result.total_with_jets.toFixed(1)} ${t('common.unit_ms')}` },
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
    <h1>{{ t('launch.title') }}</h1>

    <div class="calc-form">
      <div class="form-row">
        <label>{{ t('launch.bodyName') }}</label>
        <Select
          v-model="selectedBody"
          :options="bodyOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('launch.bodyName')"
          style="width: 260px"
        />
      </div>

      <div class="form-row">
        <label>{{ t('launch.targetAltitude') }}</label>
        <InputNumber
          v-model="targetAltitude"
          :min="0"
          :step="1000"
          style="width: 200px"
        />
      </div>

      <Button
        :label="t('launch.calculate')"
        icon="pi pi-calculator"
        :loading="calculating"
        @click="calculate"
      />
    </div>

    <DataTable v-if="resultRows.length > 0" :value="resultRows" class="result-table">
      <Column field="label" header="" style="width: 50%" />
      <Column field="value" header="" style="width: 50%; text-align: right; font-family: monospace" />
    </DataTable>
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
  width: 220px;
  color: var(--p-text-muted-color, #9ca3af);
}

.result-table {
  margin-top: 1rem;
}
</style>
