<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import ProgressBar from 'primevue/progressbar'
import { useToast } from 'primevue/usetoast'
import { useApi } from '@/composables/useApi'
import type { BodyDetail } from '@/types/api'

const { t } = useI18n()
const route = useRoute()
const toast = useToast()
const api = useApi()

const body = ref<BodyDetail | null>(null)
const loading = ref(true)

onMounted(async () => {
  const name = String(route.params.name)
  try {
    body.value = await api.getBody(name)
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: err instanceof Error ? err.message : String(err),
      life: 5000,
    })
  } finally {
    loading.value = false
  }
})

const hasAtmosphere = computed(() => body.value?.atmosphere !== null)
const hasOrbit = computed(() => body.value?.orbit !== null)

function formatSeconds(sec: number): string {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${h}h ${m}m ${s}s`
}
</script>

<template>
  <div>
    <ProgressBar v-if="loading" mode="indeterminate" style="margin-bottom: 1rem" />

    <template v-if="body">
      <h1>{{ body.display_name }}</h1>

      <Tabs value="physical">
        <TabList>
          <Tab value="physical">{{ t('body.name') }}</Tab>
          <Tab v-if="hasAtmosphere" value="atmosphere">{{ t('body.atmosphere') }}</Tab>
          <Tab v-if="hasOrbit" value="orbit">{{ t('body.orbit') }}</Tab>
        </TabList>

        <TabPanels>
          <!-- Physical Properties -->
          <TabPanel value="physical">
            <table class="detail-table">
              <tbody>
                <tr>
                  <th>{{ t('body.radius') }}</th>
                  <td>{{ body.radius.toLocaleString() }} {{ t('common.unit_m') }}</td>
                </tr>
                <tr>
                  <th>{{ t('body.gravity') }}</th>
                  <td>{{ body.gee_asl.toFixed(3) }} {{ t('common.unit_g') }}</td>
                </tr>
                <tr>
                  <th>{{ t('body.mu') }}</th>
                  <td>{{ body.mu.toExponential(4) }} m³/s²</td>
                </tr>
                <tr>
                  <th>{{ t('body.soi') }}</th>
                  <td>{{ body.soi.toLocaleString() }} {{ t('common.unit_m') }}</td>
                </tr>
                <tr>
                  <th>{{ t('body.rotationalPeriod') }}</th>
                  <td>{{ formatSeconds(body.rotational_period) }}</td>
                </tr>
                <tr>
                  <th>{{ t('body.ocean') }}</th>
                  <td>{{ body.has_ocean ? t('body.yes') : t('body.no') }}</td>
                </tr>
              </tbody>
            </table>
          </TabPanel>

          <!-- Atmosphere -->
          <TabPanel v-if="hasAtmosphere && body.atmosphere" value="atmosphere">
            <table class="detail-table">
              <tbody>
                <tr>
                  <th>{{ t('body.atmosphere') }} Depth</th>
                  <td>{{ body.atmosphere.atmosphere_depth.toLocaleString() }} {{ t('common.unit_m') }}</td>
                </tr>
                <tr>
                  <th>Pressure (ASL)</th>
                  <td>{{ body.atmosphere.pressure_at_sea_level.toFixed(3) }} kPa</td>
                </tr>
                <tr>
                  <th>Temperature (ASL)</th>
                  <td>{{ body.atmosphere.temperature_at_sea_level.toFixed(1) }} K</td>
                </tr>
                <tr v-if="body.atmosphere.sea_level_density !== null">
                  <th>Sea Level Density</th>
                  <td>{{ body.atmosphere.sea_level_density!.toFixed(4) }} kg/m³</td>
                </tr>
              </tbody>
            </table>
          </TabPanel>

          <!-- Orbital Elements -->
          <TabPanel v-if="hasOrbit && body.orbit" value="orbit">
            <table class="detail-table">
              <tbody>
                <tr>
                  <th>Semi-Major Axis</th>
                  <td>{{ body.orbit.semi_major_axis.toLocaleString() }} {{ t('common.unit_m') }}</td>
                </tr>
                <tr>
                  <th>Eccentricity</th>
                  <td>{{ body.orbit.eccentricity.toFixed(5) }}</td>
                </tr>
                <tr>
                  <th>Inclination</th>
                  <td>{{ body.orbit.inclination.toFixed(3) }}°</td>
                </tr>
              </tbody>
            </table>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </template>
  </div>
</template>

<style scoped>
.detail-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

.detail-table th,
.detail-table td {
  padding: 0.6rem 0.8rem;
  border-bottom: 1px solid var(--p-surface-border, #374151);
  text-align: left;
}

.detail-table th {
  width: 40%;
  color: var(--p-text-muted-color, #9ca3af);
  font-weight: 500;
}
</style>
