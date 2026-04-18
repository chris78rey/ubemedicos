<script setup lang="ts">
type PatientProfileResponse = {
  user: {
    id: number
    email: string
    first_name: string
    last_name: string
    phone: string
    role: string
    is_email_verified: boolean
  }
  profile: {
    id: number
    birth_date: string | null
    gender: string
    national_id: string
    emergency_contact_name: string
    emergency_contact_phone: string
    created_at: string | null
    updated_at: string | null
  }
}

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const profileResponse = ref<PatientProfileResponse | null>(null)

const form = reactive({
  first_name: '',
  last_name: '',
  phone: '',
  birth_date: '',
  gender: '',
  national_id: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
})

const genderOptions = [
  { title: 'No especificado', value: '' },
  { title: 'Femenino', value: 'female' },
  { title: 'Masculino', value: 'male' },
  { title: 'Otro', value: 'other' },
]

function authHeaders(extra: Record<string, string> = {}) {
  return token.value
    ? {
        Authorization: `Bearer ${token.value}`,
        ...extra,
      }
    : extra
}

function formatDateTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function setForm(response: PatientProfileResponse) {
  form.first_name = response.user.first_name || ''
  form.last_name = response.user.last_name || ''
  form.phone = response.user.phone || ''
  form.birth_date = response.profile.birth_date || ''
  form.gender = response.profile.gender || ''
  form.national_id = response.profile.national_id || ''
  form.emergency_contact_name = response.profile.emergency_contact_name || ''
  form.emergency_contact_phone = response.profile.emergency_contact_phone || ''
}

async function loadProfile() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    const response = await $fetch<PatientProfileResponse>(
      `${apiBase.value}/patient/profile`,
      {
        headers: authHeaders(),
      }
    )

    profileResponse.value = response
    setForm(response)
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar el perfil del paciente.'
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  saving.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    const response = await $fetch<PatientProfileResponse>(
      `${apiBase.value}/patient/profile`,
      {
        method: 'PATCH',
        headers: authHeaders({
          'Content-Type': 'application/json',
        }),
        body: {
          first_name: form.first_name,
          last_name: form.last_name,
          phone: form.phone,
          birth_date: form.birth_date || null,
          gender: form.gender,
          national_id: form.national_id,
          emergency_contact_name: form.emergency_contact_name,
          emergency_contact_phone: form.emergency_contact_phone,
        },
      }
    )

    profileResponse.value = response
    setForm(response)
    successMessage.value = 'Perfil del paciente actualizado correctamente.'
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo guardar el perfil del paciente.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadProfile()
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Perfil del paciente</h1>
        <p class="text-medium-emphasis">
          Panel principal para completar datos personales y contactos de emergencia.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2 flex-wrap">
        <v-btn variant="outlined" @click="navigateTo('/patient/appointments')">
          Ver citas
        </v-btn>
        <v-btn color="primary" variant="tonal" :loading="loading" @click="loadProfile">
          Recargar
        </v-btn>
      </v-col>
    </v-row>

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

    <v-row>
      <v-col cols="12" lg="8">
        <v-card>
          <v-card-title>Datos del paciente</v-card-title>

          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="form.first_name"
                  label="Nombres"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="form.last_name"
                  label="Apellidos"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="form.phone"
                  label="Teléfono"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="form.national_id"
                  label="Cédula o identificación"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="form.birth_date"
                  label="Fecha de nacimiento"
                  type="date"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-select
                  v-model="form.gender"
                  :items="genderOptions"
                  item-title="title"
                  item-value="value"
                  label="Género"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="form.emergency_contact_name"
                  label="Contacto de emergencia"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="form.emergency_contact_phone"
                  label="Teléfono de emergencia"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>
          </v-card-text>

          <v-divider />

          <v-card-actions class="pa-4">
            <v-spacer />
            <v-btn
              color="primary"
              :loading="saving"
              @click="saveProfile"
            >
              Guardar cambios
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <v-col cols="12" lg="4">
        <v-card class="mb-4">
          <v-card-title>Cuenta</v-card-title>
          <v-card-text>
            <div class="mb-2">
              <strong>Correo:</strong>
              {{ profileResponse?.user.email || '—' }}
            </div>
            <div class="mb-2">
              <strong>Rol:</strong>
              {{ profileResponse?.user.role || '—' }}
            </div>
            <div class="mb-2">
              <strong>Email verificado:</strong>
              {{ profileResponse?.user.is_email_verified ? 'Sí' : 'No' }}
            </div>
          </v-card-text>
        </v-card>

        <v-card>
          <v-card-title>Trazabilidad básica</v-card-title>
          <v-card-text>
            <div class="mb-2">
              <strong>Creado:</strong>
              {{ formatDateTime(profileResponse?.profile.created_at || null) }}
            </div>
            <div class="mb-2">
              <strong>Última actualización:</strong>
              {{ formatDateTime(profileResponse?.profile.updated_at || null) }}
            </div>
            <div class="text-caption text-medium-emphasis mt-4">
              Esta pantalla usa el endpoint de autoservicio del paciente y no modifica pagos, agenda ni validaciones del profesional.
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
