<template>
  <div class="row wrap">
    <input
      v-model="model"
      class="input"
      style="flex:1;min-width:260px"
      placeholder="Enter token mint address (e.g. So11111111111111111111111111111111111111112)"
      @keyup.enter="submit"
    />
    <button class="btn" :disabled="!model || loading" @click="submit">
      {{ loading ? 'Loading...' : 'Search' }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const props = defineProps({
  modelValue: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'search'])
const model = ref(props.modelValue)
function submit() {
  emit('update:modelValue', model.value.trim())
  emit('search', model.value.trim())
}
</script>