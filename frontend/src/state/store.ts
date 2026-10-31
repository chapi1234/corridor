import { create } from 'zustand'

import type { IntervalMi, Place, PlanResponse } from '@/api/types'
import type { HeatmapVariable } from '@/domain/heatmap'
import { nextFullHour } from '@/lib/localTime'

export interface TripDraft {
  origin: Place | null
  destination: Place | null
  /** Wall-clock time at the origin, "YYYY-MM-DDTHH:MM" (D14). */
  departureLocal: string
  loadLb: number
  intervalMi: IntervalMi
}

export interface CheckpointRef {
  routeId: string
  index: number
}

export type HoverTarget =
  { kind: 'route'; routeId: string } | ({ kind: 'checkpoint' } & CheckpointRef)

export type Theme = 'night' | 'day'

export const FORECAST_HOURS = 48

interface State {
  draft: TripDraft
  plan: PlanResponse | null
  editing: boolean
  /** What-if load: re-scores the current plan client-side without a request. */
  loadOverrideLb: number | null
  selectedRouteId: string | null
  hover: HoverTarget | null
  openCheckpoint: CheckpointRef | null
  /** Forecast hour relative to the departure hour, 0..48 (D15). */
  forecastHour: number
  playing: boolean
  heatmap: { visible: boolean; variable: HeatmapVariable; opacity: number }
  rulesOpen: boolean
  theme: Theme
}

interface Actions {
  updateDraft(patch: Partial<TripDraft>): void
  swapEndpoints(): void
  showPlan(plan: PlanResponse): void
  editTrip(): void
  setLoadOverride(loadLb: number | null): void
  selectRoute(routeId: string): void
  setHover(target: HoverTarget | null): void
  openCheckpointDetail(ref: CheckpointRef | null): void
  stepCheckpoint(delta: 1 | -1): void
  setForecastHour(hour: number): void
  setPlaying(playing: boolean): void
  updateHeatmap(patch: Partial<State['heatmap']>): void
  setRulesOpen(open: boolean): void
  setTheme(theme: Theme): void
}

/**
 * Applied synchronously (not in an effect) so components reading CSS variables — the map
 * and canvas layers — always see the active theme's colours.
 */
function applyTheme(theme: Theme): Theme {
  document.documentElement.dataset.theme = theme
  return theme
}

function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem('corridor.theme')
    if (stored === 'night' || stored === 'day') return stored
  } catch {
    /* storage unavailable: fall through to system preference */
  }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'day' : 'night'
}

export const useAppStore = create<State & Actions>()((set, get) => ({
  draft: {
    origin: null,
    destination: null,
    departureLocal: nextFullHour(),
    loadLb: 42_000,
    intervalMi: 25,
  },
  plan: null,
  editing: true,
  loadOverrideLb: null,
  selectedRouteId: null,
  hover: null,
  openCheckpoint: null,
  forecastHour: 0,
  playing: false,
  heatmap: { visible: true, variable: 'risk', opacity: 0.7 },
  rulesOpen: false,
  theme: applyTheme(initialTheme()),

  updateDraft: (patch) => set((s) => ({ draft: { ...s.draft, ...patch } })),
  swapEndpoints: () =>
    set((s) => ({
      draft: { ...s.draft, origin: s.draft.destination, destination: s.draft.origin },
    })),

  showPlan: (plan) =>
    set({
      plan,
      editing: false,
      loadOverrideLb: null,
      selectedRouteId: plan.recommendation.route_id,
      hover: null,
      openCheckpoint: null,
      forecastHour: 0,
      playing: false,
    }),
  editTrip: () => set({ editing: true, playing: false }),
  setLoadOverride: (loadOverrideLb) => set({ loadOverrideLb }),
  selectRoute: (selectedRouteId) =>
    set((s) => ({
      selectedRouteId,
      openCheckpoint: s.openCheckpoint?.routeId === selectedRouteId ? s.openCheckpoint : null,
    })),
  setHover: (hover) => {
    const current = get().hover
    if (JSON.stringify(current) !== JSON.stringify(hover)) set({ hover })
  },
  openCheckpointDetail: (openCheckpoint) =>
    set(
      openCheckpoint
        ? { openCheckpoint, selectedRouteId: openCheckpoint.routeId }
        : { openCheckpoint },
    ),
  stepCheckpoint: (delta) => {
    const { openCheckpoint, plan } = get()
    if (!openCheckpoint || !plan) return
    const route = plan.routes.find((r) => r.id === openCheckpoint.routeId)
    if (!route) return
    const index = Math.min(Math.max(openCheckpoint.index + delta, 0), route.checkpoints.length - 1)
    set({ openCheckpoint: { ...openCheckpoint, index } })
  },
  setForecastHour: (hour) =>
    set({ forecastHour: Math.min(Math.max(Math.round(hour), 0), FORECAST_HOURS) }),
  setPlaying: (playing) => set({ playing }),
  updateHeatmap: (patch) => set((s) => ({ heatmap: { ...s.heatmap, ...patch } })),
  setRulesOpen: (rulesOpen) => set({ rulesOpen }),
  setTheme: (theme) => {
    try {
      localStorage.setItem('corridor.theme', theme)
    } catch {
      /* non-essential preference */
    }
    set({ theme: applyTheme(theme) })
  },
}))
