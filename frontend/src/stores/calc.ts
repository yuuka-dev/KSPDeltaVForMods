import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { LaunchResponse, HohmannResponse, TsiolkovskyResponse } from '@/types/api'

export const useCalcStore = defineStore('calc', () => {
  const launchResult = ref<LaunchResponse | null>(null)
  const hohmannResult = ref<HohmannResponse | null>(null)
  const tsiolkovskyResult = ref<TsiolkovskyResponse | null>(null)

  function setLaunchResult(result: LaunchResponse): void {
    launchResult.value = result
  }

  function setHohmannResult(result: HohmannResponse): void {
    hohmannResult.value = result
  }

  function setTsiolkovskyResult(result: TsiolkovskyResponse): void {
    tsiolkovskyResult.value = result
  }

  function clear(): void {
    launchResult.value = null
    hohmannResult.value = null
    tsiolkovskyResult.value = null
  }

  return {
    launchResult, hohmannResult, tsiolkovskyResult,
    setLaunchResult, setHohmannResult, setTsiolkovskyResult, clear,
  }
})
