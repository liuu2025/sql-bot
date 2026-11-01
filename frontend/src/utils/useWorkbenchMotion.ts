import { onMounted, onUnmounted, type Ref } from 'vue'
import { attachSpotlight } from './spotlight'

export function useWorkbenchMotion(root: Ref<HTMLElement | null>) {
  let cleanup: (() => void) | undefined
  onMounted(() => {
    if (root.value) cleanup = attachSpotlight(root.value)
  })
  onUnmounted(() => cleanup?.())
}
