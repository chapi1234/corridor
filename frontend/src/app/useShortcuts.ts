import { useEffect } from 'react'

import { useAppStore } from '@/state/store'

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return (
    target.isContentEditable ||
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.tagName === 'SELECT' ||
    target.getAttribute('role') === 'slider'
  )
}

/** Global keyboard shortcuts (listed in the Rules panel). Ignored while typing. */
export function useShortcuts(): void {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) return
      const state = useAppStore.getState()

      if (event.key === '?') {
        state.setRulesOpen(true)
        event.preventDefault()
        return
      }
      if (!state.plan || state.editing || state.rulesOpen) return

      switch (event.key) {
        case 'ArrowLeft':
        case 'ArrowRight': {
          const step = (event.shiftKey ? 6 : 1) * (event.key === 'ArrowLeft' ? -1 : 1)
          state.setPlaying(false)
          state.setForecastHour(state.forecastHour + step)
          break
        }
        case ' ':
          if (event.target instanceof HTMLButtonElement) return
          state.setPlaying(!state.playing)
          break
        case '1':
        case '2':
        case '3': {
          const id = state.plan.recommendation.order.slice().sort()[Number(event.key) - 1]
          if (id) state.selectRoute(id)
          break
        }
        case 'h':
        case 'H':
          state.updateHeatmap({ visible: !state.heatmap.visible })
          break
        case 'Escape':
          if (!state.openCheckpoint) return
          state.openCheckpointDetail(null)
          break
        default:
          return
      }
      event.preventDefault()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])
}
