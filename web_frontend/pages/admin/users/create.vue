<template>
  <v-container>
    <v-card class="pa-6" rounded="xl" elevation="2">
      <v-card-title class="text-h5 mb-4 text-primary">
        <v-icon start icon="mdi-account-plus"></v-icon>
        Crear Nuevo Administrador
      </v-card-title>

      <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" closable>
        {{ errorMessage }}
      </v-alert>
      <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-4" closable>
        {{ successMessage }}
      </v-alert>

      <v-form ref="formRef" @submit.prevent="submitForm">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="form.first_name"
              label="Nombres"
              required
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="form.last_name"
              label="Apellidos"
              required
              variant="outlined"
              density="comfortable"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="form.email"
              label="Correo Electrónico"
              type="email"
              required
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-email-outline"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="form.password"
              label="Contraseña temporal"
              type="password"
              required
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-lock-outline"
            />
          </v-col>
          <v-col cols="12">
            <v-select
              v-model="form.role"
              :items="roleOptions"
              label="Rol del Usuario"
              variant="outlined"
              density="comfortable"
              required
              prepend-inner-icon="mdi-shield-account"
            />
          </v-col>
        </v-row>
        
        <v-card-actions class="px-0 mt-4">
          <v-spacer />
          <v-btn variant="text" @click="navigateTo('/admin')">
            Cancelar
          </v-btn>
          <v-btn
            type="submit"
            color="primary"
            variant="flat"
            size="large"
            :loading="loading"
          >
            Crear Usuario
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const formRef = ref()

const form = reactive({
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  role: 'admin'
})

const roleOptions = [
  { title: 'Administrador Operativo (Validaciones y Pagos)', value: 'admin' },
  { title: 'Auditor de Privacidad (Solo visualización de logs)', value: 'privacy_auditor' }
]

function authHeaders() {
  return token.value ? { Authorization: `Bearer ${token.value}` } : {}
}

async function submitForm() {
  errorMessage.value = ''
  successMessage.value = ''

  if (!form.first_name || !form.last_name || !form.email || !form.password || !form.role) {
    errorMessage.value = 'Todos los campos son obligatorios.'
    return
  }

  loading.value = true

  try {
    await $fetch(`${apiBase.value}/admin/users`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders()
      },
      body: {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role
      }
    })

    successMessage.value = 'El nuevo administrador se ha creado con éxito.'
    
    // Limpiar formulario tras éxito
    form.first_name = ''
    form.last_name = ''
    form.email = ''
    form.password = ''
    
  } catch (error: any) {
    errorMessage.value = error?.data?.detail || 'Ocurrió un error al intentar crear el usuario.'
  } finally {
    loading.value = false
  }
}
</script>
