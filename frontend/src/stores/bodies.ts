import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { BodyDetail, BodySummary } from '@/types/api'

export const useBodiesStore = defineStore('bodies', () => {
  const bodies = ref<BodySummary[]>([])
  const currentBody = ref<BodyDetail | null>(null)

  function setBodies(list: BodySummary[]): void {
    bodies.value = list
  }

  function setCurrentBody(body: BodyDetail | null): void {
    currentBody.value = body
  }

  function clear(): void {
    bodies.value = []
    currentBody.value = null
  }

  return { bodies, currentBody, setBodies, setCurrentBody, clear }
})
