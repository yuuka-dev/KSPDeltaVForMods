<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { useToast } from 'primevue/usetoast'
import { useApi } from '@/composables/useApi'
import { useCalcStore } from '@/stores/calc'
import type { TsiolkovskyResponse } from '@/types/api'

const { t } = useI18n()
const toast = useToast()
const api = useApi()
const calcStore = useCalcStore()

const deltaV = ref<number>(3100)
const isp = ref<number>(310)
const wetMass = ref<number>(50000)
const calculating = ref(false)

interface ResultRow {
  label: string
  value: string
}

const resultRows = ref<ResultRow[]>([])

async function calculate(): Promise<void> {
  calculating.value = true
  try {
    const result: TsiolkovskyResponse = await api.calcTsiolkovsky({
      delta_v: deltaV.value,
      isp: isp.value,
      wet_mass: wetMass.value,
    })
    calcStore.setTsiolkovskyResult(result)

    resultRows.value = [
      { label: t('tsiolkovsky.massRatio'), value: result.mass_ratio.toFixed(4) },
      { label: t('tsiolkovsky.fuelFraction'), value: `${(result.fuel_fraction * 100).toFixed(2)} %` },
      { label: t('tsiolkovsky.dryMass'), value: `${result.dry_mass.toFixed(1)} ${t('common.unit_kg')}` },
      { label: t('tsiolkovsky.fuelMass'), value: `${result.fuel_mass.toFixed(1)} ${t('common.unit_kg')}` },
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
    <h1>{{ t('tsiolkovsky.title') }}</h1>

    <div class="calc-form">
      <div class="form-row">
        <label>{{ t('tsiolkovsky.deltaV') }}</label>
        <InputNumber
          v-model="deltaV"
          :min="0"
          :step="100"
          style="width: 200px"
        />
      </div>

      <div class="form-row">
        <label>{{ t('tsiolkovsky.isp') }}</label>
        <InputNumber
          v-model="isp"
          :min="1"
          :step="10"
          style="width: 200px"
        />
      </div>

      <div class="form-row">
        <label>{{ t('tsiolkovsky.wetMass') }}</label>
        <InputNumber
          v-model="wetMass"
          :min="1"
          :step="1000"
          style="width: 200px"
        />
      </div>

      <Button
        :label="t('tsiolkovsky.calculate')"
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
  max-width: 600px;
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
