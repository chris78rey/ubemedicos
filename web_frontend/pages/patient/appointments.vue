<script setup lang="ts">
type AppointmentItem = {
  id: number
  scheduled_at: string
  ends_at: string
  modality: string
  status: string
  notes: string
  price: string
  is_paid: boolean
  patient: {
    id: number
    name: string
  }
  professional: {
    id: number
    name: string
    specialty: string | null
  }
}

type PaymentResolutionSummary = {
  kind: string
  message: string
  cancelled_as: string | null
  appointment_status_after: string | null
  refunded_at: string | null
}

type PaymentItem = {
  id: number
  external_reference: string
  amount: string
  currency: string
  status: string
  paid_at: string | null
  created_at: string
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
  resolution_summary?: PaymentResolutionSummary | null
}

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loading = ref(false)
const acting = ref(false)
const actingAppointmentId = ref<number | null>(null)

const errorMessage = ref('')
const successMessage = ref('')

const appointments = ref<AppointmentItem[]>([])
const payments = ref<PaymentItem[]>([])

const confirmCancelDialog = ref(false)
const targetAppointment = ref<AppointmentItem | null>(null)

function authHeaders() {
  return token.value
    ? { Authorization: `Bearer ${token.value}` }
    : {}
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString()
}

function formatNullableDateTime(value: string | null | undefined) {
  return value ? formatDateTime(value) : '—'
}

function modalityLabel(value: string) {
  if (value === 'teleconsultation') return 'Teleconsulta'
  return 'Presencial'
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

const paymentsByAppointment = computed<Record<number, PaymentItem>>(() => {
  const map: Record<number, PaymentItem> = {}
  for (const item of payments.value) {
    map[item.appointment.id] = item
  }
  return map
})

function paymentResolutionSummary(appointment: AppointmentItem) {
  return paymentsByAppointment.value[appointment.id]?.resolution_summary || null
}

function shouldShowResolutionBanner(appointment: AppointmentItem) {
  const payment = paymentsByAppointment.value[appointment.id]
  if (!payment) return false

  return Boolean(payment.resolution_summary) || payment.status === 'refunded'
}

function patientResolutionMessage(appointment: AppointmentItem) {
  const payment = paymentsByAppointment.value[appointment.id]
  const summary = paymentResolutionSummary(appointment)

  if (summary?.message) {
    return summary.message
  }

  if (payment?.status === 'refunded') {
    return 'El pago de esta cita fue reembolsado administrativamente.'
  }

  if (appointment.is_paid) {
    return 'Si la cita ya fue pagada, la resolución posterior depende del flujo administrativo.'
  }

  return ''
}

function showGenericPaidHint(appointment: AppointmentItem) {
  return appointment.is_paid && !shouldShowResolutionBanner(appointment)
}

function canCancel(appointment: AppointmentItem) {
  return (
    ['pending_confirmation', 'confirmed'].includes(appointment.status) &&
    !appointment.is_paid
  )
}

function canGeneratePayment(appointment: AppointmentItem) {
  if (!['pending_confirmation', 'confirmed'].includes(appointment.status)) {
    return false
  }

  const payment = paymentsByAppointment.value[appointment.id]
  if (!payment) return true
  return payment.status !== 'succeeded'
}

function paymentButtonText(appointment: AppointmentItem) {
  const payment = paymentsByAppointment.value[appointment.id]
  if (!payment) return 'Generar pago'
  if (payment.status === 'failed' || payment.status === 'refunded') return 'Reintentar pago'
  if (payment.status === 'pending') return 'Consultar pago pendiente'
  return 'Pago realizado'
}

async function loadData() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const [appointmentsResponse, paymentsResponse] = await Promise.all([
      $fetch<{ items: AppointmentItem[] }>(
        `${apiBase.value}/patient/appointments`,
        { headers: authHeaders() }
      ),
      $fetch<{ items: PaymentItem[] }>(
        `${apiBase.value}/patient/payments`,
        { headers: authHeaders() }
      ),
    ])

    appointments.value = appointmentsResponse.items || []
    payments.value = paymentsResponse.items || []
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudieron cargar las citas del paciente.'
  } finally {
    loading.value = false
  }
}

async function cancelAppointment(appointment: AppointmentItem) {
  targetAppointment.value = appointment
  confirmCancelDialog.value = true
}

async function confirmCancelAppointment() {
  if (!token.value || !targetAppointment.value) return

  acting.value = true
  actingAppointmentId.value = targetAppointment.value.id
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(`${apiBase.value}/patient/appointments/${targetAppointment.value.id}/cancel`, {
      method: 'POST',
      headers: {
        ...authHeaders(),
        'Content-Type': 'application/json',
      },
    })

    successMessage.value = 'Cita cancelada correctamente.'
    await loadData()
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cancelar la cita.'
  } finally {
    acting.value = false
    actingAppointmentId.value = null
    confirmCancelDialog.value = false
    targetAppointment.value = null
  }
}

async function createPaymentIntent(appointment: AppointmentItem) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  acting.value = true
  actingAppointmentId.value = appointment.id
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(`${apiBase.value}/patient/appointments/${appointment.id}/payment-intent`, {
      method: 'POST',
      headers: {
        ...authHeaders(),
        'Content-Type': 'application/json',
      },
    })

    successMessage.value = 'Intento de pago generado o actualizado correctamente.'
    await loadData()
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo generar el pago.'
  } finally {
    acting.value = false
    actingAppointmentId.value = null
  }
}

onMounted(async () => {
  await loadData()
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Mis citas</h1>
        <p class="text-medium-emphasis">
          Desde esta pantalla el paciente revisa sus citas y el estado de sus pagos.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2">
        <v-btn variant="outlined" @click="navigateTo('/')">
          Buscar profesionales
        </v-btn>
        <v-btn color="primary" :loading="loading" @click="loadData">
          Recargar
        </v-btn>
      </v-col>
    </v-row>

    <v-alert v-if="!token" type="info" variant="tonal" class="mb-4">
      Esta pantalla requiere sesión iniciada como paciente.
    </v-alert>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4">
      {{ errorMessage }}
    </v-alert>

    <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-4">
      {{ successMessage }}
    </v-alert>

    <v-row v-if="!loading && appointments.length === 0">
      <v-col cols="12">
        <v-card>
          <v-card-text>
            No existen citas registradas para el paciente actual.
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col
        v-for="appointment in appointments"
        :key="appointment.id"
        cols="12"
      >
        <v-card>
          <v-card-item>
            <template #title>
              <div class="d-flex flex-wrap ga-3 align-center">
                <span>Cita #{{ appointment.id }}</span>
                <v-chip
                  :color="appointmentStatusColor(appointment.status)"
                  size="small"
                  variant="tonal"
                >
                  {{ appointmentStatusLabel(appointment.status) }}
                </v-chip>

                <v-chip
                  v-if="paymentsByAppointment[appointment.id]"
                  :color="paymentStatusColor(paymentsByAppointment[appointment.id].status)"
                  size="small"
                  variant="tonal"
                >
                  Pago {{ paymentStatusLabel(paymentsByAppointment[appointment.id].status) }}
                </v-chip>
              </div>
            </template>

            <template #subtitle>
              {{ appointment.professional.name }} · {{ appointment.professional.specialty || 'Sin especialidad' }}
            </template>
          </v-card-item>

          <v-card-text>
            <v-row>
              <v-col cols="12" md="4">
                <div><strong>Inicio:</strong> {{ formatDateTime(appointment.scheduled_at) }}</div>
                <div><strong>Fin:</strong> {{ formatDateTime(appointment.ends_at) }}</div>
              </v-col>

              <v-col cols="12" md="4">
                <div><strong>Modalidad:</strong> {{ modalityLabel(appointment.modality) }}</div>
                <div><strong>Valor:</strong> ${{ appointment.price }}</div>
              </v-col>

              <v-col cols="12" md="4">
                <div><strong>Pagada:</strong> {{ appointment.is_paid ? 'Sí' : 'No' }}</div>
                <div><strong>Notas:</strong> {{ appointment.notes || 'Sin notas' }}</div>
              </v-col>
            </v-row>

            <v-divider class="my-4" />

            <div v-if="paymentsByAppointment[appointment.id]">
              <div class="text-subtitle-1 mb-2">Pago asociado</div>
              <div><strong>Referencia:</strong> {{ paymentsByAppointment[appointment.id].external_reference }}</div>
              <div><strong>Estado:</strong> {{ paymentStatusLabel(paymentsByAppointment[appointment.id].status) }}</div>
              <div><strong>Creado:</strong> {{ formatDateTime(paymentsByAppointment[appointment.id].created_at) }}</div>
              <div>
                <strong>Pagado en:</strong>
                {{ paymentsByAppointment[appointment.id].paid_at ? formatDateTime(paymentsByAppointment[appointment.id].paid_at as string) : 'Pendiente' }}
              </div>

              <v-alert
                v-if="shouldShowResolutionBanner(appointment)"
                type="info"
                variant="tonal"
                class="mt-4"
              >
                <div class="font-weight-medium">
                  {{ patientResolutionMessage(appointment) }}
                </div>

                <div
                  v-if="paymentResolutionSummary(appointment)?.refunded_at"
                  class="text-caption mt-1"
                >
                  Reembolso registrado:
                  {{ formatNullableDateTime(paymentResolutionSummary(appointment)?.refunded_at) }}
                </div>
              </v-alert>
            </div>
          </v-card-text>

          <v-divider />

          <v-card-actions class="flex-wrap">
            <v-btn
              v-if="canGeneratePayment(appointment)"
              color="primary"
              variant="flat"
              :loading="acting && actingAppointmentId === appointment.id"
              @click="createPaymentIntent(appointment)"
            >
              {{ paymentButtonText(appointment) }}
            </v-btn>

            <v-btn
              v-if="canCancel(appointment)"
              color="error"
              variant="tonal"
              :loading="acting && actingAppointmentId === appointment.id"
              @click="cancelAppointment(appointment)"
            >
              Cancelar cita
            </v-btn>

            <v-spacer />

            <span
              v-if="showGenericPaidHint(appointment)"
              class="text-caption text-medium-emphasis"
            >
              Si la cita ya fue pagada y aún no aparece una resolución, el siguiente paso depende del flujo administrativo.
            </span>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
    <ConfirmDialog
      v-model="confirmCancelDialog"
      title="¿Cancelar cita?"
      message="¿Estás seguro que deseas cancelar esta cita? Esta acción no se puede deshacer y liberará el horario del profesional."
      confirm-text="Cancelar cita"
      color="error"
      :loading="acting"
      @confirm="confirmCancelAppointment"
    />
  </v-container>
</template>
