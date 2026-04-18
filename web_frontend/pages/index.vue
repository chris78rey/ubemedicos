<script setup lang="ts">
type SpecialtyItem = {
  id: number
  name: string
}

type ProfessionalItem = {
  id: number
  name: string
  specialty: string | null
  city: string
  province: string
  office_address: string
  bio: string
  consultation_fee: string
  teleconsultation_fee: string
}

type SlotItem = {
  time: string
  datetime: string
  modality: string
}

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loadingProfessionals = ref(false)
const loadingSlots = ref(false)
const booking = ref(false)

const errorMessage = ref('')
const successMessage = ref('')

const specialties = ref<SpecialtyItem[]>([])
const professionals = ref<ProfessionalItem[]>([])
const availableSlots = ref<SlotItem[]>([])

const filters = reactive({
  city: '',
  specialtyId: null as number | null,
})

const selectedProfessionalId = ref<number | null>(null)
const selectedModality = ref<'in_person' | 'teleconsultation'>('in_person')
const selectedSlotDatetime = ref('')
const notes = ref('')

function nextDayString() {
  const value = new Date()
  value.setDate(value.getDate() + 1)
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const selectedDate = ref(nextDayString())

function authHeaders() {
  return token.value
    ? { Authorization: `Bearer ${token.value}` }
    : {}
}

function modalityLabel(value: string) {
  if (value === 'teleconsultation') return 'Teleconsulta'
  return 'Presencial'
}

const specialtyOptions = computed(() => {
  return specialties.value.map((item) => ({
    title: item.name,
    value: item.id,
  }))
})

const filteredProfessionals = computed(() => {
  return professionals.value.filter((item) => {
    const matchesCity = !filters.city.trim()
      ? true
      : `${item.city} ${item.province}`.toLowerCase().includes(filters.city.trim().toLowerCase())

    const matchesSpecialty = !filters.specialtyId
      ? true
      : specialties.value.find((sp) => sp.id === filters.specialtyId)?.name === item.specialty

    return matchesCity && matchesSpecialty
  })
})

const selectedProfessional = computed(() => {
  return professionals.value.find((item) => item.id === selectedProfessionalId.value) || null
})

async function loadSpecialties() {
  const response = await $fetch<{ items: SpecialtyItem[] }>(
    `${apiBase.value}/catalogs/specialties`
  )
  specialties.value = response.items || []
}

async function loadProfessionals() {
  loadingProfessionals.value = true
  errorMessage.value = ''

  try {
    const response = await $fetch<{ items: ProfessionalItem[] }>(
      `${apiBase.value}/professionals/public`
    )
    professionals.value = response.items || []
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar la lista pública de profesionales.'
  } finally {
    loadingProfessionals.value = false
  }
}

async function loadAvailableSlots() {
  availableSlots.value = []
  selectedSlotDatetime.value = ''

  if (!selectedProfessionalId.value || !selectedDate.value) {
    return
  }

  loadingSlots.value = true
  errorMessage.value = ''

  try {
    const query = new URLSearchParams({
      date: selectedDate.value,
      modality: selectedModality.value,
    })

    const response = await $fetch<{ items: SlotItem[] }>(
      `${apiBase.value}/professionals/public/${selectedProfessionalId.value}/available-slots?${query.toString()}`
    )

    availableSlots.value = response.items || []
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudieron cargar los horarios disponibles.'
  } finally {
    loadingSlots.value = false
  }
}

async function selectProfessional(item: ProfessionalItem) {
  selectedProfessionalId.value = item.id
  successMessage.value = ''
  errorMessage.value = ''
  await loadAvailableSlots()
}

async function bookAppointment() {
  if (!token.value) {
    errorMessage.value = 'Se requiere sesión iniciada como paciente para reservar.'
    return
  }

  if (!selectedProfessionalId.value) {
    errorMessage.value = 'Debe seleccionarse un profesional.'
    return
  }

  if (!selectedSlotDatetime.value) {
    errorMessage.value = 'Debe seleccionarse un horario.'
    return
  }

  booking.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(`${apiBase.value}/patient/appointments`, {
      method: 'POST',
      headers: {
        ...authHeaders(),
        'Content-Type': 'application/json',
      },
      body: {
        professional_id: selectedProfessionalId.value,
        scheduled_at: selectedSlotDatetime.value,
        modality: selectedModality.value,
        notes: notes.value,
      },
    })

    successMessage.value = 'Cita reservada correctamente.'
    notes.value = ''
    selectedSlotDatetime.value = ''
    await loadAvailableSlots()
    await navigateTo('/patient/appointments')
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo reservar la cita.'
  } finally {
    booking.value = false
  }
}

watch(selectedDate, async () => {
  if (selectedProfessionalId.value) {
    await loadAvailableSlots()
  }
})

watch(selectedModality, async () => {
  if (selectedProfessionalId.value) {
    await loadAvailableSlots()
  }
})

onMounted(async () => {
  await Promise.all([
    loadSpecialties(),
    loadProfessionals(),
  ])
})
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-4" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Buscar profesional</h1>
        <p class="text-medium-emphasis">
          Pantalla pública para consultar profesionales aprobados y reservar una cita.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2">
        <v-btn variant="outlined" @click="loadProfessionals" :loading="loadingProfessionals">
          Recargar
        </v-btn>
        <v-btn color="primary" variant="flat" @click="navigateTo('/patient/appointments')">
          Mis citas
        </v-btn>
      </v-col>
    </v-row>

    <v-alert v-if="!token" type="info" variant="tonal" class="mb-4">
      La navegación pública está habilitada. Para reservar, debe existir sesión iniciada como paciente.
    </v-alert>

    <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4">
      {{ errorMessage }}
    </v-alert>

    <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-4">
      {{ successMessage }}
    </v-alert>

    <v-row class="mb-4">
      <v-col cols="12" md="4">
        <v-text-field
          v-model="filters.city"
          label="Filtrar por ciudad o provincia"
          variant="outlined"
          density="comfortable"
          clearable
        />
      </v-col>

      <v-col cols="12" md="4">
        <v-select
          v-model="filters.specialtyId"
          :items="specialtyOptions"
          label="Especialidad"
          variant="outlined"
          density="comfortable"
          clearable
        />
      </v-col>

      <v-col cols="12" md="4">
        <v-select
          v-model="selectedModality"
          :items="[
            { title: 'Presencial', value: 'in_person' },
            { title: 'Teleconsulta', value: 'teleconsultation' },
          ]"
          label="Modalidad"
          variant="outlined"
          density="comfortable"
        />
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" lg="7">
        <v-card>
          <v-card-title>Profesionales disponibles</v-card-title>
          <v-card-text>
            <v-row v-if="filteredProfessionals.length > 0">
              <v-col
                v-for="item in filteredProfessionals"
                :key="item.id"
                cols="12"
              >
                <v-card variant="outlined">
                  <v-card-text>
                    <div class="d-flex flex-wrap justify-space-between ga-3 mb-3">
                      <div>
                        <div class="text-h6">{{ item.name }}</div>
                        <div class="text-body-2 text-medium-emphasis">
                          {{ item.specialty || 'Sin especialidad' }}
                        </div>
                      </div>

                      <div class="text-right">
                        <div class="text-body-2">
                          <strong>Presencial:</strong> ${{ item.consultation_fee }}
                        </div>
                        <div class="text-body-2">
                          <strong>Teleconsulta:</strong> ${{ item.teleconsultation_fee }}
                        </div>
                      </div>
                    </div>

                    <div class="mb-2">
                      <strong>Ubicación:</strong> {{ item.city || 'Sin ciudad' }}{{ item.province ? `, ${item.province}` : '' }}
                    </div>

                    <v-alert
                      v-if="selectedModality === 'in_person' && item.office_address"
                      icon="mdi-map-marker"
                      variant="tonal"
                      density="compact"
                      class="mb-3"
                    >
                      <strong>Dirección:</strong> {{ item.office_address }}
                    </v-alert>

                    <div class="text-body-2 text-medium-emphasis mb-4">
                      {{ item.bio || 'Sin biografía pública.' }}
                    </div>

                    <div class="d-flex flex-wrap ga-2">
                      <v-btn color="primary" variant="flat" @click="selectProfessional(item)">
                        Seleccionar
                      </v-btn>
                      <v-chip v-if="selectedProfessionalId === item.id" color="primary" variant="tonal">
                        Seleccionado
                      </v-chip>
                    </div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <div v-else class="text-medium-emphasis py-4">
              No existen profesionales que coincidan con los filtros aplicados.
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card height="100%">
          <v-card-title>Reserva</v-card-title>
          <v-card-text>
            <div v-if="selectedProfessional">
              <div class="text-h6 mb-1">{{ selectedProfessional.name }}</div>
              <div class="text-body-2 text-medium-emphasis mb-4">
                {{ selectedProfessional.specialty || 'Sin especialidad' }}
              </div>

              <v-text-field
                v-model="selectedDate"
                type="date"
                label="Fecha"
                variant="outlined"
                density="comfortable"
                class="mb-3"
              />

              <div class="text-subtitle-1 mb-2">
                Horarios disponibles ({{ modalityLabel(selectedModality) }})
              </div>

              <v-progress-linear
                v-if="loadingSlots"
                indeterminate
                class="mb-4"
              />

              <div v-if="!loadingSlots && availableSlots.length > 0" class="d-flex flex-wrap ga-2 mb-4">
                <v-btn
                  v-for="slot in availableSlots"
                  :key="slot.datetime"
                  :color="selectedSlotDatetime === slot.datetime ? 'primary' : undefined"
                  :variant="selectedSlotDatetime === slot.datetime ? 'flat' : 'outlined'"
                  @click="selectedSlotDatetime = slot.datetime"
                >
                  {{ slot.time.slice(0, 5) }}
                </v-btn>
              </div>

              <div v-else-if="!loadingSlots" class="text-medium-emphasis mb-4">
                No existen horarios disponibles para la fecha seleccionada.
              </div>

              <v-textarea
                v-model="notes"
                label="Notas para la cita"
                variant="outlined"
                density="comfortable"
                rows="3"
                class="mb-4"
              />

              <v-btn
                color="primary"
                block
                :loading="booking"
                :disabled="!selectedSlotDatetime"
                @click="bookAppointment"
              >
                Reservar cita
              </v-btn>
            </div>

            <div v-else class="text-medium-emphasis">
              Debe seleccionarse un profesional para consultar horarios y reservar.
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
