<script setup lang="ts">
definePageMeta({
  layout: false
})
type LoginResponse = {
  access_token: string
  token_type: string
  user?: {
    primary_role?: string | null
    email?: string
    first_name?: string
    last_name?: string
    [key: string]: any
  }
}

const runtimeConfig = useRuntimeConfig()

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const token = useCookie<string | null>('access_token', {
  path: '/',
})

const form = reactive({
  email: '',
  password: '',
})

const loading = ref(false)
const errorMessage = ref('')
const showPassword = ref(false)

const canSubmit = computed(() => {
  return form.email.trim().length > 0 && form.password.trim().length > 0
})

function resolveHomeByRole(primaryRole?: string | null) {
  const role = String(primaryRole || '').trim().toLowerCase()

  if (role === 'super_admin') {
    return '/admin'
  }

  if (
    role === 'admin' ||
    role === 'admin_validation' ||
    role === 'admin_support' ||
    role === 'admin_moderation' ||
    role === 'admin_privacy'
  ) {
    return '/admin'
  }

  if (role === 'privacy_auditor') {
    return '/admin/privacy/access-logs'
  }

  if (role === 'professional') {
    return '/professional'
  }

  if (role === 'patient') {
    return '/patient/appointments'
  }

  return '/'
}

async function handleLogin() {
  errorMessage.value = ''

  if (!canSubmit.value) {
    errorMessage.value = 'Email y contraseña son obligatorios.'
    return
  }

  loading.value = true

  try {
    const response = await $fetch<LoginResponse>(`${apiBase.value}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: {
        email: form.email.trim(),
        password: form.password,
      },
    })

    if (!response?.access_token) {
      throw new Error('No se recibió access_token en la respuesta.')
    }

    token.value = response.access_token

    const targetPath = resolveHomeByRole(response?.user?.primary_role)
    await navigateTo(targetPath)
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail ||
      'Credenciales inválidas o error de conexión'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-container fluid class="login-page d-flex align-center justify-center">
    <v-row justify="center" class="w-100 ma-0">
      <v-col cols="12" sm="10" md="6" lg="4" xl="3">
        <v-card class="login-card" elevation="10" rounded="xl">
          <v-card-text class="pa-6 pa-md-8">
            <div class="text-center mb-6">
              <div class="text-h4 font-weight-bold mb-2">
                Ubemedicos
              </div>
              <div class="text-body-1 text-medium-emphasis">
                Inicio de sesión seguro
              </div>
            </div>

            <v-alert
              v-if="errorMessage"
              type="error"
              variant="tonal"
              class="mb-4"
            >
              {{ errorMessage }}
            </v-alert>

            <v-form @submit.prevent="handleLogin">
              <v-text-field
                v-model="form.email"
                label="Correo electrónico"
                type="email"
                autocomplete="email"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-email-outline"
                class="mb-3"
                :disabled="loading"
                clearable
              />

              <v-text-field
                v-model="form.password"
                label="Contraseña"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-lock-outline"
                :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                class="mb-2"
                :disabled="loading"
                @click:append-inner="showPassword = !showPassword"
              />

              <v-btn
                type="submit"
                color="primary"
                block
                size="large"
                class="mt-4"
                :loading="loading"
                :disabled="loading || !canSubmit"
              >
                Iniciar sesión
              </v-btn>
            </v-form>

            <div class="text-center mt-6">
              <span class="text-body-2 text-medium-emphasis">
                ¿No tiene cuenta?
              </span>
              <NuxtLink to="/register" class="register-link ms-1">
                Registrarse
              </NuxtLink>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background:
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.08), rgba(var(--v-theme-surface), 1));
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 460px;
  margin: 0 auto;
  backdrop-filter: blur(4px);
}

.register-link {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
  font-weight: 600;
}

.register-link:hover {
  text-decoration: underline;
}
</style>
