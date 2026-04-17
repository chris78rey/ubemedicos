<script setup lang="ts">
type SlotItem = {
  id: number
  weekday: number
  start_time: string
  end_time: string
  modality: string
  is_active: boolean
}

type BlockItem = {
  id: number
  start_at: string
  end_at: string
  reason: string
  created_at: string | null
}

const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loading = ref(false)
const savingSlot = ref(false)
const savingBlock = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const slots = ref<SlotItem[]>([])
const blocks = ref<BlockItem[]>([])

const weekdays = [
  { title: 'Lunes', value: 0 },
  { title: 'Martes', value: 1 },
  { title: 'Miércoles', value: 2 },
  { title: 'Jueves', value: 3 },
  { title: 'Viernes', value: 4 },
  { title: 'Sábado', value: 5 },
  { title: 'Domingo', value: 6 },
]

const modalities = [
  { title: 'Presencial', value: 'in_person' },
  { title: 'Teleconsulta', value: 'teleconsultation' },
]

const slotForm = reactive({
  id: null as number | null,
  weekday: 0,
  start_time: '08:00',
  end_time: '12:00',
  modality: 'in_person',
  is_active: true,
})

const blockForm = reactive({
  id: null as number | null,
  start_at: '',
  end_at: '',
  reason: '',
})

function authHeaders() {
  return token.value
    ? { Authorization: `Bearer ${token.value}` }
    : {}
}

function weekdayLabel(value: number) {
  return weekdays.find((item) => item.value === value)?.title || String(value)
}

function modalityLabel(value: string) {
  return value === 'teleconsultation' ? 'Teleconsulta' : 'Presencial'
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString()
}

function toInputDateTime(value: string) {
  const date = new Date(value)
  const pad = (n: number) => String(n).padStart(2, '0')

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function resetSlotForm() {
  slotForm.id = null
  slotForm.weekday = 0
  slotForm.start_time = '08:00'
  slotForm.end_time = '12:00'
  slotForm.modality = 'in_person'
  slotForm.is_active = true
}

function resetBlockForm() {
  blockForm.id = null
  blockForm.start_at = ''
  blockForm.end_at = ''
  blockForm.reason = ''
}

async function loadData() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const [slotResponse, blockResponse] = await Promise.all([
      $fetch<{ items: SlotItem[] }>(`${apiBase.value}/professional/availability`, {
        headers: authHeaders(),
      }),
      $fetch<{ items: BlockItem[] }>(`${apiBase.value}/professional/availability/blocks`, {
        headers: authHeaders(),
      }),
    ])

    slots.value = slotResponse.items || []
    blocks.value = blockResponse.items || []
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo cargar la disponibilidad.'
  } finally {
    loading.value = false
  }
}

function editSlot(slot: SlotItem) {
  slotForm.id = slot.id
  slotForm.weekday = slot.weekday
  slotForm.start_time = slot.start_time.slice(0, 5)
  slotForm.end_time = slot.end_time.slice(0, 5)
  slotForm.modality = slot.modality
  slotForm.is_active = slot.is_active
}

function editBlock(block: BlockItem) {
  blockForm.id = block.id
  blockForm.start_at = toInputDateTime(block.start_at)
  blockForm.end_at = toInputDateTime(block.end_at)
  blockForm.reason = block.reason || ''
}

async function submitSlot() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  savingSlot.value = true
  errorMessage.value = ''
  successMessage.value = ''

  const payload = {
    weekday: slotForm.weekday,
    start_time: slotForm.start_time,
    end_time: slotForm.end_time,
    modality: slotForm.modality,
    is_active: slotForm.is_active,
  }

  try {
    if (slotForm.id) {
      await $fetch(`${apiBase.value}/professional/availability/${slotForm.id}`, {
        method: 'PATCH',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: payload,
      })
      successMessage.value = 'Horario actualizado correctamente.'
    } else {
      await $fetch(`${apiBase.value}/professional/availability`, {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: payload,
      })
      successMessage.value = 'Horario creado correctamente.'
    }

    resetSlotForm()
    await loadData()
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo guardar el horario.'
  } finally {
    savingSlot.value = false
  }
}

async function deactivateSlot(slotId: number) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(`${apiBase.value}/professional/availability/${slotId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    successMessage.value = 'Horario desactivado correctamente.'
    await loadData()
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo desactivar el horario.'
  }
}

async function submitBlock() {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  savingBlock.value = true
  errorMessage.value = ''
  successMessage.value = ''

  const payload = {
    start_at: blockForm.start_at,
    end_at: blockForm.end_at,
    reason: blockForm.reason,
  }

  try {
    if (blockForm.id) {
      await $fetch(`${apiBase.value}/professional/availability/blocks/${blockForm.id}`, {
        method: 'PATCH',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: payload,
      })
      successMessage.value = 'Bloqueo actualizado correctamente.'
    } else {
      await $fetch(`${apiBase.value}/professional/availability/blocks`, {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: payload,
      })
      successMessage.value = 'Bloqueo creado correctamente.'
    }

    resetBlockForm()
    await loadData()
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo guardar el bloqueo.'
  } finally {
    savingBlock.value = false
  }
}

async function deleteBlock(blockId: number) {
  if (!token.value) {
    errorMessage.value = 'No existe token de autenticación.'
    return
  }

  errorMessage.value = ''
  successMessage.value = ''

  try {
    await $fetch(`${apiBase.value}/professional/availability/blocks/${blockId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    successMessage.value = 'Bloqueo eliminado correctamente.'
    await loadData()
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'No se pudo eliminar el bloqueo.'
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
        <h1 class="text-h4 font-weight-bold">Disponibilidad del profesional</h1>
        <p class="text-medium-emphasis">
          Desde esta pantalla se administran horarios semanales y bloqueos puntuales.
        </p>
      </v-col>

      <v-col cols="12" md="4" class="d-flex justify-md-end ga-2">
        <v-btn variant="outlined" @click="navigateTo('/professional')">
          Panel
        </v-btn>
        <v-btn color="primary" :loading="loading" @click="loadData">
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
      <v-col cols="12" lg="5">
        <v-card class="mb-6">
          <v-card-title>{{ slotForm.id ? 'Editar horario' : 'Nuevo horario semanal' }}</v-card-title>
          <v-card-text>
            <v-select
              v-model="slotForm.weekday"
              :items="weekdays"
              item-title="title"
              item-value="value"
              label="Día"
              class="mb-3"
            />

            <v-text-field
              v-model="slotForm.start_time"
              label="Hora inicio"
              type="time"
              class="mb-3"
            />

            <v-text-field
              v-model="slotForm.end_time"
              label="Hora fin"
              type="time"
              class="mb-3"
            />

            <v-select
              v-model="slotForm.modality"
              :items="modalities"
              item-title="title"
              item-value="value"
              label="Modalidad"
              class="mb-3"
            />

            <v-switch
              v-model="slotForm.is_active"
              label="Horario activo"
              inset
            />
          </v-card-text>

          <v-card-actions>
            <v-btn color="primary" :loading="savingSlot" @click="submitSlot">
              {{ slotForm.id ? 'Actualizar horario' : 'Crear horario' }}
            </v-btn>
            <v-btn variant="text" @click="resetSlotForm">
              Limpiar
            </v-btn>
          </v-card-actions>
        </v-card>

        <v-card>
          <v-card-title>{{ blockForm.id ? 'Editar bloqueo' : 'Nuevo bloqueo puntual' }}</v-card-title>
          <v-card-text>
            <v-text-field
              v-model="blockForm.start_at"
              label="Inicio"
              type="datetime-local"
              class="mb-3"
            />

            <v-text-field
              v-model="blockForm.end_at"
              label="Fin"
              type="datetime-local"
              class="mb-3"
            />

            <v-textarea
              v-model="blockForm.reason"
              label="Motivo"
              rows="3"
            />
          </v-card-text>

          <v-card-actions>
            <v-btn color="primary" :loading="savingBlock" @click="submitBlock">
              {{ blockForm.id ? 'Actualizar bloqueo' : 'Crear bloqueo' }}
            </v-btn>
            <v-btn variant="text" @click="resetBlockForm">
              Limpiar
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <v-col cols="12" lg="7">
        <v-card class="mb-6">
          <v-card-title>Horarios semanales</v-card-title>
          <v-card-text>
            <v-table>
              <thead>
                <tr>
                  <th>Día</th>
                  <th>Inicio</th>
                  <th>Fin</th>
                  <th>Modalidad</th>
                  <th>Activo</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="slot in slots" :key="slot.id">
                  <td>{{ weekdayLabel(slot.weekday) }}</td>
                  <td>{{ slot.start_time }}</td>
                  <td>{{ slot.end_time }}</td>
                  <td>{{ modalityLabel(slot.modality) }}</td>
                  <td>{{ slot.is_active ? 'Sí' : 'No' }}</td>
                  <td class="d-flex ga-2">
                    <v-btn size="small" variant="tonal" @click="editSlot(slot)">
                      Editar
                    </v-btn>
                    <v-btn
                      size="small"
                      color="error"
                      variant="tonal"
                      @click="deactivateSlot(slot.id)"
                    >
                      Desactivar
                    </v-btn>
                  </td>
                </tr>

                <tr v-if="slots.length === 0">
                  <td colspan="6">No existen horarios registrados.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>

        <v-card>
          <v-card-title>Bloqueos puntuales</v-card-title>
          <v-card-text>
            <v-table>
              <thead>
                <tr>
                  <th>Inicio</th>
                  <th>Fin</th>
                  <th>Motivo</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="block in blocks" :key="block.id">
                  <td>{{ formatDateTime(block.start_at) }}</td>
                  <td>{{ formatDateTime(block.end_at) }}</td>
                  <td>{{ block.reason || 'Sin motivo' }}</td>
                  <td class="d-flex ga-2">
                    <v-btn size="small" variant="tonal" @click="editBlock(block)">
                      Editar
                    </v-btn>
                    <v-btn
                      size="small"
                      color="error"
                      variant="tonal"
                      @click="deleteBlock(block.id)"
                    >
                      Eliminar
                    </v-btn>
                  </td>
                </tr>

                <tr v-if="blocks.length === 0">
                  <td colspan="4">No existen bloqueos registrados.</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
