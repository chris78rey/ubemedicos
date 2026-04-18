<script setup lang="ts">
const runtimeConfig = useRuntimeConfig()
const token = useCookie<string | null>('access_token')

const apiBase = computed(() => {
  return runtimeConfig.public.apiBaseUrl || 'http://127.0.0.1:8000/api/v1'
})

const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const file = ref<File | null>(null)
const summary = ref<any>(null)

function authHeaders() {
  return token.value ? { Authorization: `Bearer ${token.value}` } : {}
}

async function uploadExcel() {
  if (!file.value) {
    errorMessage.value = 'Por favor, selecciona un archivo Excel.'
    return
  }

  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''
  summary.value = null

  const formData = new FormData()
  formData.append('file', file.value)

  try {
    const response = await $fetch<any>(
      `${apiBase.value}/admin/catalogs/specialties/upload`,
      {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      }
    )

    successMessage.value = response.detail
    summary.value = response.summary
  } catch (error: any) {
    errorMessage.value =
      error?.data?.detail || 'Ocurrió un error al subir el archivo.'
  } finally {
    loading.value = false
  }
}

function reset() {
  file.value = null
  summary.value = null
  errorMessage.value = ''
  successMessage.value = ''
}

async function downloadTemplate() {
  try {
    const response: any = await $fetch(
      `${apiBase.value}/admin/catalogs/specialties/template`,
      {
        headers: authHeaders(),
        responseType: 'blob',
      }
    )
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'plantilla_especialidades.xlsx')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error) {
    errorMessage.value = 'No se pudo descargar la plantilla.'
  }
}
</script>

<template>
  <v-container class="py-6">
    <v-row class="mb-6" align="center" justify="space-between">
      <v-col cols="12" md="8">
        <h1 class="text-h4 font-weight-bold">Carga masiva de especialidades</h1>
        <p class="text-medium-emphasis">
          Sube un archivo Excel para registrar múltiples especialidades médicas de forma simultánea.
        </p>
      </v-col>
      <v-col cols="12" md="4" class="d-flex justify-md-end">
        <v-btn
          prepend-icon="mdi-download"
          variant="outlined"
          @click="downloadTemplate"
        >
          Descargar plantilla
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
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Subir archivo .xlsx</v-card-title>
          <v-card-text>
            <v-file-input
              v-model="file"
              label="Seleccionar archivo Excel"
              accept=".xlsx"
              prepend-icon="mdi-file-excel"
              variant="outlined"
              show-size
              :loading="loading"
              class="mb-4"
            />
            <div class="d-flex ga-2">
              <v-btn
                color="primary"
                :loading="loading"
                :disabled="!file"
                @click="uploadExcel"
              >
                Subir archivo
              </v-btn>
              <v-btn variant="plain" @click="reset">Limpiar</v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6" v-if="summary">
        <v-card variant="outlined">
          <v-card-title>Resumen del proceso</v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <template #prepend><v-icon icon="mdi-sigma" /></template>
                <v-list-item-title>Total filas procesadas:</v-list-item-title>
                <template #append>{{ summary.total_rows }}</template>
              </v-list-item>
              
              <v-list-item v-if="summary.created > 0">
                <template #prepend><v-icon icon="mdi-plus-circle" color="success" /></template>
                <v-list-item-title>Especialidades creadas:</v-list-item-title>
                <template #append>{{ summary.created }}</template>
              </v-list-item>

              <v-list-item v-if="summary.reactivated > 0">
                <template #prepend><v-icon icon="mdi-refresh" color="info" /></template>
                <v-list-item-title>Especialidades reactivadas:</v-list-item-title>
                <template #append>{{ summary.reactivated }}</template>
              </v-list-item>

              <v-list-item v-if="summary.existing > 0">
                <template #prepend><v-icon icon="mdi-check-circle" color="grey" /></template>
                <v-list-item-title>Ya existentes (sin cambios):</v-list-item-title>
                <template #append>{{ summary.existing }}</template>
              </v-list-item>

              <v-list-item v-if="summary.blank_skipped > 0">
                <template #prepend><v-icon icon="mdi-skip-next" color="warning" /></template>
                <v-list-item-title>Filas vacías omitidas:</v-list-item-title>
                <template #append>{{ summary.blank_skipped }}</template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
