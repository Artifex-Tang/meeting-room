import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/pages/login/LoginPage.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', component: () => import('@/pages/dashboard/DashboardPage.vue') },
        { path: 'rooms',     component: () => import('@/pages/rooms/RoomsPage.vue') },
        { path: 'users',     component: () => import('@/pages/users/UsersPage.vue') },
        { path: 'departments', component: () => import('@/pages/departments/DepartmentsPage.vue') },
        { path: 'bookings',  component: () => import('@/pages/bookings/BookingsPage.vue') },
        { path: 'settings',  component: () => import('@/pages/settings/SettingsPage.vue') },
        { path: 'profile',   component: () => import('@/pages/profile/ProfilePage.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (!auth.isLoggedIn && !to.meta.public) {
    return '/login'
  }

  // T-ADM-09: force change-password on first login
  if (auth.isLoggedIn && auth.mustChangePassword && to.path !== '/profile') {
    return '/profile'
  }
})

export default router
