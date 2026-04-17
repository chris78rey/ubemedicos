<script setup lang="ts">
type AuditActor = {
  id: number
  email: string
  role: string
  first_name: string
  last_name: string
} | null

type AuditEventItem = {
  id: number
  actor: AuditActor
  event_type: string
  entity_type: string
  entity_id: string
  metadata: Record<string, any>
  created_at: string | null
}

type PaginationInfo = {
  page: number
  page_size: number
  total: number
  has_next: boolean
}

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loading = ref(false)
const exporting = ref(false)
const detailLoading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const items = ref<AuditEventItem[]>([])
const selectedEvent = ref<AuditEventItem | null>(null)
const detailDialog = ref(false)
const detailEventId = ref<number | null>(null)

const pagination = reactive<PaginationInfo>({
  page: 1,
  page_size: 25,
  total: 0,
  has_next: false,
})

const filters = reactive({
  actor_email: '',
  event_type: '',
  entity_type: '',
  entity_id: '',
  created_from: '',
  created_to: '',
})

function authHeaders() {
  return token.value
    ? { Authorization: `Bearer ${token.value}` }
    : {}
}

function actorLabel(actor: AuditActor) {
  if (!actor) return 'Sistema'
  const fullName = `${actor.first_name || ''} ${actor.last_name || ''}`.trim()
  if (fullName) return `${fullName} (${actor.email})`
  return actor.email
}

function roleLabel(role: string | undefined) {
  const labels: Record<string, string> = {
    admin: 'Administrador',
    super_admin: 'Super administrador',
    privacy_auditor: 'Auditor de privacidad',
    professional: 'Profesional',
    patient: 'Paciente',
  }
  if (!role) return '—'
  return labels[role] || role
}

function formatDateTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function prettyMetadata(value: Record<string, any> | null | undefined) {
  return JSON.stringify(value || {}, null, 2)
}

const totalPages = computed(() => {
  if (!pagination.total || !pagination.page_size) return 1
  return Math.max(1, Math.ceil(pagination.total / pagination.page_size))
})

const activeFilterCount = computed(() => {
  let count = 0
  Object.values(filters).forEach((value) => {
    if (String(value || '').trim()) count += 1
  })
  return count
})

function buildQuery(params?: { includePage?: boolean; exportLimit?: number }) {
  const query = new URLSearchParams()

  if (filters.actor_email.trim()) query.set('actor_email', filters.actor_email.trim())
  if (filters.event_type.trim()) query.set('event_type', filters.event_type.trim())
  if (filters.entity_type.trim()) query.set('entity_type', filters.entity_type.trim())
  if (filters.entity_id.trim()) query.set('entity_id', filters.entity_id.trim())
  if (filters.created_from.trim()) query.set('created_from', filters.created_from.trim())
  if (filters.created_to.trim()) query.set('created_to', filters.created_to.trim())

  if (params?.includePage !== false) {
    query.set('page', String(pagination.page))
    query.set('page_size', String(pagination.page_size))
  }

  if (params?.exportLimit) {
    query.set('limit', String(params.exportLimit))
  }

  return query.toString()
}

async function loadAuditLogs() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    const response = await $fetch<{
      items: AuditEventItem[]
      pagination: PaginationInfo
    }>(`${apiBase.value}/admin/audits/access-logs?${buildQuery()}`, {
      headers: authHeaders(),
    })

    items.value = response.items || []
    pagination.page = response.pagination?.page || 1
    pagination.page_size = response.pagination?.page_size || 25
    pagination.total = response.pagination?.total || 0
    pagination.has_next = !!response.pagination?.has_next
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudieron cargar los logs de auditoría.'
  } finally {
    loading.value = false
  }
}

async function openEventDetail(eventId: number) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  detailLoading.value = true
  detailEventId.value = eventId
  errorMessage.value = ''

  try {
    const response = await $fetch<AuditEventItem>(
      `${apiBase.value}/admin/audits/access-logs/${eventId}`,
      {
        headers: authHeaders(),
      }
    )

    selectedEvent.value = response
    detailDialog.value = true
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar el detalle del evento.'
  } finally {
    detailLoading.value = false
    detailEventId.value = null
  }
}

async function exportCsv() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  exporting.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    const response = await fetch(
      `${apiBase.value}/admin/audits/access-logs/export.csv?${buildQuery({ includePage: false, exportLimit: 5000 })}`,
      {
        method: 'GET',
        headers: authHeaders(),
      }
    )

    if (!response.ok) {
      let detail = 'No se pudo exportar el CSV.'
      try {
        const payload = await response.json()
        detail = payload?.detail || detail
      } catch {
        // mantener mensaje por defecto
      }
      throw new Error(detail)
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-')

    link.href = url
    link.download = `audit_logs_${timestamp}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    successMessage.value = 'CSV exportado correctamente.'
  } catch (error: any) {
    errorMessage.value = error?.message || 'No se pudo exportar el CSV.'
  } finally {
    exporting.value = false
  }
}

function applyFilters() {
  pagination.page = 1
  loadAuditLogs()
}

function clearFilters() {
  filters.actor_email = ''
  filters.event_type = ''
  filters.entity_type = ''
  filters.entity_id = ''
  filters.created_from = ''
  filters.created_to = ''
  pagination.page = 1
  loadAuditLogs()
}

function changePage(page: number) {
  if (page < 1 || page > totalPages.value) return
  pagination.page = page
  loadAuditLogs()
}

function goBackToAdmin() {
  return navigateTo('/admin')
}

onMounted(async () => {
  await loadAuditLogs()
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Logs de acceso y auditoría</h1>
        <p class="text-medium-emphasis">
          Pantalla administrativa para privacidad, trazabilidad y exportación controlada de eventos.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2 flex-wrap">
        <v-btn variant="outlined" @click="goBackToAdmin">
          Volver
        </v-btn>
        <v-btn color="primary" :loading="loading" @click="loadAuditLogs">
          Recargar
        </v-btn>
        <v-btn color="success" variant="flat" :loading="exporting" @click="exportCsv">
          Exportar CSV
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
      <v-col cols="12" md="3">
        <v-text-field
          v-model="filters.actor_email"
          label="Correo del actor"
          variant="outlined"
          density="comfortable"
          clearable
        />
      </v-col>

      <v-col cols="12" md="2">
        <v-text-field
          v-model="filters.event_type"
          label="Tipo de evento"
          variant="outlined"
          density="comfortable"
          clearable
        />
      </v-col>

      <v-col cols="12" md="2">
        <v-text-field
          v-model="filters.entity_type"
          label="Tipo de entidad"
          variant="outlined"
          density="comfortable"
          clearable
        />
      </v-col>

      <v-col cols="12" md="2">
        <v-text-field
          v-model="filters.entity_id"
          label="ID entidad"
          variant="outlined"
          density="comfortable"
          clearable
        />
      </v-col>

      <v-col cols="12" md="1">
        <v-text-field
          v-model="filters.created_from"
          type="date"
          label="Desde"
          variant="outlined"
          density="comfortable"
        />
      </v-col>

      <v-col cols="12" md="1">
        <v-text-field
          v-model="filters.created_to"
          type="date"
          label="Hasta"
          variant="outlined"
          density="comfortable"
        />
      </v-col>
    </v-row>

    <v-row class="mb-4">
      <v-col cols="12" class="d-flex flex-wrap ga-2 align-center">
        <v-btn color="primary" @click="applyFilters">
          Aplicar filtros
        </v-btn>
        <v-btn variant="outlined" @click="clearFilters">
          Limpiar filtros
        </v-btn>
        <v-chip variant="tonal">
          {{ activeFilterCount }} filtros activos
        </v-chip>
        <v-chip variant="tonal">
          {{ pagination.total }} registros totales
        </v-chip>
      </v-col>
    </v-row>

    <v-card>
      <v-card-title class="d-flex justify-space-between align-center flex-wrap ga-3">
        <span>Eventos visibles</span>
        <v-select
          :model-value="pagination.page_size"
          :items="[10, 25, 50, 100]"
          label="Filas"
          variant="outlined"
          density="compact"
          hide-details
          style="max-width: 120px"
          @update:model-value="(value) => { pagination.page_size = Number(value); pagination.page = 1; loadAuditLogs() }"
        />
      </v-card-title>

      <v-card-text>
        <v-progress-linear v-if="loading" indeterminate class="mb-4" />

        <v-table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Fecha</th>
              <th>Actor</th>
              <th>Rol</th>
              <th>Evento</th>
              <th>Entidad</th>
              <th>ID entidad</th>
              <th class="text-right">Acción</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>#{{ item.id }}</td>
              <td>{{ formatDateTime(item.created_at) }}</td>
              <td>{{ actorLabel(item.actor) }}</td>
              <td>{{ roleLabel(item.actor?.role) }}</td>
              <td>{{ item.event_type }}</td>
              <td>{{ item.entity_type }}</td>
              <td>{{ item.entity_id || '—' }}</td>
              <td class="text-right">
                <v-btn
                  size="small"
                  variant="text"
                  :loading="detailLoading && detailEventId === item.id"
                  @click="openEventDetail(item.id)"
                >
                  Ver detalle
                </v-btn>
              </td>
            </tr>
            <tr v-if="!loading && items.length === 0">
              <td colspan="8" class="text-center py-6 text-medium-emphasis">
                No existen eventos para los filtros aplicados.
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>

      <v-divider />

      <v-card-actions class="d-flex justify-space-between flex-wrap ga-3 px-4 py-3">
        <div class="text-body-2 text-medium-emphasis">
          Página {{ pagination.page }} de {{ totalPages }}
        </div>

        <div class="d-flex ga-2">
          <v-btn
            variant="outlined"
            :disabled="pagination.page <= 1 || loading"
            @click="changePage(pagination.page - 1)"
          >
            Anterior
          </v-btn>
          <v-btn
            variant="outlined"
            :disabled="!pagination.has_next || loading"
            @click="changePage(pagination.page + 1)"
          >
            Siguiente
          </v-btn>
        </div>
      </v-card-actions>
    </v-card>

    <v-dialog v-model="detailDialog" max-width="900">
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center flex-wrap ga-3">
          <span>Detalle de evento</span>
          <v-chip v-if="selectedEvent" variant="tonal">
            #{{ selectedEvent.id }}
          </v-chip>
        </v-card-title>

        <v-card-text v-if="selectedEvent">
          <v-row>
            <v-col cols="12" md="6">
              <div class="mb-2"><strong>Fecha:</strong> {{ formatDateTime(selectedEvent.created_at) }}</div>
              <div class="mb-2"><strong>Evento:</strong> {{ selectedEvent.event_type }}</div>
              <div class="mb-2"><strong>Entidad:</strong> {{ selectedEvent.entity_type }}</div>
              <div class="mb-2"><strong>ID entidad:</strong> {{ selectedEvent.entity_id || '—' }}</div>
            </col>

            <v-col cols="12" md="6">
              <div class="mb-2"><strong>Actor:</strong> {{ actorLabel(selectedEvent.actor) }}</div>
              <div class="mb-2"><strong>Rol:</strong> {{ roleLabel(selectedEvent.actor?.role) }}</div>
              <div class="mb-2"><strong>Actor ID:</strong> {{ selectedEvent.actor?.id || '—' }}</div>
              <div class="mb-2"><strong>Email:</strong> {{ selectedEvent.actor?.email || '—' }}</div>
            </col>
          </v-row>

          <v-divider class="my-4" />

          <div class="text-subtitle-1 mb-2">Metadata JSON</div>
          <v-textarea
            :model-value="prettyMetadata(selectedEvent.metadata)"
            variant="outlined"
            rows="14"
            readonly
            auto-grow
          />
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="outlined" @click="detailDialog = false">
            Cerrar
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
