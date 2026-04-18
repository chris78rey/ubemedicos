<script setup lang="ts">
definePageMeta({
  layout: false,
})

type AccountType = 'patient' | 'professional'

const runtimeConfig = useRuntimeConfig()

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const accountType = ref<AccountType>('patient')

const form = reactive({
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  password: '',
})

const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const showPassword = ref(false)

const formRef = ref()

const requiredRule = (value: string) =>
  String(value || '').trim().length > 0 || 'Este campo es obligatorio.'

const emailRule = (value: string) => {
  const normalized = String(value || '').trim()
  if (!normalized) return 'Este campo es obligatorio.'
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)
    || 'Debe ingresar un correo válido.'
}

const passwordRule = (value: string) => {
  const normalized = String(value || '')
  if (!normalized) return 'Este campo es obligatorio.'
  return normalized.length >= 8 || 'La contraseña debe tener al menos 8 caracteres.'
}

const canSubmit = computed(() => {
  return (
    form.first_name.trim().length > 0
    && form.last_name.trim().length > 0
    && form.phone.trim().length > 0
    && form.email.trim().length > 0
    && form.password.trim().length > 0
  )
})

function getBackendErrorMessage(error: any): string {
  const detail = error?.data?.detail

  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item?.msg) return item.msg
        if (item?.message) return item.message
        return JSON.stringify(item)
      })
      .join(' ')
  }

  if (Array.isArray(error?.data?.errors) && error.data.errors.length > 0) {
    return error.data.errors
      .map((item: any) => {
        if (typeof item === 'string') return item
        if (item?.msg) return item.msg
        if (item?.message) return item.message
        return JSON.stringify(item)
      })
      .join(' ')
  }

  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message
  }

  return 'No se pudo completar el registro.'
}

async function handleRegister() {
  errorMessage.value = ''
  successMessage.value = ''

  const validationResult = await formRef.value?.validate?.()
  if (validationResult && validationResult.valid === false) {
    errorMessage.value = 'Todos los campos son obligatorios y deben ser válidos.'
    return
  }

  if (!canSubmit.value) {
    errorMessage.value = 'Todos los campos son obligatorios.'
    return
  }

  loading.value = true

  try {
    const payload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      password: form.password,
    }

    const endpoint =
      accountType.value === 'patient'
        ? `${apiBase.value}/auth/register/patient`
        : `${apiBase.value}/auth/register/professional`

    await $fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: payload,
    })

    successMessage.value = 'Cuenta creada correctamente. Redirigiendo...'

    setTimeout(() => {
      navigateTo('/login')
    }, 2000)
  } catch (error: any) {
    errorMessage.value = getBackendErrorMessage(error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-container fluid class="register-page d-flex align-center justify-center">
    <v-row justify="center" class="w-100 ma-0">
      <v-col cols="12" sm="10" md="8" lg="5" xl="4">
        <v-card class="register-card" elevation="10" rounded="xl">
          <v-card-text class="pa-6 pa-md-8">
            <div class="text-center mb-6">
              <div class="text-h4 font-weight-bold mb-2">
                Ubemedicos
              </div>
              <div class="text-body-1 text-medium-emphasis">
                Registro seguro de usuarios
              </div>
            </div>

            <div class="mb-6">
              <div class="text-subtitle-1 font-weight-medium text-center mb-3">
                Tipo de cuenta
              </div>

              <div class="d-flex justify-center">
                <v-btn-toggle
                  v-model="accountType"
                  color="primary"
                  mandatory
                  divided
                  class="account-toggle"
                >
                  <v-btn value="patient" size="large">
                    Soy Paciente
                  </v-btn>
                  <v-btn value="professional" size="large">
                    Soy Profesional
                  </v-btn>
                </v-btn-toggle>
              </div>

              <div class="text-center text-body-2 text-medium-emphasis mt-3">
                <template v-if="accountType === 'patient'">
                  Se creará una cuenta de paciente para reserva y gestión de citas.
                </template>
                <template v-else>
                  Se creará una cuenta profesional en estado inicial para completar validación posterior.
                </template>
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

            <v-alert
              v-if="successMessage"
              type="success"
              variant="tonal"
              class="mb-4"
            >
              {{ successMessage }}
            </v-alert>

            <v-form ref="formRef" @submit.prevent="handleRegister">
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.first_name"
                    label="Nombres"
                    variant="outlined"
                    density="comfortable"
                    prepend-inner-icon="mdi-account-outline"
                    autocomplete="given-name"
                    :rules="[requiredRule]"
                    :disabled="loading"
                    required
                  />
                </v-col>

                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.last_name"
                    label="Apellidos"
                    variant="outlined"
                    density="comfortable"
                    prepend-inner-icon="mdi-account-outline"
                    autocomplete="family-name"
                    :rules="[requiredRule]"
                    :disabled="loading"
                    required
                  />
                </v-col>
              </v-row>

              <v-text-field
                v-model="form.phone"
                label="Teléfono"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-phone-outline"
                autocomplete="tel"
                class="mb-3"
                :rules="[requiredRule]"
                :disabled="loading"
                required
              />

              <v-text-field
                v-model="form.email"
                label="Correo electrónico"
                type="email"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-email-outline"
                autocomplete="email"
                class="mb-3"
                :rules="[emailRule]"
                :disabled="loading"
                required
              />

              <v-text-field
                v-model="form.password"
                label="Contraseña"
                :type="showPassword ? 'text' : 'password'"
                variant="outlined"
                density="comfortable"
                prepend-inner-icon="mdi-lock-outline"
                :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                autocomplete="new-password"
                class="mb-2"
                :rules="[passwordRule]"
                :disabled="loading"
                required
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
                Crear cuenta
              </v-btn>
            </v-form>

            <div class="text-center mt-6">
              <span class="text-body-2 text-medium-emphasis">
                ¿Ya tienes cuenta?
              </span>
              <NuxtLink to="/login" class="login-link ms-1">
                Inicia sesión aquí
              </NuxtLink>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  background:
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.08), rgba(var(--v-theme-surface), 1));
  padding: 24px;
}

.register-card {
  width: 100%;
  max-width: 620px;
  margin: 0 auto;
  backdrop-filter: blur(4px);
}

.account-toggle {
  width: 100%;
  max-width: 420px;
}

.account-toggle :deep(.v-btn) {
  flex: 1 1 0;
}

.login-link {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
  font-weight: 600;
}

.login-link:hover {
  text-decoration: underline;
}
</style>
