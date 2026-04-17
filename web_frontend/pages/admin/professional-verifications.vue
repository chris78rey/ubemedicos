<script setup lang="ts">
type SubmissionItem = {
  id: number
  status: string
  submitted_at: string | null
  assigned_admin_id: number | null
  reviewed_by_id: number | null
  reviewed_at: string | null
  reviewer_notes: string
  professional_email: string
  professional_name: string
  specialty: string | null
}

type SubmissionDetail = {
  id: number
  status: string
  submitted_at: string | null
  assigned_admin_id: number | null
  reviewed_by_id: number | null
  reviewed_at: string | null
  reviewer_notes: string
}

type ProfileDetail = {
  id: number
  email: string
  name: string
  license_number: string
  city: string
  province: string
  verification_status: string
}

type DocumentItem = {
  id: number
  document_type: string
  original_name: string
  review_status: string
  reviewer_notes: string
  uploaded_at: string | null
  reviewed_at: string | null
  download_url?: string
}

type EventItem = {
  id: number
  event_type: string
  event_payload: Record<string, any>
  created_by_id: number | null
  created_at: string | null
}

type DetailResponse = {
  submission: SubmissionDetail
  profile: ProfileDetail
  documents: DocumentItem[]
  events: EventItem[]
}

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const backendBase = computed(() => {
  return apiBase.value.replace(/\/api\/v1\/?$/, '')
})

const loadingList = ref(false)
const loadingDetail = ref(false)
const downloadingDocumentId = ref<number | null>(null)
const acting = ref(false)
const selectedSubmissionId = ref<number | null>(null)
const errorMessage = ref('')
const successMessage = ref('')

const submissions = ref<SubmissionItem[]>([])
const detail = ref<DetailResponse | null>(null)
const documentNotes = reactive<Record<number, string>>({})

const filters = reactive({
  status: '',
  professional_email: '',
  mine: true,
})

const decisionNotes = reactive({
  approval: '',
  correction: '',
  rejection: '',
})

const availableStatuses = [
  { title: 'Abiertas', value: '' },
  { title: 'Enviada', value: 'submitted' },
  { title: 'En revisión', value: 'under_review' },
  { title: 'Aprobada', value: 'approved' },
  { title: 'Rechazada', value: 'rejected' },
  { title: 'Corrección solicitada', value: 'needs_correction' },
  { title: 'Suspendida', value: 'suspended' },
]

function authHeaders() {
  return token.value
    ? { Authorization: `Bearer ${token.value}` }
    : {}
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    submitted: 'Enviada',
    under_review: 'En revisión',
    approved: 'Aprobada',
    rejected: 'Rechazada',
    needs_correction: 'Corrección solicitada',
    suspended: 'Suspendida',
    draft: 'Borrador',
    pending: 'Pendiente',
  }

  return labels[value] || value
}

function statusColor(value: string) {
  const colors: Record<string, string> = {
    submitted: 'warning',
    under_review: 'info',
    approved: 'success',
    rejected: 'error',
    needs_correction: 'deep-orange',
    suspended: 'grey',
    pending: 'warning',
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
    assigned: 'Asignación',
    comment_added: 'Comentario agregado',
    document_approved: 'Documento aprobado',
    document_rejected: 'Documento rechazado',
    approved: 'Solicitud aprobada',
    rejected: 'Solicitud rechazada',
    correction_requested: 'Corrección solicitada',
    suspended: 'Solicitud suspendida',
  }

  return labels[value] || value
}

function formatDateTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function prettyEventPayload(value: Record<string, any>) {
  if (!value || Object.keys(value).length === 0) {
    return 'Sin detalle adicional'
  }

  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return 'No se pudo representar el payload del evento'
  }
}

function isCurrentSelection(submissionId: number) {
  return selectedSubmissionId.value === submissionId
}

function canStartReview() {
  return detail.value?.submission.status === 'submitted'
}

function canApproveSubmission() {
  if (!detail.value) return false
  return ['submitted', 'under_review'].includes(detail.value.submission.status)
}

function canRequestCorrection() {
  if (!detail.value) return false
  return ['submitted', 'under_review'].includes(detail.value.submission.status)
}

function canRejectSubmission() {
  if (!detail.value) return false
  return ['submitted', 'under_review'].includes(detail.value.submission.status)
}

async function loadSubmissions(selectFirst = true) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loadingList.value = true
  errorMessage.value = ''

  const query = new URLSearchParams()
  if (filters.status) query.set('status', filters.status)
  if (filters.professional_email.trim()) {
    query.set('professional_email', filters.professional_email.trim())
  }
  if (filters.mine) query.set('mine', '1')

  try {
    const response = await $fetch<{ items: SubmissionItem[] }>(
      `${apiBase.value}/admin/professional-verifications${query.toString() ? `?${query.toString()}` : ''}`,
      {
        headers: authHeaders(),
      }
    )

    submissions.value = response.items || []

    const selectedStillExists = submissions.value.some(
      (item) => item.id === selectedSubmissionId.value
    )

    if (selectedStillExists && selectedSubmissionId.value) {
      await loadDetail(selectedSubmissionId.value)
      return
    }

    if (selectFirst && submissions.value.length > 0) {
      selectedSubmissionId.value = submissions.value[0].id
      await loadDetail(submissions.value[0].id)
      return
    }

    if (submissions.value.length === 0) {
      selectedSubmissionId.value = null
      detail.value = null
    }
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar la bandeja de validaciones.'
  } finally {
    loadingList.value = false
  }
}

function syncDocumentNotes() {
  Object.keys(documentNotes).forEach((key) => {
    delete documentNotes[Number(key)]
  })

  ;(detail.value?.documents || []).forEach((doc) => {
    documentNotes[doc.id] = doc.reviewer_notes || ''
  })
}

async function loadDetail(submissionId: number) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loadingDetail.value = true
  errorMessage.value = ''

  try {
    const response = await $fetch<DetailResponse>(
      `${apiBase.value}/admin/professional-verifications/${submissionId}`,
      {
        headers: authHeaders(),
      }
    )

    detail.value = response
    selectedSubmissionId.value = submissionId
    syncDocumentNotes()
    decisionNotes.approval = response.submission.reviewer_notes || ''
    decisionNotes.correction = ''
    decisionNotes.rejection = ''
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar el detalle de la solicitud.'
  } finally {
    loadingDetail.value = false
  }
}

async function assignToMe() {
  if (!detail.value) return

  acting.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(
      `${apiBase.value}/admin/professional-verifications/${detail.value.submission.id}/assign`,
      {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: {},
      }
    )

    successMessage.value = 'Solicitud asignada correctamente.'
    await loadSubmissions(false)
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo asignar la solicitud.'
  } finally {
    acting.value = false
  }
}

async function startReview() {
  if (!detail.value) return

  acting.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(
      `${apiBase.value}/admin/professional-verifications/${detail.value.submission.id}/start-review`,
      {
        method: 'POST',
        headers: authHeaders(),
      }
    )

    successMessage.value = 'La revisión formal fue iniciada correctamente.'
    await loadSubmissions(false)
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo iniciar la revisión.'
  } finally {
    acting.value = false
  }
}

async function reviewDocument(documentId: number, decision: 'approved' | 'rejected') {
  if (!detail.value) return

  acting.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(
      `${apiBase.value}/admin/professional-verifications/${detail.value.submission.id}/documents/${documentId}/review`,
      {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: {
          decision,
          notes: documentNotes[documentId] || '',
        },
      }
    )

    successMessage.value =
      decision === 'approved'
        ? 'Documento aprobado correctamente.'
        : 'Documento rechazado correctamente.'

    await loadDetail(detail.value.submission.id)
    await loadSubmissions(false)
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo revisar el documento.'
  } finally {
    acting.value = false
  }
}

async function requestCorrection() {
  if (!detail.value) return

  if (!decisionNotes.correction.trim()) {
    errorMessage.value = 'Debe registrar observaciones para solicitar corrección.'
    return
  }

  acting.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(
      `${apiBase.value}/admin/professional-verifications/${detail.value.submission.id}/request-correction`,
      {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: {
          notes: decisionNotes.correction.trim(),
        },
      }
    )

    successMessage.value = 'Se solicitó corrección al profesional.'
    await loadSubmissions(false)
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo solicitar la corrección.'
  } finally {
    acting.value = false
  }
}

async function approveSubmission() {
  if (!detail.value) return

  acting.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(
      `${apiBase.value}/admin/professional-verifications/${detail.value.submission.id}/approve`,
      {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: {
          notes: decisionNotes.approval.trim(),
        },
      }
    )

    successMessage.value = 'Solicitud aprobada correctamente.'
    await loadSubmissions(false)
  } catch (error: any) {
    const errors = error?.data?.errors
    if (Array.isArray(errors) && errors.length > 0) {
      errorMessage.value = errors.join(' ')
    } else {
      errorMessage.value =
        error?.data?.detail || 'No se pudo aprobar la solicitud.'
    }
  } finally {
    acting.value = false
  }
}

async function rejectSubmission() {
  if (!detail.value) return

  if (!decisionNotes.rejection.trim()) {
    errorMessage.value = 'Debe registrar observaciones para rechazar la solicitud.'
    return
  }

  acting.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(
      `${apiBase.value}/admin/professional-verifications/${detail.value.submission.id}/reject`,
      {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: {
          notes: decisionNotes.rejection.trim(),
        },
      }
    )

    successMessage.value = 'Solicitud rechazada correctamente.'
    await loadSubmissions(false)
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo rechazar la solicitud.'
  } finally {
    acting.value = false
  }
}

async function openDocument(document: DocumentItem) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  if (!document.download_url) {
    errorMessage.value =
      'Este backend todavía no expone download_url. Debe aplicarse el parche de descarga segura.'
    return
  }

  downloadingDocumentId.value = document.id
  errorMessage.value = ''

  try {
    const response = await fetch(`${backendBase.value}${document.download_url}`, {
      headers: authHeaders(),
    })

    if (!response.ok) {
      throw new Error('No se pudo descargar el documento.')
    }

    const blob = await response.blob()
    const fileUrl = window.URL.createObjectURL(blob)
    window.open(fileUrl, '_blank', 'noopener,noreferrer')

    setTimeout(() => {
      window.URL.revokeObjectURL(fileUrl)
    }, 60_000)
  } catch (error: any) {
    errorMessage.value =
      error?.message || 'No se pudo abrir el documento.'
  } finally {
    downloadingDocumentId.value = null
  }
}

onMounted(async () => {
  await loadSubmissions(true)
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Validación profesional</h1>
        <p class="text-medium-emphasis">
          Desde esta pantalla el administrador revisa documentos, asigna casos y decide la aprobación final.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2">
        <v-btn color="primary" :loading="loadingList || loadingDetail" @click="loadSubmissions(false)">
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

    <v-row>
      <v-col cols="12" lg="4">
        <v-card class="mb-6">
          <v-card-title>Filtros</v-card-title>
          <v-card-text>
            <v-select
              v-model="filters.status"
              :items="availableStatuses"
              item-title="title"
              item-value="value"
              label="Estado"
              class="mb-3"
            />

            <v-text-field
              v-model="filters.professional_email"
              label="Correo del profesional"
              class="mb-3"
            />

            <v-switch
              v-model="filters.mine"
              label="Solo asignadas al administrador actual"
              inset
              color="primary"
            />
          </v-card-text>

          <v-card-actions>
            <v-btn color="primary" :loading="loadingList" @click="loadSubmissions(true)">
              Aplicar filtros
            </v-btn>
          </v-card-actions>
        </v-card>

        <v-card>
          <v-card-title>Bandeja</v-card-title>
          <v-card-text>
            <v-list lines="two" density="comfortable">
              <v-list-item
                v-for="item in submissions"
                :key="item.id"
                :active="isCurrentSelection(item.id)"
                rounded="lg"
                @click="loadDetail(item.id)"
              >
                <template #prepend>
                  <v-avatar color="primary" variant="tonal">
                    {{ item.id }}
                  </v-avatar>
                </template>

                <v-list-item-title>
                  {{ item.professional_name || item.professional_email }}
                </v-list-item-title>

                <v-list-item-subtitle>
                  {{ item.professional_email }} · {{ item.specialty || 'Sin especialidad' }}
                </v-list-item-subtitle>

                <template #append>
                  <div class="d-flex flex-column align-end ga-1">
                    <v-chip size="small" :color="statusColor(item.status)" variant="tonal">
                      {{ statusLabel(item.status) }}
                    </v-chip>
                    <span class="text-caption text-medium-emphasis">
                      {{ formatDateTime(item.submitted_at) }}
                    </span>
                  </div>
                </template>
              </v-list-item>
            </v-list>

            <div v-if="submissions.length === 0" class="text-medium-emphasis">
              No existen solicitudes para los filtros seleccionados.
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="8">
        <v-card v-if="detail" class="mb-6">
          <v-card-title class="d-flex flex-wrap align-center ga-2">
            <span>Solicitud #{{ detail.submission.id }}</span>
            <v-chip :color="statusColor(detail.submission.status)" variant="tonal">
              {{ statusLabel(detail.submission.status) }}
            </v-chip>
          </v-card-title>

          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <div class="text-subtitle-1 font-weight-bold mb-2">Datos del profesional</div>
                <div class="mb-1"><strong>Nombre:</strong> {{ detail.profile.name || '—' }}</div>
                <div class="mb-1"><strong>Correo:</strong> {{ detail.profile.email }}</div>
                <div class="mb-1"><strong>Licencia:</strong> {{ detail.profile.license_number || '—' }}</div>
                <div class="mb-1"><strong>Ciudad:</strong> {{ detail.profile.city || '—' }}</div>
                <div class="mb-1"><strong>Provincia:</strong> {{ detail.profile.province || '—' }}</div>
                <div><strong>Estado perfil:</strong> {{ statusLabel(detail.profile.verification_status) }}</div>
              </v-col>

              <v-col cols="12" md="6">
                <div class="text-subtitle-1 font-weight-bold mb-2">Datos de la solicitud</div>
                <div class="mb-1"><strong>Enviada:</strong> {{ formatDateTime(detail.submission.submitted_at) }}</div>
                <div class="mb-1"><strong>Admin asignado:</strong> {{ detail.submission.assigned_admin_id || 'No asignado' }}</div>
                <div class="mb-1"><strong>Revisado por:</strong> {{ detail.submission.reviewed_by_id || '—' }}</div>
                <div class="mb-1"><strong>Fecha revisión:</strong> {{ formatDateTime(detail.submission.reviewed_at) }}</div>
                <div><strong>Notas finales:</strong> {{ detail.submission.reviewer_notes || 'Sin notas' }}</div>
              </v-col>
            </v-row>
          </v-card-text>

          <v-divider />

          <v-card-actions class="flex-wrap ga-2 pa-4">
            <v-btn color="primary" variant="tonal" :loading="acting" @click="assignToMe">
              Asignarme caso
            </v-btn>

            <v-btn
              color="info"
              variant="tonal"
              :loading="acting"
              :disabled="!canStartReview()"
              @click="startReview"
            >
              Iniciar revisión
            </v-btn>
          </v-card-actions>
        </v-card>

        <v-card v-if="detail" class="mb-6">
          <v-card-title>Documentos</v-card-title>
          <v-card-text>
            <v-table>
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Archivo</th>
                  <th>Estado</th>
                  <th>Subido</th>
                  <th>Revisado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="doc in detail.documents" :key="doc.id">
                  <td>{{ documentTypeLabel(doc.document_type) }}</td>
                  <td>{{ doc.original_name }}</td>
                  <td>
                    <v-chip size="small" :color="statusColor(doc.review_status)" variant="tonal">
                      {{ statusLabel(doc.review_status) }}
                    </v-chip>
                  </td>
                  <td>{{ formatDateTime(doc.uploaded_at) }}</td>
                  <td>{{ formatDateTime(doc.reviewed_at) }}</td>
                  <td>
                    <div class="d-flex flex-column ga-2" style="min-width: 280px;">
                      <v-btn
                        size="small"
                        variant="tonal"
                        :loading="downloadingDocumentId === doc.id"
                        @click="openDocument(doc)"
                      >
                        Abrir documento
                      </v-btn>

                      <v-textarea
                        v-model="documentNotes[doc.id]"
                        rows="2"
                        density="comfortable"
                        label="Observaciones del documento"
                        hide-details
                      />

                      <div class="d-flex ga-2 flex-wrap">
                        <v-btn
                          size="small"
                          color="success"
                          variant="tonal"
                          :loading="acting"
                          @click="reviewDocument(doc.id, 'approved')"
                        >
                          Aprobar documento
                        </v-btn>
                        <v-btn
                          size="small"
                          color="error"
                          variant="tonal"
                          :loading="acting"
                          @click="reviewDocument(doc.id, 'rejected')"
                        >
                          Rechazar documento
                        </v-btn>
                      </div>
                    </div>
                  </td>
                </tr>

                <tr v-if="detail.documents.length === 0">
                  <td colspan="6">La solicitud no tiene documentos cargados.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>

        <v-card v-if="detail" class="mb-6">
          <v-card-title>Decisión final</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="4">
                <v-textarea
                  v-model="decisionNotes.approval"
                  label="Notas para aprobar"
                  rows="4"
                />
                <v-btn
                  block
                  color="success"
                  :loading="acting"
                  :disabled="!canApproveSubmission()"
                  @click="approveSubmission"
                >
                  Aprobar solicitud
                </v-btn>
              </v-col>

              <v-col cols="12" md="4">
                <v-textarea
                  v-model="decisionNotes.correction"
                  label="Observaciones para corrección"
                  rows="4"
                />
                <v-btn
                  block
                  color="deep-orange"
                  :loading="acting"
                  :disabled="!canRequestCorrection()"
                  @click="requestCorrection"
                >
                  Solicitar corrección
                </v-btn>
              </v-col>

              <v-col cols="12" md="4">
                <v-textarea
                  v-model="decisionNotes.rejection"
                  label="Motivo del rechazo"
                  rows="4"
                />
                <v-btn
                  block
                  color="error"
                  :loading="acting"
                  :disabled="!canRejectSubmission()"
                  @click="rejectSubmission"
                >
                  Rechazar solicitud
                </v-btn>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <v-card v-if="detail">
          <v-card-title>Historial</v-card-title>
          <v-card-text>
            <v-timeline density="compact" side="end" align="start">
              <v-timeline-item
                v-for="event in detail.events"
                :key="event.id"
                :dot-color="statusColor(event.event_type)"
                size="small"
              >
                <div class="d-flex flex-column ga-1">
                  <div class="d-flex flex-wrap align-center ga-2">
                    <strong>{{ eventTypeLabel(event.event_type) }}</strong>
                    <v-chip size="x-small" variant="tonal">
                      {{ formatDateTime(event.created_at) }}
                    </v-chip>
                    <v-chip size="x-small" variant="outlined">
                      Usuario {{ event.created_by_id || 'sistema' }}
                    </v-chip>
                  </div>
                  <pre class="text-caption bg-grey-lighten-4 pa-3 rounded">{{ prettyEventPayload(event.event_payload) }}</pre>
                </div>
              </v-timeline-item>
            </v-timeline>

            <div v-if="detail.events.length === 0" class="text-medium-emphasis">
              La solicitud aún no tiene eventos registrados.
            </div>
          </v-card-text>
        </v-card>

        <v-card v-else>
          <v-card-text class="text-medium-emphasis py-8">
            Se debe seleccionar una solicitud para revisar el expediente documental.
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
