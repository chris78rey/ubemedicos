<script setup lang="ts">
const props = defineProps<{
  modelValue: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  color?: string
  loading?: boolean
}>()

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

function handleCancel() {
  emit('cancel')
  emit('update:modelValue', false)
}

function handleConfirm() {
  emit('confirm')
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="450" persistent>
    <v-card>
      <v-card-title class="text-h6 pt-4 px-4 pb-0">
        {{ title || '¿Estás seguro?' }}
      </v-card-title>

      <v-card-text class="pt-2 px-4 pb-4">
        {{ message || 'Esta acción no se puede deshacer.' }}
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn
          variant="text"
          :disabled="loading"
          @click="handleCancel"
        >
          {{ cancelText || 'Cancelar' }}
        </v-btn>
        <v-btn
          :color="color || 'primary'"
          variant="flat"
          :loading="loading"
          @click="handleConfirm"
        >
          {{ confirmText || 'Confirmar' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
