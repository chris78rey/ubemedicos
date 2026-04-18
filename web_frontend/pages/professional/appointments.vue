<script setup lang="ts">
type AppointmentResolutionSummary = {
  kind: string
  message: string
  cancelled_as: string | null
  appointment_status_after: string | null
  refunded_at: string | null
}

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
  resolution_summary: AppointmentResolutionSummary | null
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

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    pending_confirmation: 'Pendiente de confirmación',
    confirmed: 'Confirmed',
    cancelled_by_patient: 'Cancelada por paciente',
    cancelled_by_professional: 'Cancelada por profesional',
    completed: 'Completada',
    no_show_patient: 'No asistió paciente',
    no_show_professional: 'No asistió profesional',
  }
  return labels[value] || value
}

function statusColor(value: string) {
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

function isPast(appointment: AppointmentItem) {
  return new Date(appointment.scheduled_at).getTime() <= Date.now()
}

function canConfirm(appointment: AppointmentItem) {
  return appointment.status === 'pending_confirmation'
}

function canCancel(appointment: AppointmentItem) {
  return (
    ['pending_confirmation', 'confirmed'].includes(appointment.status) &&
    !appointment.is_paid
  )
}

function canComplete(appointment: AppointmentItem) {
  return appointment.status === 'confirmed' && isPast(appointment)
}

function canMarkNoShow(appointment: AppointmentItem) {
  return appointment.status === 'confirmed' && isPast(appointment)
}

function shouldShowResolutionBanner(appointment: AppointmentItem) {
  return Boolean(appointment.resolution_summary)
}

function showGenericPaidHint(appointment: AppointmentItem) {
  return (
    appointment.is_paid &&
    ['pending_confirmation', 'confirmed'].includes(appointment.status) &&
    !appointment.resolution_summary
  )
}

async function loadAppointments() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const response = await $fetch<{ items: AppointmentItem[] }>(
      `${apiBase.value}/professional/appointments`,
      {
        headers: authHeaders(),
      }
    )
    appointments.value = response.items || []
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar la lista de citas.'
  } finally {
    loading.value = false
  }
}

async function runAction(
  appointmentId: number,
  path: string,
  payload: Record<string, any>,
  successText: string
) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  acting.value = true
  actingAppointmentId.value = appointmentId
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(`${apiBase.value}${path}`, {
      method: 'POST',
      headers: {
        ...authHeaders(),
        'Content-Type': 'application/json',
      },
      body: payload,
    })

    successMessage.value = successText
    await loadAppointments()
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo completar la acción.'
  } finally {
    acting.value = false
    actingAppointmentId.value = null
  }
}

async function confirmAppointment(appointment: AppointmentItem) {
  await runAction(
    appointment.id,
    `/professional/appointments/${appointment.id}/confirm`,
    { notes: 'Confirmada desde panel profesional' },
    'Cita confirmada correctamente.'
  )
}

async function cancelAppointment(appointment: AppointmentItem) {
  targetAppointment.value = appointment
  confirmCancelDialog.value = true
}

async function confirmCancelAppointment() {
  if (!token.value || !targetAppointment.value) return

  await runAction(
    targetAppointment.value.id,
    `/professional/appointments/${targetAppointment.value.id}/cancel`,
    { reason: 'Cancelada desde panel profesional' },
    'Cita cancelada correctamente.'
  )

  confirmCancelDialog.value = false
  targetAppointment.value = null
}

async function completeAppointment(appointment: AppointmentItem) {
  await runAction(
    appointment.id,
    `/professional/appointments/${appointment.id}/complete`,
    { notes: 'Consulta finalizada desde panel profesional' },
    'Cita completada correctamente.'
  )
}

async function markNoShow(appointment: AppointmentItem) {
  await runAction(
    appointment.id,
    `/professional/appointments/${appointment.id}/mark-no-show-patient`,
    { reason: 'Paciente no asistió' },
    'Se marcó la no asistencia del paciente.'
  )
}

onMounted(async () => {
  await loadAppointments()
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Citas del profesional</h1>
        <p class="text-medium-emphasis">
          Desde esta pantalla se confirma, cancela, completa y marca la no asistencia.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2">
        <v-btn variant="outlined" @click="navigateTo('/professional')">
          Panel
        </v-btn>
        <v-btn color="primary" :loading="loading" @click="loadAppointments">
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

    <v-row v-if="!loading && appointments.length === 0">
      <v-col cols="12">
        <v-card>
          <v-card-text>No existen citas para mostrar.</v-card-text>
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
                <v-chip :color="statusColor(appointment.status)" size="small">
                  {{ statusLabel(appointment.status) }}
                </v-chip>
              </div>
            </template>

            <template #subtitle>
              {{ appointment.patient.name }} · {{ modalityLabel(appointment.modality) }}
            </template>
          </v-card-item>

          <v-card-text>
            <v-row>
              <v-col cols="12" md="4">
                <div><strong>Inicio:</strong> {{ formatDateTime(appointment.scheduled_at) }}</div>
                <div><strong>Fin:</strong> {{ formatDateTime(appointment.ends_at) }}</div>
              </v-col>

              <v-col cols="12" md="4">
                <div><strong>Precio:</strong> ${{ appointment.price }}</div>
                <div>
                  <strong>Pago:</strong>
                  {{ appointment.is_paid ? 'Pagada' : 'Pendiente' }}
                </div>
              </v-col>

              <v-col cols="12" md="4">
                <div><strong>Especialidad:</strong> {{ appointment.professional.specialty || 'Sin especialidad' }}</div>
                <div><strong>Notas:</strong> {{ appointment.notes || 'Sin notas' }}</div>
              </v-col>
            </v-row>

            <v-alert
              v-if="shouldShowResolutionBanner(appointment)"
              type="info"
              variant="tonal"
              class="mt-4"
            >
              <div class="font-weight-medium">
                {{ appointment.resolution_summary?.message }}
              </div>

              <div
                v-if="appointment.resolution_summary?.refunded_at"
                class="text-caption mt-1"
              >
                Reembolso registrado:
                {{ formatNullableDateTime(appointment.resolution_summary?.refunded_at) }}
              </div>
            </v-alert>
          </v-card-text>

          <v-divider />

          <v-card-actions class="flex-wrap">
            <v-btn
              v-if="canConfirm(appointment)"
              color="primary"
              variant="flat"
              :loading="acting && actingAppointmentId === appointment.id"
              @click="confirmAppointment(appointment)"
            >
              Confirmar
            </v-btn>

            <v-btn
              v-if="canCancel(appointment)"
              color="error"
              variant="tonal"
              :loading="acting && actingAppointmentId === appointment.id"
              @click="cancelAppointment(appointment)"
            >
              Cancelar
            </v-btn>

            <v-btn
              v-if="canComplete(appointment)"
              color="success"
              variant="flat"
              :loading="acting && actingAppointmentId === appointment.id"
              @click="completeAppointment(appointment)"
            >
              Completar
            </v-btn>

            <v-btn
              v-if="canMarkNoShow(appointment)"
              color="warning"
              variant="tonal"
              :loading="acting && actingAppointmentId === appointment.id"
              @click="markNoShow(appointment)"
            >
              Marcar no asistencia
            </v-btn>

            <v-spacer />

            <span
              v-if="showGenericPaidHint(appointment)"
              class="text-caption text-medium-emphasis"
            >
              La cancelación de una cita pagada queda bloqueada hasta que exista una resolución administrativa.
            </span>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
    <ConfirmDialog
      v-model="confirmCancelDialog"
      title="¿Cancelar cita?"
      message="¿Estás seguro que deseas cancelar esta cita? Esta acción no se puede deshacer y liberará el horario de tu disponibilidad."
      confirm-text="Cancelar cita"
      color="error"
      :loading="acting"
      @confirm="confirmCancelAppointment"
    />
  </v-container>
</template>
