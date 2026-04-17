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

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loading = ref(false)
const errorMessage = ref('')
const submissions = ref<SubmissionItem[]>([])

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

function formatDateTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

const summaryCards = computed(() => {
  const counts: Record<string, number> = {
    total: submissions.value.length,
    submitted: 0,
    under_review: 0,
    needs_correction: 0,
    approved: 0,
    rejected: 0,
  }

  submissions.value.forEach((item) => {
    if (typeof counts[item.status] === 'number') {
      counts[item.status] += 1
    }
  })

  return [
    {
      title: 'Solicitudes visibles',
      value: counts.total,
      color: 'primary',
      subtitle: 'Total cargado en la bandeja administrativa.',
    },
    {
      title: 'Pendientes de atención',
      value: counts.submitted,
      color: 'warning',
      subtitle: 'Casos enviados y todavía no iniciados.',
    },
    {
      title: 'En revisión',
      value: counts.under_review,
      color: 'info',
      subtitle: 'Solicitudes que ya están siendo revisadas.',
    },
    {
      title: 'Con corrección solicitada',
      value: counts.needs_correction,
      color: 'deep-orange',
      subtitle: 'Expedientes devueltos al profesional.',
    },
  ]
})

const recentItems = computed(() => submissions.value.slice(0, 8))

async function loadDashboard() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const response = await $fetch<{ items: SubmissionItem[] }>(
      `${apiBase.value}/admin/professional-verifications`,
      {
        headers: authHeaders(),
      }
    )

    submissions.value = response.items || []
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar el dashboard administrativo.'
  } finally {
    loading.value = false
  }
}

function openVerificationPanel(submissionId?: number) {
  const query: Record<string, string> = {
    mine: '0',
  }

  if (submissionId) {
    query.submission_id = String(submissionId)
  }

  return navigateTo({
    path: '/admin/professional-verifications',
    query,
  })
}

function openPaymentsPanel() {
  return navigateTo('/admin/payments')
}

function openAuditLogsPanel() {
  return navigateTo('/admin/privacy/access-logs')
}

onMounted(async () => {
  await loadDashboard()
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Dashboard administrativo</h1>
        <p class="text-medium-emphasis">
          Punto de entrada del administrador para revisar solicitudes y abrir casos operativos.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2">
        <v-btn color="primary" :loading="loading" @click="loadDashboard">
          Recargar
        </v-btn>
      </v-col>
    </v-row>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4">
      {{ errorMessage }}
    </v-alert>

    <v-row class="mb-2">
      <v-col v-for="card in summaryCards" :key="card.title" cols="12" sm="6" lg="3">
        <v-card height="100%">
          <v-card-text>
            <div class="text-body-2 text-medium-emphasis mb-2">{{ card.title }}</div>
            <div class="text-h4 font-weight-bold mb-2">{{ card.value }}</div>
            <v-chip :color="card.color" variant="tonal" class="mb-3">
              Estado resumido
            </v-chip>
            <div class="text-body-2 text-medium-emphasis">{{ card.subtitle }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" lg="4">
        <v-card height="100%">
          <v-card-title>Accesos rápidos</v-card-title>
          <v-card-text class="d-flex flex-column ga-4">
            <v-card variant="outlined">
              <v-card-text>
                <div class="text-h6 mb-2">Validación profesional</div>
                <div class="text-body-2 text-medium-emphasis mb-4">
                  Abre la bandeja completa para asignar, revisar documentos y decidir el resultado final.
                </div>
                <v-btn color="primary" block @click="openVerificationPanel()">
                  Abrir panel
                </v-btn>
              </v-card-text>
            </v-card>

            <v-card variant="outlined">
              <v-card-text>
                <div class="text-h6 mb-2">Pagos administrativos</div>
                <div class="text-body-2 text-medium-emphasis mb-4">
                  Permite revisar pagos demo y decidir manualmente si se aprueban o fallan.
                </div>
                <v-btn color="success" block @click="openPaymentsPanel()">
                  Abrir pagos
                </v-btn>
              </v-card-text>
            </v-card>

            <v-card variant="outlined">
              <v-card-text>
                <div class="text-h6 mb-2">Privacidad y auditoría</div>
                <div class="text-body-2 text-medium-emphasis mb-4">
                  Permite filtrar trazabilidad, revisar eventos sensibles y exportar CSV controlado.
                </div>
                <v-btn color="secondary" block @click="openAuditLogsPanel()">
                  Abrir auditoría
                </v-btn>
              </v-card-text>
            </v-card>

            <v-card variant="outlined">
              <v-card-text>
                <div class="text-h6 mb-2">Observación operativa</div>
                <div class="text-body-2 text-medium-emphasis">
                  Como el snapshot no trae sidebar ni layout global, este dashboard funciona como menú administrativo real.
                </div>
              </v-card-text>
            </v-card>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="8">
        <v-card>
          <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-3">
            <span>Solicitudes recientes</span>
            <v-chip variant="tonal">{{ submissions.length }} visibles</v-chip>
          </v-card-title>

          <v-card-text>
            <v-table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Profesional</th>
                  <th>Estado</th>
                  <th>Especialidad</th>
                  <th>Enviada</th>
                  <th class="text-right">Acción</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in recentItems" :key="item.id">
                  <td>#{{ item.id }}</td>
                  <td>
                    <div class="font-weight-medium">{{ item.professional_name || 'Sin nombre' }}</div>
                    <div class="text-caption text-medium-emphasis">{{ item.professional_email }}</div>
                  </td>
                  <td>
                    <v-chip :color="statusColor(item.status)" variant="tonal" size="small">
                      {{ statusLabel(item.status) }}
                    </v-chip>
                  </td>
                  <td>{{ item.specialty || 'Sin especialidad' }}</td>
                  <td>{{ formatDateTime(item.submitted_at) }}</td>
                  <td class="text-right">
                    <v-btn size="small" variant="text" @click="openVerificationPanel(item.id)">
                      Abrir
                    </v-btn>
                  </td>
                </tr>
                <tr v-if="recentItems.length === 0">
                  <td colspan="6" class="text-center py-6 text-medium-emphasis">
                    No existen solicitudes visibles.
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
