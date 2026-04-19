import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { AdminInfo } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('admin_token') || '')
  const admin = ref<AdminInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const mustChangePassword = computed(() => admin.value?.must_change_password === 1)

  function setAuth(newToken: string, adminInfo: AdminInfo) {
    token.value = newToken
    admin.value = adminInfo
    localStorage.setItem('admin_token', newToken)
  }

  function logout() {
    token.value = ''
    admin.value = null
    localStorage.removeItem('admin_token')
  }

  return { token, admin, isLoggedIn, mustChangePassword, setAuth, logout }
})
