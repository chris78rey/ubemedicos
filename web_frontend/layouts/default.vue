<script setup lang="ts">
const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const drawer = ref(true)
const loading = ref(false)
const user = ref<any>(null)

async function fetchMe() {
  if (!token.value) {
    user.value = null
    return
  }

  try {
    const response = await $fetch<any>(`${apiBase.value}/auth/me`, {
      headers: { Authorization: `Bearer ${token.value}` },
    })
    user.value = response
  } catch (error) {
    user.value = null
    // If token is invalid, we might want to clear it, but let's be conservative
  }
}

async function logout() {
  loading.value = true
  try {
    // We could call the logout endpoint but clearing the cookie is essential
    token.value = null
    user.value = null
    await navigateTo('/login')
  } finally {
    loading.value = false
  }
}

const role = computed(() => {
  if (!user.value) return null
  return user.value.primary_role || user.value.actor_type
})

const menuItems = computed(() => {
  const items = [
    { title: 'Inicio Público', icon: 'mdi-home', to: '/' },
  ]

  if (!user.value) {
    items.push({ title: 'Iniciar Sesión', icon: 'mdi-login', to: '/login' })
    return items
  }

  // Admin items
  if (['admin', 'super_admin', 'admin_validation', 'admin_support', 'admin_moderation', 'admin_privacy'].includes(role.value)) {
    items.push({ title: 'Admin Dashboard', icon: 'mdi-view-dashboard', to: '/admin' })
    items.push({ title: 'Pagos Administrativos', icon: 'mdi-currency-usd', to: '/admin/payments' })
    items.push({ title: 'Validación Pro', icon: 'mdi-check-decagram', to: '/admin/professional-verifications' })
    items.push({ title: 'Logs de Acceso', icon: 'mdi-shield-account', to: '/admin/privacy/access-logs' })
  }

  // Super Admin only items
  if (role.value === 'super_admin') {
    items.push({ title: 'Crear Administrador', icon: 'mdi-account-plus', to: '/admin/users/create' })
  }

  // Professional items
  if (role.value === 'professional') {
    items.push({ title: 'Mi Perfil Pro', icon: 'mdi-account-star', to: '/professional' })
    items.push({ title: 'Mis Citas', icon: 'mdi-calendar-check', to: '/professional/appointments' })
    items.push({ title: 'Mi Agenda', icon: 'mdi-clock-outline', to: '/professional/availability' })
  }

  // Patient items
  if (role.value === 'patient') {
    items.push({ title: 'Mi Perfil', icon: 'mdi-account-circle', to: '/patient' })
    items.push({ title: 'Mis Citas', icon: 'mdi-calendar-heart', to: '/patient/appointments' })
  }

  return items
})

onMounted(async () => {
  await fetchMe()
})

// Re-fetch if token changes (e.g. after login)
watch(token, async (newVal) => {
  if (newVal) {
    await fetchMe()
  } else {
    user.value = null
  }
})
</script>

<template>
  <v-layout>
    <v-navigation-drawer
      v-model="drawer"
      elevation="2"
      color="surface"
      class="border-e-0"
    >
      <v-list-item class="pa-6">
        <template #title>
          <div class="text-h5 font-weight-bold primary-text">
            Ubemedicos
          </div>
        </template>
        <template #subtitle>
          <div v-if="user" class="mt-1 text-caption text-medium-emphasis">
            {{ user.email }}
          </div>
        </template>
      </v-list-item>

      <v-divider />

      <v-list nav density="comfortable" class="pa-4 ga-1">
        <v-list-item
          v-for="item in menuItems"
          :key="item.to"
          :to="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          active-color="primary"
          rounded="lg"
        />
      </v-list>

      <template #append>
        <div v-if="user" class="pa-4">
          <v-btn
            block
            variant="tonal"
            color="error"
            prepend-icon="mdi-logout"
            :loading="loading"
            @click="logout"
          >
            Cerrar Sesión
          </v-btn>
        </div>
      </template>
    </v-navigation-drawer>

    <v-app-bar flat border="b" class="px-4">
      <v-app-bar-nav-icon variant="text" @click="drawer = !drawer" />
      
      <v-app-bar-title>
        <span class="text-body-1 font-weight-medium">
          {{ $route.meta.title || 'Panel de Gestión' }}
        </span>
      </v-app-bar-title>

      <v-spacer />

      <v-btn
        v-if="!user"
        variant="flat"
        color="primary"
        to="/login"
      >
        Ingresar
      </v-btn>

      <div v-else class="d-flex align-center ga-3">
        <div class="text-right d-none d-sm-block">
          <div class="text-body-2 font-weight-bold">
            {{ user.first_name }} {{ user.last_name }}
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ user.actor_type }}
          </div>
        </div>
        <v-avatar color="primary" size="40">
          <span class="text-h6 initials text-white">
            {{ (user.first_name?.[0] || '') + (user.last_name?.[0] || '') }}
          </span>
        </v-avatar>
      </div>
    </v-app-bar>

    <v-main class="bg-grey-lighten-4 min-vh-100">
      <slot />
    </v-main>
  </v-layout>
</template>

<style scoped>
.primary-text {
  color: rgb(var(--v-theme-primary));
  letter-spacing: -0.5px;
}

.min-vh-100 {
  min-height: 100vh;
}

.initials {
  font-weight: 500;
}
</style>
