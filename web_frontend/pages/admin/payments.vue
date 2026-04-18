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
const cancelAsByPayment = reactive<Record<number, 'patient' | 'professional'>>({})

const cancelOriginOptions = [
  { title: 'Como paciente', value: 'patient' },
  { title: 'Como profesional', value: 'professional' },
]

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

const filteredPayments = computed(() => {
  return payments.value.filter((item) => {
    const matchesStatus = !filters.status || item.status === filters.status
    const matchesReference =
      !filters.reference ||
      item.external_reference.toLowerCase().includes(filters.reference.toLowerCase())
    const matchesProfessional =
      !filters.professional ||
      item.appointment.professional.name.toLowerCase().includes(filters.professional.toLowerCase())
    const matchesPatient =
      !filters.patient ||
      item.appointment.patient.name.toLowerCase().includes(filters.patient.toLowerCase())

    return matchesStatus && matchesReference && matchesProfessional && matchesPatient
  })
})

const summaryCards = computed(() => {
  const total = payments.value.length
  const pending = payments.value.filter(item => item.status === 'pending').length
  const succeeded = payments.value.filter(item => item.status === 'succeeded').length
  const failed = payments.value.filter(item => item.status === 'failed').length
  const refunded = payments.value.filter(item => item.status === 'refunded').length

  return [
    { title: 'Total', value: total, color: 'default' },
    { title: 'Pendientes', value: pending, color: 'warning' },
    { title: 'Exitosos', value: succeeded, color: 'success' },
    { title: 'Fallidos', value: failed, color: 'error' },
    { title: 'Reembolsados', value: refunded, color: 'info' },
  ]
})

function canMarkSucceeded(payment: PaymentItem) {
  if (payment.status === 'succeeded' || payment.status === 'refunded') return false
  return ![
    'cancelled_by_patient',
    'cancelled_by_professional',
    'completed',
    'no_show_patient',
    'no_show_professional',
  ].includes(payment.appointment.status)
}

function canMarkFailed(payment: PaymentItem) {
  return payment.status !== 'succeeded'
}

function canMarkRefunded(payment: PaymentItem) {
  return payment.status === 'succeeded'
}

function canResolvePaidAppointment(payment: PaymentItem) {
  if (payment.status !== 'succeeded' && payment.status !== 'refunded') return false
  return ![
    'cancelled_by_patient',
    'cancelled_by_professional',
    'completed',
    'no_show_patient',
    'no_show_professional',
  ].includes(payment.appointment.status)
}

function resolvePaidAppointmentButtonText(payment: PaymentItem) {
  if (payment.status === 'refunded') return 'Re-cancelar cita'
  return 'Reembolsar y cancelar cita'
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

async function runAction(
  payment: PaymentItem,
  action: 'mark-succeeded' | 'mark-failed' | 'mark-refunded' | 'refund-and-cancel-appointment'
) {
  if (action === 'refund-and-cancel-appointment' && !cancelAsByPayment[payment.id]) {
    errorMessage.value = 'Debe seleccionar el origen de la cancelación (paciente/profesional).'
    return
  }
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
        cancel_as: action === 'refund-and-cancel-appointment'
          ? cancelAsByPayment[payment.id]
          : undefined,
      },
    })

    successMessage.value =
      action === 'mark-succeeded'
        ? 'Pago marcado como exitoso correctamente.'
        : action === 'mark-failed'
          ? 'Pago marcado como fallido correctamente.'
          : action === 'mark-refunded'
            ? 'Pago marcado como reembolsado correctamente.'
            : 'Pago y cita resueltos correctamente.'

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
          Bandeja para revisar pagos demo y resolver también citas pagadas en una sola operación administrativa.
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

    <v-row class="mb-4">
      <v-col
        v-for="card in summaryCards"
        :key="card.title"
        cols="12"
        sm="6"
        md="4"
        lg="2"
      >
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-medium-emphasis">{{ card.title }}</div>
            <div class="text-h5 font-weight-bold">
              <v-chip :color="card.color" variant="tonal">
                {{ card.value }}
              </v-chip>
            </div>
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
              item-title="title"
              item-value="value"
              label="Estado"
              clearable
              density="comfortable"
              @update:model-value="loadPayments"
            />
          </v-col>

          <v-col cols="12" md="3">
            <v-text-field
              v-model="filters.reference"
              label="Referencia"
              density="comfortable"
              clearable
            />
          </v-col>

          <v-col cols="12" md="3">
            <v-text-field
              v-model="filters.professional"
              label="Profesional"
              density="comfortable"
              clearable
            />
          </v-col>

          <v-col cols="12" md="3">
            <v-text-field
              v-model="filters.patient"
              label="Paciente"
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
          <v-card-text>
            No existen pagos para los filtros seleccionados.
          </v-card-text>
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
              Pago #{{ payment.id }} · {{ payment.external_reference }}
            </template>
            <template #subtitle>
              {{ payment.appointment.patient.name }} · {{ payment.appointment.professional.name }}
            </template>
          </v-card-item>

          <v-card-text>
            <v-row>
              <v-col cols="12" md="4">
                <div><strong>Monto:</strong> {{ payment.amount }} {{ payment.currency }}</div>
                <div><strong>Estado pago:</strong>
                  <v-chip :color="paymentStatusColor(payment.status)" variant="tonal" size="small" class="ml-2">
                    {{ paymentStatusLabel(payment.status) }}
                  </v-chip>
                </div>
                <div><strong>Pagado en:</strong> {{ formatDateTime(payment.paid_at) }}</div>
              </v-col>

              <v-col cols="12" md="4">
                <div><strong>Cita:</strong> #{{ payment.appointment.id }}</div>
                <div><strong>Inicio:</strong> {{ formatDateTime(payment.appointment.scheduled_at) }}</div>
                <div><strong>Modalidad:</strong> {{ modalityLabel(payment.appointment.modality) }}</div>
              </v-col>

              <v-col cols="12" md="4">
                <div>
                  <strong>Estado cita:</strong>
                  <v-chip :color="appointmentStatusColor(payment.appointment.status)" variant="tonal" size="small" class="ml-2">
                    {{ appointmentStatusLabel(payment.appointment.status) }}
                  </v-chip>
                </div>
                <div><strong>Especialidad:</strong> {{ payment.appointment.professional.specialty || 'Sin especialidad' }}</div>
                <div><strong>Marcada pagada:</strong> {{ payment.appointment.is_paid ? 'Sí' : 'No' }}</div>
              </v-col>
            </v-row>

            <v-textarea
              v-model="notesByPayment[payment.id]"
              label="Notas administrativas"
              rows="2"
              auto-grow
              class="mt-4"
            />

            <v-select
              v-if="canResolvePaidAppointment(payment)"
              v-model="cancelAsByPayment[payment.id]"
              :items="cancelOriginOptions"
              item-title="title"
              item-value="value"
              label="Origen de cancelación para la resolución administrativa"
              density="comfortable"
              clearable
              class="mt-4"
            />

            <v-expansion-panels class="mt-3" variant="accordion">
              <v-expansion-panel>
                <v-expansion-panel-title>Respuesta cruda</v-expansion-panel-title>
                <v-expansion-panel-text>
                  <pre class="text-caption">{{ JSON.stringify(payment.raw_response || {}, null, 2) }}</pre>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
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

            <v-btn
              color="info"
              variant="tonal"
              :disabled="!canMarkRefunded(payment)"
              :loading="acting && actingPaymentId === payment.id"
              @click="runAction(payment, 'mark-refunded')"
            >
              Marcar reembolsado
            </v-btn>

            <v-btn
              color="info"
              variant="flat"
              :disabled="!canResolvePaidAppointment(payment)"
              :loading="acting && actingPaymentId === payment.id"
              @click="runAction(payment, 'refund-and-cancel-appointment')"
            >
              {{ resolvePaidAppointmentButtonText(payment) }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
