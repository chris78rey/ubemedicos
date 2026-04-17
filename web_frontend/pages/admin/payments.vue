<script setup lang="ts">
type PaymentItem = {
  id: number
  external_reference: string
  amount: string
  currency: string
  status: string
  paid_at: string | null
  created_at: string
  raw_response?: Record<string, any>
  appointment: {
    id: number
    status: string
    is_paid: boolean
    scheduled_at: string
    ends_at: string
    modality: string
    price: string
    professional: {
      id: number
      name: string
      specialty: string | null
    }
    patient: {
      id: number
      name: string
    }
  }
}

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loading = ref(false)
const acting = ref(false)
const actingPaymentId = ref<number | null>(null)
const errorMessage = ref('')
const successMessage = ref('')

const payments = ref<PaymentItem[]>([])

const filters = reactive({
  status: '',
  reference: '',
  professional: '',
  patient: '',
})

const notesByPayment = reactive<Record<number, string>>({})

const availableStatuses = [
  { title: 'Todos', value: '' },
  { title: 'Pendiente', value: 'pending' },
  { title: 'Exitoso', value: 'succeeded' },
  { title: 'Fallido', value: 'failed' },
  { title: 'Reembolsado', value: 'refunded' },
]

function authHeaders() {
  return token.value
    ? { Authorization: `Bearer ${token.value}` }
    : {}
}

function formatDateTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function modalityLabel(value: string) {
  return value === 'teleconsultation' ? 'Teleconsulta' : 'Presencial'
}

function paymentStatusLabel(value: string) {
  const labels: Record<string, string> = {
    pending: 'Pendiente',
    succeeded: 'Exitoso',
    failed: 'Fallido',
    refunded: 'Reembolsado',
  }

  return labels[value] || value
}

function paymentStatusColor(value: string) {
  const colors: Record<string, string> = {
    pending: 'warning',
    succeeded: 'success',
    failed: 'error',
    refunded: 'info',
  }

  return colors[value] || 'default'
}

function appointmentStatusLabel(value: string) {
  const labels: Record<string, string> = {
    pending_confirmation: 'Pendiente de confirmación',
    confirmed: 'Confirmada',
    cancelled_by_patient: 'Cancelada por paciente',
    cancelled_by_professional: 'Cancelada por profesional',
    completed: 'Completada',
    no_show_patient: 'No asistió paciente',
    no_show_professional: 'No asistió profesional',
  }

  return labels[value] || value
}

function appointmentStatusColor(value: string) {
  const colors: Record<string, string> = {
    pending_confirmation: 'warning',
    confirmed: 'primary',
    cancelled_by_patient: 'grey',
    cancelled_by_professional: 'grey',
    completed: 'success',
    no_show_patient: 'error',
    no_show_professional: 'error',
  }

  return colors[value] || 'default'
}

const summaryCards = computed(() => {
  const counts = {
    total: payments.value.length,
    pending: 0,
    succeeded: 0,
    failed: 0,
    refunded: 0,
  }

  payments.value.forEach((item) => {
    if (item.status === 'pending') counts.pending += 1
    if (item.status === 'succeeded') counts.succeeded += 1
    if (item.status === 'failed') counts.failed += 1
    if (item.status === 'refunded') counts.refunded += 1
  })

  return [
    {
      title: 'Pagos visibles',
      value: counts.total,
      color: 'primary',
      subtitle: 'Total cargado con el filtro actual.',
    },
    {
      title: 'Pendientes',
      value: counts.pending,
      color: 'warning',
      subtitle: 'Requieren decisión administrativa.',
    },
    {
      title: 'Exitosos',
      value: counts.succeeded,
      color: 'success',
      subtitle: 'Ya impactaron a la cita asociada.',
    },
    {
      title: 'Fallidos',
      value: counts.failed,
      color: 'error',
      subtitle: 'Pueden reintentarse según el caso.',
    },
  ]
})

const filteredPayments = computed(() => {
  return payments.value.filter((item) => {
    const matchesReference = !filters.reference.trim()
      ? true
      : item.external_reference.toLowerCase().includes(filters.reference.trim().toLowerCase())

    const professionalName = item.appointment.professional.name || ''
    const patientName = item.appointment.patient.name || ''

    const matchesProfessional = !filters.professional.trim()
      ? true
      : professionalName.toLowerCase().includes(filters.professional.trim().toLowerCase())

    const matchesPatient = !filters.patient.trim()
      ? true
      : patientName.toLowerCase().includes(filters.patient.trim().toLowerCase())

    return matchesReference && matchesProfessional && matchesPatient
  })
})

function canMarkSucceeded(payment: PaymentItem) {
  const appointmentStatus = payment.appointment.status
  const terminalStatuses = [
    'cancelled_by_patient',
    'cancelled_by_professional',
    'completed',
    'no_show_patient',
    'no_show_professional',
  ]

  if (payment.status === 'succeeded') return false
  if (payment.status === 'refunded') return false
  if (terminalStatuses.includes(appointmentStatus)) return false
  return true
}

function canMarkFailed(payment: PaymentItem) {
  return payment.status !== 'succeeded'
}

async function loadPayments() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const query = new URLSearchParams()
    if (filters.status) {
      query.set('status', filters.status)
    }

    const url = query.toString()
      ? `${apiBase.value}/admin/payments?${query.toString()}`
      : `${apiBase.value}/admin/payments`

    const response = await $fetch<{ items: PaymentItem[] }>(url, {
      headers: authHeaders(),
    })

    payments.value = response.items || []
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar la bandeja administrativa de pagos.'
  } finally {
    loading.value = false
  }
}

async function runAction(payment: PaymentItem, action: 'mark-succeeded' | 'mark-failed') {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  acting.value = true
  actingPaymentId.value = payment.id
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(`${apiBase.value}/admin/payments/${payment.id}/${action}`, {
      method: 'POST',
      headers: {
        ...authHeaders(),
        'Content-Type': 'application/json',
      },
      body: {
        notes: notesByPayment[payment.id] || '',
      },
    })

    successMessage.value =
      action === 'mark-succeeded'
        ? 'Pago marcado como exitoso correctamente.'
        : 'Pago marcado como fallido correctamente.'

    await loadPayments()
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo ejecutar la acción solicitada sobre el pago.'
  } finally {
    acting.value = false
    actingPaymentId.value = null
  }
}

onMounted(async () => {
  await loadPayments()
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Pagos administrativos</h1>
        <p class="text-medium-emphasis">
          Bandeja para revisar pagos demo y decidir manualmente si se marcan como exitosos o fallidos.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2 flex-wrap">
        <v-btn variant="outlined" @click="navigateTo('/admin')">
          Volver al dashboard
        </v-btn>
        <v-btn color="primary" :loading="loading" @click="loadPayments">
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

    <v-card class="mb-4">
      <v-card-title>Filtros</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" md="3">
            <v-select
              v-model="filters.status"
              :items="availableStatuses"
              label="Estado"
              variant="outlined"
              density="comfortable"
              @update:model-value="loadPayments"
            />
          </v-col>

          <v-col cols="12" md="3">
            <v-text-field
              v-model="filters.reference"
              label="Referencia externa"
              variant="outlined"
              density="comfortable"
              clearable
            />
          </v-col>

          <v-col cols="12" md="3">
            <v-text-field
              v-model="filters.professional"
              label="Profesional"
              variant="outlined"
              density="comfortable"
              clearable
            />
          </v-col>

          <v-col cols="12" md="3">
            <v-text-field
              v-model="filters.patient"
              label="Paciente"
              variant="outlined"
              density="comfortable"
              clearable
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-row v-if="!loading && filteredPayments.length === 0">
      <v-col cols="12">
        <v-card>
          <v-card-text>No existen pagos para mostrar con los filtros actuales.</v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col
        v-for="payment in filteredPayments"
        :key="payment.id"
        cols="12"
      >
        <v-card>
          <v-card-item>
            <template #title>
              <div class="d-flex flex-wrap ga-3 align-center">
                <span>Pago #{{ payment.id }}</span>
                <v-chip :color="paymentStatusColor(payment.status)" size="small" variant="tonal">
                  {{ paymentStatusLabel(payment.status) }}
                </v-chip>
                <v-chip :color="appointmentStatusColor(payment.appointment.status)" size="small" variant="tonal">
                  {{ appointmentStatusLabel(payment.appointment.status) }}
                </v-chip>
              </div>
            </template>

            <template #subtitle>
              {{ payment.external_reference }}
            </template>
          </v-card-item>

          <v-card-text>
            <v-row>
              <v-col cols="12" md="4">
                <div><strong>Paciente:</strong> {{ payment.appointment.patient.name || 'Sin nombre' }}</div>
                <div><strong>Profesional:</strong> {{ payment.appointment.professional.name || 'Sin nombre' }}</div>
                <div><strong>Especialidad:</strong> {{ payment.appointment.professional.specialty || 'Sin especialidad' }}</div>
              </v-col>

              <v-col cols="12" md="4">
                <div><strong>Valor:</strong> {{ payment.currency }} {{ payment.amount }}</div>
                <div><strong>Creado:</strong> {{ formatDateTime(payment.created_at) }}</div>
                <div><strong>Pagado en:</strong> {{ formatDateTime(payment.paid_at) }}</div>
              </v-col>

              <v-col cols="12" md="4">
                <div><strong>Cita:</strong> #{{ payment.appointment.id }}</div>
                <div><strong>Inicio:</strong> {{ formatDateTime(payment.appointment.scheduled_at) }}</div>
                <div><strong>Modalidad:</strong> {{ modalityLabel(payment.appointment.modality) }}</div>
              </v-col>
            </row>

            <v-divider class="my-4" />

            <v-textarea
              v-model="notesByPayment[payment.id]"
              label="Notas administrativas"
              variant="outlined"
              density="comfortable"
              rows="2"
              placeholder="Ejemplo: validado contra comprobante externo"
              class="mb-4"
            />

            <div v-if="payment.raw_response" class="text-caption text-medium-emphasis mb-4">
              Último proveedor: {{ payment.raw_response.provider || 'N/D' }} ·
              Última decisión: {{ payment.raw_response.decision || 'N/D' }}
            </div>
          </v-card-text>

          <v-divider />

          <v-card-actions class="flex-wrap ga-2">
            <v-btn
              color="success"
              variant="flat"
              :disabled="!canMarkSucceeded(payment)"
              :loading="acting && actingPaymentId === payment.id"
              @click="runAction(payment, 'mark-succeeded')"
            >
              Marcar exitoso
            </v-btn>

            <v-btn
              color="error"
              variant="tonal"
              :disabled="!canMarkFailed(payment)"
              :loading="acting && actingPaymentId === payment.id"
              @click="runAction(payment, 'mark-failed')"
            >
              Marcar fallido
            </v-btn>

            <v-spacer />

            <span class="text-caption text-medium-emphasis">
              is_paid actual: {{ payment.appointment.is_paid ? 'Sí' : 'No' }}
            </span>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
