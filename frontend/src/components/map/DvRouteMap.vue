<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Select from 'primevue/select'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ProgressBar from 'primevue/progressbar'
import { useApi } from '@/composables/useApi'
import { useRouteMap } from '@/composables/useRouteMap'
import type { DestinationEntry, DvStepResponse, RouteResponse } from '@/types/api'

const { t } = useI18n()
const api = useApi()

// Template ref for the D3 container div
const mapContainer = ref<HTMLElement | null>(null)

// Loading states
const loadingMap = ref(false)
const calculating = ref(false)
const loadError = ref(false)

// Data
const destinations = ref<DestinationEntry[]>([])
const selectedDestination = ref<string | null>(null)
const moons = ref<DestinationEntry[]>([])
const selectedMoon = ref<string | null>(null)
const loadingMoons = ref(false)
const routeSteps = ref<DvStepResponse[]>([])
const routeResult = ref<RouteResponse | null>(null)

// D3 composable — must be called with the ref before render()
const { render, highlightRoute } = useRouteMap(mapContainer, {
  onNodeClick(name: string) {
    selectedDestination.value = name
  },
})

interface SelectOption {
  label: string
  value: string
}
const destOptions = ref<SelectOption[]>([])
const moonOptions = ref<SelectOption[]>([])

// Home world name and its moon names (for route calc distinction)
const homeWorldName = ref<string>('')
const homeWorldMoonNames = ref<Set<string>>(new Set())

onMounted(async () => {
  loadingMap.value = true
  try {
    // Fetch system tree and destinations in parallel
    const [system, dests] = await Promise.all([api.getSystem(), api.getDestinations()])

    destinations.value = dests
    homeWorldName.value = system.home_world.name

    // Build destination options: planets first
    const options: SelectOption[] = dests.map((d) => ({
      label: d.body.display_name,
      value: d.body.name,
    }))

    // Add home world moons to destination list
    try {
      const homeMoons = await api.getBodyMoons(system.home_world.name)
      const moonNames = new Set<string>()
      for (const m of homeMoons) {
        options.push({
          label: `${m.body.display_name} (${system.home_world.display_name})`,
          value: m.body.name,
        })
        moonNames.add(m.body.name)
      }
      homeWorldMoonNames.value = moonNames
    } catch {
      // Home world may have no moons — non-fatal
    }

    destOptions.value = options

    render(system.tree, system.root, system.home_world.name, dests)
  } catch (err) {
    loadError.value = true
    api.handleError(err)
  } finally {
    loadingMap.value = false
  }
})

watch(selectedDestination, async (name) => {
  selectedMoon.value = null
  moonOptions.value = []
  moons.value = []
  if (!name) return

  loadingMoons.value = true
  try {
    const result = await api.getBodyMoons(name)
    moons.value = result
    moonOptions.value = result.map((m) => ({
      label: m.body.display_name,
      value: m.body.name,
    }))
  } catch {
    // no moons
  } finally {
    loadingMoons.value = false
  }
})

async function calcRoute(): Promise<void> {
  if (!selectedDestination.value && !selectedMoon.value) return

  calculating.value = true
  try {
    // Route param mapping:
    // - Home world moon (no sub-moon): destination=null, moon=selected
    // - Home world moon + sub-moon: destination=moon, moon=sub-moon
    // - Planet (no moon): destination=planet, moon=null
    // - Planet + moon: destination=planet, moon=moon
    const isHomeMoon = selectedDestination.value && homeWorldMoonNames.value.has(selectedDestination.value)
    let destParam: string | null
    let moonParam: string | null
    if (isHomeMoon && selectedMoon.value) {
      destParam = selectedDestination.value
      moonParam = selectedMoon.value
    } else if (isHomeMoon) {
      destParam = null
      moonParam = selectedDestination.value
    } else {
      destParam = selectedDestination.value
      moonParam = selectedMoon.value
    }
    const result: RouteResponse = await api.calcRoute({
      destination: destParam,
      moon: moonParam,
    })
    routeResult.value = result
    routeSteps.value = result.steps
    highlightRoute(result.steps)
  } catch (err) {
    api.handleError(err)
  } finally {
    calculating.value = false
  }
}
</script>

<template>
  <div class="route-map-page">
    <!-- Controls -->
    <div class="controls">
      <h1>{{ t('map.title') }}</h1>

      <div class="controls-row">
        <Select
          v-model="selectedDestination"
          :options="destOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('map.selectDestination')"
          show-clear
          style="width: 260px"
        />
        <Select
          v-if="moonOptions.length > 0"
          v-model="selectedMoon"
          :options="moonOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('map.selectMoon')"
          :loading="loadingMoons"
          show-clear
          style="width: 260px"
        />
        <Button
          :label="t('map.calculate')"
          icon="pi pi-send"
          :loading="calculating"
          :disabled="(!selectedDestination && !selectedMoon) || loadingMap"
          @click="calcRoute"
        />
      </div>
    </div>

    <!-- Map card -->
    <div class="map-card">
      <ProgressBar v-if="loadingMap" mode="indeterminate" style="height: 4px" />
      <div v-if="loadError" class="map-placeholder map-error">
        {{ t('common.error') }}
      </div>
      <div
        ref="mapContainer"
        class="map-container"
        :aria-label="t('map.title')"
      />
      <div v-if="!loadingMap && !loadError && destOptions.length === 0" class="map-placeholder">
        {{ t('common.notLoaded') }}
      </div>
    </div>

    <!-- Route results -->
    <div v-if="routeSteps.length > 0" class="route-results">
      <h2>{{ t('map.routeResult') }}</h2>

      <DataTable :value="routeSteps" class="route-table">
        <Column field="label" :header="t('map.step')" />
        <Column :header="t('map.dv')">
          <template #body="{ data }">
            {{ (data as DvStepResponse).dv.toFixed(1) }}
          </template>
        </Column>
        <Column :header="t('map.cumulative')">
          <template #body="{ data }">
            {{ (data as DvStepResponse).cumulative.toFixed(1) }}
          </template>
        </Column>
        <Column field="note" :header="t('map.note')" />
      </DataTable>

      <div v-if="routeResult" class="route-summary">
        <span>
          {{ t('map.totalPowered') }}:
          <strong>{{ routeResult.total_powered.toFixed(1) }} {{ t('common.unit_ms') }}</strong>
        </span>
        <span v-if="routeResult.total_aerobrake !== null">
          {{ t('map.totalAerobrake') }}:
          <strong>{{ routeResult.total_aerobrake.toFixed(1) }} {{ t('common.unit_ms') }}</strong>
        </span>
      </div>
    </div>

    <!-- Empty state when no route calculated yet -->
    <div v-else-if="!loadingMap" class="no-route">
      {{ t('map.noRoute') }}
    </div>
  </div>
</template>

<style scoped>
.route-map-page {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  height: 100%;
}

.controls h1 {
  margin-bottom: 0.75rem;
}

.controls-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.map-card {
  position: relative;
  flex-grow: 1;
  min-height: 400px;
  background: var(--p-surface-800, #1f2937);
  border: 1px solid var(--p-surface-700, #374151);
  border-radius: 8px;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.map-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.875rem;
}

.route-results h2 {
  margin-bottom: 0.75rem;
  font-size: 1rem;
  font-weight: 600;
}

.route-table {
  margin-bottom: 1rem;
}

.route-summary {
  display: flex;
  gap: 2rem;
  font-size: 0.9rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.route-summary strong {
  color: var(--p-text-color, #f3f4f6);
}

.no-route {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.875rem;
}
</style>
