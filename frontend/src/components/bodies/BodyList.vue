<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import { useBodiesStore } from '@/stores/bodies'
import type { BodySummary } from '@/types/api'

const { t } = useI18n()
const router = useRouter()
const bodiesStore = useBodiesStore()

onMounted(() => {
  // bodies are already populated by ConfigUpload; nothing extra needed
})

function onRowClick(event: { data: BodySummary }): void {
  void router.push({ name: 'body-detail', params: { name: event.data.name } })
}

function formatRadius(value: number): string {
  return value.toLocaleString()
}
</script>

<template>
  <div>
    <h1>{{ t('nav.bodies') }}</h1>

    <DataTable
      :value="bodiesStore.bodies"
      :paginator="bodiesStore.bodies.length > 20"
      :rows="20"
      sortMode="single"
      rowHover
      class="body-table"
      @row-click="onRowClick"
    >
      <Column field="display_name" :header="t('body.name')" sortable />
      <Column field="radius" :header="t('body.radius')" sortable>
        <template #body="{ data }">
          {{ formatRadius((data as BodySummary).radius) }} {{ t('common.unit_m') }}
        </template>
      </Column>
      <Column field="gee_asl" :header="t('body.gravity')" sortable>
        <template #body="{ data }">
          {{ (data as BodySummary).gee_asl.toFixed(2) }} {{ t('common.unit_g') }}
        </template>
      </Column>
      <Column field="has_atmosphere" :header="t('body.atmosphere')" sortable>
        <template #body="{ data }">
          <Tag
            :severity="(data as BodySummary).has_atmosphere ? 'success' : 'secondary'"
            :value="(data as BodySummary).has_atmosphere ? t('body.yes') : t('body.no')"
          />
        </template>
      </Column>
      <Column field="has_ocean" :header="t('body.ocean')" sortable>
        <template #body="{ data }">
          <Tag
            :severity="(data as BodySummary).has_ocean ? 'info' : 'secondary'"
            :value="(data as BodySummary).has_ocean ? t('body.yes') : t('body.no')"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
.body-table {
  cursor: pointer;
}
</style>
