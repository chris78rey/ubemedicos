<script setup lang="ts">
type SpecialtyItem = {
  id: number
  name: string
}

type ProfessionalProfileResponse = {
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
    specialty: {
      id: number | null
      name: string | null
    }
    license_number: string
    bio: string
    city: string
    province: string
    office_address: string
    public_profile_enabled: boolean
    verification_status: string
    consultation_fee: string
    teleconsultation_fee: string
    is_accepting_patients: boolean
    created_at: string | null
    updated_at: string | null
  }
  submission_blockers: string[]
  can_submit_for_verification: boolean
}

type VerificationStatusResponse = {
  profile: {
    professional_id: number
    verification_status: string
    public_profile_enabled: boolean
    can_submit_for_verification: boolean
    submission_blockers: string[]
    specialty_id: number | null
    license_number: string
    city: string
    province: string
  }
  latest_submission: {
    id: number
    status: string
    submitted_at: string | null
    assigned_admin_id: number | null
    reviewed_by_id: number | null
    reviewed_at: string | null
    reviewer_notes: string
  } | null
}

type DocumentItem = {
  id: number
  document_type: string
  original_name: string
  review_status: string
  reviewer_notes: string
  uploaded_at: string | null
  reviewed_at: string | null
  download_url: string
}

type EventItem = {
  id: number
  event_type: string
  event_payload: Record<string, any>
  created_by_id: number | null
  created_at: string | null
}

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const backendBase = computed(() => {
  return apiBase.value.replace(/\/api\/v1\/?$/, '')
})

const loading = ref(false)
const savingProfile = ref(false)
const uploadingDocument = ref(false)
const submittingVerification = ref(false)
const downloadingDocumentId = ref<number | null>(null)

const errorMessage = ref('')
const successMessage = ref('')

const specialties = ref<SpecialtyItem[]>([])
const profileResponse = ref<ProfessionalProfileResponse | null>(null)
const verificationResponse = ref<VerificationStatusResponse | null>(null)
const documents = ref<DocumentItem[]>([])
const events = ref<EventItem[]>([])

const profileForm = reactive({
  first_name: '',
  last_name: '',
  phone: '',
  specialty_id: null as number | null,
  license_number: '',
  bio: '',
  city: '',
  province: '',
  office_address: '',
  consultation_fee: '0.00',
  teleconsultation_fee: '0.00',
  public_profile_enabled: false,
  is_accepting_patients: true,
})

const uploadForm = reactive({
  document_type: 'id',
  file: null as File | File[] | null,
  replace_document_id: null as number | null,
})

const requiredDocumentTypes = ['id', 'title', 'license', 'senescyt']

const documentTypeOptions = [
  { title: 'Documento de identidad', value: 'id' },
  { title: 'Título profesional', value: 'title' },
  { title: 'Licencia profesional', value: 'license' },
  { title: 'Documento SENESCYT', value: 'senescyt' },
  { title: 'Otro documento', value: 'other' },
]

function authHeaders(extra: Record<string, string> = {}) {
  return token.value
    ? { Authorization: `Bearer ${token.value}`, ...extra }
    : { ...extra }
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    draft: 'Borrador',
    submitted: 'Enviada',
    under_review: 'En revisión',
    approved: 'Aprobada',
    rejected: 'Rechazada',
    needs_correction: 'Corrección solicitada',
    suspended: 'Suspendida',
    pending: 'Pendiente',
  }

  return labels[value] || value
}

function statusColor(value: string) {
  const colors: Record<string, string> = {
    draft: 'grey',
    submitted: 'warning',
    under_review: 'info',
    approved: 'success',
    rejected: 'error',
    needs_correction: 'deep-orange',
    suspended: 'grey-darken-1',
    pending: 'warning',
  }

  return colors[value] || 'default'
}

function reviewLabel(value: string) {
  const labels: Record<string, string> = {
    pending: 'Pendiente',
    approved: 'Aprobado',
    rejected: 'Rechazado',
  }
  return labels[value] || value
}

function reviewColor(value: string) {
  const colors: Record<string, string> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'error',
  }
  return colors[value] || 'default'
}

function documentTypeLabel(value: string) {
  const labels: Record<string, string> = {
    id: 'Documento de identidad',
    title: 'Título profesional',
    license: 'Licencia profesional',
    senescyt: 'Documento SENESCYT',
    other: 'Otro documento',
  }
  return labels[value] || value
}

function eventTypeLabel(value: string) {
  const labels: Record<string, string> = {
    submitted: 'Solicitud enviada',
    assigned: 'Asignada',
    comment_added: 'Comentario',
    document_approved: 'Documento aprobado',
    document_rejected: 'Documento rechazado',
    approved: 'Solicitud aprobada',
    rejected: 'Solicitud rechazada',
    correction_requested: 'Corrección solicitada',
    suspended: 'Suspendida',
  }
  return labels[value] || value
}

function formatDateTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function specialtyOptions() {
  return specialties.value.map((item) => ({
    title: item.name,
    value: item.id,
  }))
}

function currentBlockers() {
  return (
    verificationResponse.value?.profile.submission_blockers ||
    profileResponse.value?.submission_blockers ||
    []
  )
}

function canSubmitNow() {
  return verificationResponse.value?.profile.can_submit_for_verification || false
}

function latestSubmission() {
  return verificationResponse.value?.latest_submission || null
}

function findDocumentByType(documentType: string) {
  return documents.value.find((item) => item.document_type === documentType) || null
}

function documentSummaryItems() {
  return requiredDocumentTypes.map((documentType) => {
    const doc = findDocumentByType(documentType)
    return {
      document_type: documentType,
      label: documentTypeLabel(documentType),
      exists: Boolean(doc),
      review_status: doc?.review_status || 'missing',
      original_name: doc?.original_name || '',
      reviewer_notes: doc?.reviewer_notes || '',
      uploaded_at: doc?.uploaded_at || null,
    }
  })
}

function hasLicenseOrSenescyt() {
  return Boolean(findDocumentByType('license') || findDocumentByType('senescyt'))
}

function singleUploadFile() {
  if (Array.isArray(uploadForm.file)) {
    return uploadForm.file[0] || null
  }
  return uploadForm.file
}

function setProfileForm(response: ProfessionalProfileResponse) {
  profileForm.first_name = response.user.first_name || ''
  profileForm.last_name = response.user.last_name || ''
  profileForm.phone = response.user.phone || ''
  profileForm.specialty_id = response.profile.specialty?.id || null
  profileForm.license_number = response.profile.license_number || ''
  profileForm.bio = response.profile.bio || ''
  profileForm.city = response.profile.city || ''
  profileForm.province = response.profile.province || ''
  profileForm.office_address = response.profile.office_address || ''
  profileForm.consultation_fee = response.profile.consultation_fee || '0.00'
  profileForm.teleconsultation_fee = response.profile.teleconsultation_fee || '0.00'
  profileForm.public_profile_enabled = Boolean(response.profile.public_profile_enabled)
  profileForm.is_accepting_patients = Boolean(response.profile.is_accepting_patients)
}

async function fetchSpecialties() {
  const response = await $fetch<{ items: SpecialtyItem[] }>(
    `${apiBase.value}/catalogs/specialties`,
    {
      headers: authHeaders(),
    }
  )
  specialties.value = response.items || []
}

async function fetchProfile() {
  const response = await $fetch<ProfessionalProfileResponse>(
    `${apiBase.value}/professional/profile`,
    {
      headers: authHeaders(),
    }
  )
  profileResponse.value = response
  setProfileForm(response)
}

async function fetchVerificationStatus() {
  verificationResponse.value = await $fetch<VerificationStatusResponse>(
    `${apiBase.value}/professional/verification/status`,
    {
      headers: authHeaders(),
    }
  )
}

async function fetchDocuments() {
  const response = await $fetch<{ items: DocumentItem[] }>(
    `${apiBase.value}/professional/documents`,
    {
      headers: authHeaders(),
    }
  )
  documents.value = response.items || []
}

async function fetchEvents() {
  const response = await $fetch<{ items: EventItem[] }>(
    `${apiBase.value}/professional/verification/events`,
    {
      headers: authHeaders(),
    }
  )
  events.value = response.items || []
}

async function loadPage() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await Promise.all([
      fetchSpecialties(),
      fetchProfile(),
      fetchVerificationStatus(),
      fetchDocuments(),
      fetchEvents(),
    ])
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar el panel profesional.'
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  savingProfile.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch<ProfessionalProfileResponse>(`${apiBase.value}/professional/profile`, {
      method: 'PATCH',
      headers: authHeaders({
        'Content-Type': 'application/json',
      }),
      body: {
        first_name: profileForm.first_name,
        last_name: profileForm.last_name,
        phone: profileForm.phone,
        specialty_id: profileForm.specialty_id,
        license_number: profileForm.license_number,
        bio: profileForm.bio,
        city: profileForm.city,
        province: profileForm.province,
        office_address: profileForm.office_address,
        consultation_fee: profileForm.consultation_fee,
        teleconsultation_fee: profileForm.teleconsultation_fee,
        public_profile_enabled: profileForm.public_profile_enabled,
        is_accepting_patients: profileForm.is_accepting_patients,
      },
    })

    successMessage.value = 'Perfil profesional actualizado correctamente.'
    await Promise.all([fetchProfile(), fetchVerificationStatus()])
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo guardar el perfil profesional.'
  } finally {
    savingProfile.value = false
  }
}

function prepareReplacement(document: DocumentItem) {
  uploadForm.document_type = document.document_type
  uploadForm.replace_document_id = document.id
  successMessage.value = `Se preparó reemplazo para: ${document.original_name}`
}

function clearUploadSelection() {
  uploadForm.file = null
  uploadForm.replace_document_id = null
}

async function uploadDocument() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  const file = singleUploadFile()
  if (!file) {
    errorMessage.value = 'Se debe seleccionar un archivo.'
    return
  }

  uploadingDocument.value = true
  errorMessage.value = ''
  successMessage.value = ''

  const formData = new FormData()
  formData.append('document_type', uploadForm.document_type)
  formData.append('file', file)

  let url = `${apiBase.value}/professional/documents`
  let method: 'POST' | 'PATCH' = 'POST'

  if (uploadForm.replace_document_id) {
    url = `${apiBase.value}/professional/documents/${uploadForm.replace_document_id}`
    method = 'PATCH'
  } else if (uploadForm.document_type !== 'other') {
    const existing = findDocumentByType(uploadForm.document_type)
    if (existing) {
      url = `${apiBase.value}/professional/documents/${existing.id}`
      method = 'PATCH'
    }
  }

  try {
    await $fetch(url, {
      method,
      headers: authHeaders(),
      body: formData,
    })

    successMessage.value =
      method === 'PATCH'
        ? 'Documento reemplazado correctamente.'
        : 'Documento cargado correctamente.'

    clearUploadSelection()
    await Promise.all([fetchDocuments(), fetchVerificationStatus(), fetchEvents()])
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar el documento.'
  } finally {
    uploadingDocument.value = false
  }
}

async function submitForVerification() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  submittingVerification.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    const response = await $fetch<{ detail: string }>(
      `${apiBase.value}/professional/verification/submit`,
      {
        method: 'POST',
        headers: authHeaders(),
      }
    )

    successMessage.value =
      response.detail || 'Expediente enviado a revisión correctamente.'

    await Promise.all([
      fetchProfile(),
      fetchVerificationStatus(),
      fetchDocuments(),
      fetchEvents(),
    ])
  } catch (error: any) {
    if (Array.isArray(error?.data?.errors) && error.data.errors.length > 0) {
      errorMessage.value = error.data.errors.join(' ')
    } else {
      errorMessage.value =
        error?.data?.detail || 'No se pudo enviar la validación.'
    }
    await Promise.all([fetchVerificationStatus(), fetchProfile()])
  } finally {
    submittingVerification.value = false
  }
}

async function openDocument(document: DocumentItem) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  downloadingDocumentId.value = document.id
  errorMessage.value = ''

  try {
    const blob = await $fetch<Blob>(`${backendBase.value}${document.download_url}`, {
      headers: authHeaders(),
      responseType: 'blob',
    })

    const objectUrl = window.URL.createObjectURL(blob)
    window.open(objectUrl, '_blank', 'noopener,noreferrer')
    setTimeout(() => window.URL.revokeObjectURL(objectUrl), 60000)
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo abrir el documento.'
  } finally {
    downloadingDocumentId.value = null
  }
}

onMounted(async () => {
  await loadPage()
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Panel profesional</h1>
        <p class="text-medium-emphasis">
          Gestión del perfil, carga documental y seguimiento del estado de validación.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2 flex-wrap">
        <v-btn variant="outlined" @click="navigateTo('/professional/availability')">
          Agenda
        </v-btn>
        <v-btn variant="outlined" @click="navigateTo('/professional/appointments')">
          Citas
        </v-btn>
        <v-btn color="primary" :loading="loading" @click="loadPage">
          Recargar
        </v-btn>
      </v-col>
    </v-row>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4">
      {{ errorMessage }}
    </v-alert>

    <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-4">
      {{ successMessage }}
    </v-alert>

    <v-row class="mb-4">
      <v-col cols="12" md="4">
        <v-card height="100%">
          <v-card-text>
            <div class="text-body-2 text-medium-emphasis mb-2">Estado actual</div>
            <div class="d-flex align-center ga-3 mb-3">
              <div class="text-h5 font-weight-bold">
                {{ statusLabel(verificationResponse?.profile.verification_status || profileResponse?.profile.verification_status || 'draft') }}
              </div>
              <v-chip
                :color="statusColor(verificationResponse?.profile.verification_status || profileResponse?.profile.verification_status || 'draft')"
                variant="tonal"
              >
                Flujo de validación
              </v-chip>
            </div>

            <div class="text-body-2 text-medium-emphasis mb-1">
              Publicación pública
            </div>
            <div class="mb-3">
              {{ verificationResponse?.profile.public_profile_enabled ? 'Habilitada' : 'Bloqueada o deshabilitada' }}
            </div>

            <div class="text-body-2 text-medium-emphasis mb-1">
              Último envío
            </div>
            <div>
              {{ formatDateTime(latestSubmission()?.submitted_at || null) }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card height="100%">
          <v-card-text>
            <div class="text-body-2 text-medium-emphasis mb-2">Solicitud más reciente</div>

            <template v-if="latestSubmission()">
              <div class="mb-2">
                <strong>ID:</strong> {{ latestSubmission()?.id }}
              </div>
              <div class="mb-2">
                <strong>Estado:</strong> {{ statusLabel(latestSubmission()?.status || '') }}
              </div>
              <div class="mb-2">
                <strong>Fecha de revisión:</strong>
                {{ formatDateTime(latestSubmission()?.reviewed_at || null) }}
              </div>
              <div>
                <strong>Observación:</strong>
                {{ latestSubmission()?.reviewer_notes || 'Sin observaciones.' }}
              </div>
            </template>

            <template v-else>
              <div class="text-medium-emphasis">
                Todavía no existe una solicitud enviada.
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card height="100%">
          <v-card-text>
            <div class="text-body-2 text-medium-emphasis mb-2">Acción principal</div>

            <v-btn
              block
              color="primary"
              :disabled="!canSubmitNow()"
              :loading="submittingVerification"
              @click="submitForVerification"
            >
              Enviar expediente a validación
            </v-btn>

            <div class="text-caption text-medium-emphasis mt-3">
              El envío solo se habilita cuando el perfil y los documentos obligatorios cumplen las reglas del backend.
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row v-if="currentBlockers().length" class="mb-2">
      <v-col cols="12">
        <v-alert type="warning" variant="tonal">
          <div class="font-weight-bold mb-2">Bloqueos actuales para enviar a revisión</div>
          <ul class="pl-5">
            <li v-for="item in currentBlockers()" :key="item">
              {{ item }}
            </li>
          </ul>
        </v-alert>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" lg="7">
        <v-card class="mb-4">
          <v-card-title>Perfil profesional</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="profileForm.first_name"
                  label="Nombres"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="profileForm.last_name"
                  label="Apellidos"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="profileForm.phone"
                  label="Teléfono"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-select
                  v-model="profileForm.specialty_id"
                  :items="specialtyOptions()"
                  label="Especialidad"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="profileForm.license_number"
                  label="Número de licencia"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="3">
                <v-text-field
                  v-model="profileForm.city"
                  label="Ciudad"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="3">
                <v-text-field
                  v-model="profileForm.province"
                  label="Provincia"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="profileForm.office_address"
                  label="Dirección del consultorio (presencial)"
                  variant="outlined"
                  density="comfortable"
                  placeholder="Ej: Av. Principal 123 y Calle 5, Edificio Médico Of. 4B"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="profileForm.consultation_fee"
                  label="Tarifa consulta presencial"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="profileForm.teleconsultation_fee"
                  label="Tarifa teleconsulta"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12">
                <v-textarea
                  v-model="profileForm.bio"
                  label="Biografía profesional"
                  variant="outlined"
                  density="comfortable"
                  rows="4"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-switch
                  v-model="profileForm.public_profile_enabled"
                  color="primary"
                  inset
                  label="Habilitar perfil público"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-switch
                  v-model="profileForm.is_accepting_patients"
                  color="primary"
                  inset
                  label="Aceptar nuevos pacientes"
                />
              </v-col>
            </v-row>
          </v-card-text>

          <v-card-actions class="px-4 pb-4">
            <v-btn color="primary" :loading="savingProfile" @click="saveProfile">
              Guardar perfil
            </v-btn>
          </v-card-actions>
        </v-card>

        <v-card>
          <v-card-title>Carga y reemplazo de documentos</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <v-select
                  v-model="uploadForm.document_type"
                  :items="documentTypeOptions"
                  label="Tipo de documento"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>

              <v-col cols="12" md="6">
                <v-file-input
                  v-model="uploadForm.file"
                  label="Archivo"
                  variant="outlined"
                  density="comfortable"
                  prepend-icon="mdi-paperclip"
                  show-size
                  accept=".pdf,.png,.jpg,.jpeg"
                />
              </v-col>

              <v-col cols="12" v-if="uploadForm.replace_document_id">
                <v-alert type="info" variant="tonal">
                  El formulario está en modo reemplazo para el documento ID {{ uploadForm.replace_document_id }}.
                </v-alert>
              </v-col>
            </v-row>

            <div class="d-flex ga-2 flex-wrap">
              <v-btn color="primary" :loading="uploadingDocument" @click="uploadDocument">
                {{ uploadForm.replace_document_id ? 'Reemplazar documento' : 'Subir documento' }}
              </v-btn>
              <v-btn variant="outlined" @click="clearUploadSelection">
                Limpiar selección
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card class="mb-4">
          <v-card-title>Documentos obligatorios</v-card-title>
          <v-card-text>
            <div class="text-body-2 text-medium-emphasis mb-4">
              Para el tercer requisito basta con licencia profesional o documento SENESCYT.
            </div>

            <v-list lines="three">
              <v-list-item
                v-for="item in documentSummaryItems()"
                :key="item.document_type"
                class="px-0"
              >
                <template #prepend>
                  <v-chip
                    :color="item.exists ? reviewColor(item.review_status) : 'grey'"
                    variant="tonal"
                    size="small"
                  >
                    {{ item.exists ? reviewLabel(item.review_status) : 'Falta' }}
                  </v-chip>
                </template>

                <v-list-item-title class="font-weight-medium">
                  {{ item.label }}
                </v-list-item-title>
                <v-list-item-subtitle>
                  {{ item.original_name || 'No existe archivo cargado.' }}
                </v-list-item-subtitle>

                <template #append>
                  <span class="text-caption text-medium-emphasis">
                    {{ formatDateTime(item.uploaded_at) }}
                  </span>
                </template>
              </v-list-item>
            </v-list>

            <v-alert
              class="mt-4"
              :type="hasLicenseOrSenescyt() ? 'success' : 'warning'"
              variant="tonal"
            >
              {{
                hasLicenseOrSenescyt()
                  ? 'Se detectó al menos uno entre licencia profesional o SENESCYT.'
                  : 'Todavía falta licencia profesional o documento SENESCYT.'
              }}
            </v-alert>
          </v-card-text>
        </v-card>

        <v-card>
          <v-card-title>Historial de documentos</v-card-title>
          <v-card-text class="pa-0">
            <v-table density="comfortable">
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Archivo</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="document in documents" :key="document.id">
                  <td>{{ documentTypeLabel(document.document_type) }}</td>
                  <td>
                    <div>{{ document.original_name }}</div>
                    <div class="text-caption text-medium-emphasis">
                      {{ formatDateTime(document.uploaded_at) }}
                    </div>
                    <div
                      v-if="document.reviewer_notes"
                      class="text-caption text-error mt-1"
                    >
                      {{ document.reviewer_notes }}
                    </div>
                  </td>
                  <td>
                    <v-chip :color="reviewColor(document.review_status)" variant="tonal" size="small">
                      {{ reviewLabel(document.review_status) }}
                    </v-chip>
                  </td>
                  <td>
                    <div class="d-flex flex-column ga-2">
                      <v-btn
                        size="small"
                        variant="outlined"
                        :loading="downloadingDocumentId === document.id"
                        @click="openDocument(document)"
                      >
                        Abrir
                      </v-btn>
                      <v-btn
                        size="small"
                        color="primary"
                        variant="text"
                        @click="prepareReplacement(document)"
                      >
                        Reemplazar
                      </v-btn>
                    </div>
                  </td>
                </tr>

                <tr v-if="documents.length === 0">
                  <td colspan="4" class="text-center py-6 text-medium-emphasis">
                    No existen documentos cargados todavía.
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>Trazabilidad del expediente</v-card-title>
          <v-card-text>
            <v-timeline density="compact" side="end">
              <v-timeline-item
                v-for="item in events"
                :key="item.id"
                :dot-color="statusColor(item.event_type)"
                size="small"
              >
                <div class="d-flex justify-space-between flex-wrap ga-2">
                  <div class="font-weight-medium">
                    {{ eventTypeLabel(item.event_type) }}
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    {{ formatDateTime(item.created_at) }}
                  </div>
                </div>

                <div class="text-body-2 mt-1">
                  {{
                    Object.keys(item.event_payload || {}).length
                      ? JSON.stringify(item.event_payload)
                      : 'Sin detalle adicional.'
                  }}
                </div>
              </v-timeline-item>

              <v-timeline-item v-if="events.length === 0" dot-color="grey" size="small">
                Aún no existen eventos de validación.
              </v-timeline-item>
            </v-timeline>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
