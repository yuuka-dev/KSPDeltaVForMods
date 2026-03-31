<script setup lang="ts">
import { RouterView } from 'vue-router'
import Toast from 'primevue/toast'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
</script>

<template>
  <div class="app-layout app-dark">
    <AppSidebar />
    <div class="app-main">
      <AppHeader />
      <div class="app-content">
        <RouterView />
      </div>
    </div>
  </div>
  <Toast />
</template>
