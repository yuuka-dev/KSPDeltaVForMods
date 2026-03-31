import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DvStepResponse, SystemResponse } from '@/types/api'

export const useSystemStore = defineStore('system', () => {
  const system = ref<SystemResponse | null>(null)
  const route = ref<DvStepResponse[]>([])

  function setSystem(sys: SystemResponse): void {
    system.value = sys
  }

  function setRoute(steps: DvStepResponse[]): void {
    route.value = steps
  }

  function clear(): void {
    system.value = null
    route.value = []
  }

  return { system, route, setSystem, setRoute, clear }
})
