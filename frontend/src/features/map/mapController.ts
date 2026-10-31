/**
 * Imperative owner of the MapLibre map. React hands it data; it never rebuilds layers on
 * re-render. Per-frame interactions (forecast hour, hover) change paint properties or
 * feature-state only — no source uploads, no React work.
 */

import maplibregl, {
  type ExpressionSpecification,
  type GeoJSONSource,
  type LngLatBoundsLike,
  type Map as MapLibreMap,
  type MapMouseEvent,
} from 'maplibre-gl'

import {
  HEATMAP_FLOOR,
  KERNEL_SPACING_RATIO,
  UNIFORM_FIELD_DENSITY,
  VARIABLE_SCALES,
  type Frames,
  type HeatmapVariable,
} from '@/domain/heatmap'
import { cssColor } from '@/domain/levels'
import { RouteTrack, riskGradientStops } from '@/domain/routeGeometry'
import type { ScoredPlan } from '@/domain/scoring'
import type { CheckpointRef, HoverTarget, Theme } from '@/state/store'

import { BASEMAP_STYLES, firstSymbolLayerId, tintBasemap } from './basemap'
import { endpointIcon, shieldIcon, truckIcon } from './mapImages'

const SRC = {
  heat: 'c-heat',
  routes: 'c-routes',
  selected: 'c-route-selected',
  checkpoints: 'c-checkpoints',
  ghost: 'c-ghost',
  endpoints: 'c-endpoints',
} as const

const LYR = {
  heat: 'c-heat',
  casing: 'c-route-casing',
  muted: 'c-route-muted',
  selectedCasing: 'c-route-selected-casing',
  selected: 'c-route-selected',
  checkpoints: 'c-checkpoints',
  shields: 'c-route-shields',
  endpoints: 'c-endpoints',
  ghost: 'c-ghost',
} as const

const INTERACTIVE_LAYERS = [LYR.checkpoints, LYR.selected, LYR.muted]
const CHECKPOINT_ID_STRIDE = 10_000
const HEATMAP_MAX_ZOOM = 10
const METERS_PER_PIXEL_Z0 = 78_271.517 // 512 px tiles at the equator
const HIT_TOLERANCE_PX = 6
const UNKNOWN_LEVEL = -1

export interface PlanView {
  scored: ScoredPlan
  selectedRouteId: string | null
}

export interface HeatmapView {
  frames: Frames
  points: number[][]
  spacingM: number
  variable: HeatmapVariable
  visible: boolean
  opacity: number
}

export interface MapCallbacks {
  onHover(target: HoverTarget | null, screen: { x: number; y: number } | null): void
  onSelectRoute(routeId: string): void
  onOpenCheckpoint(ref: CheckpointRef): void
}

/**
 * How the truck travels to a new forecast hour. Playback uses linear motion lasting exactly
 * one tick, so consecutive hours chain into one continuous drive; manual scrubbing eases out.
 */
export interface HourTransition {
  durationMs: number
  easing: 'linear' | 'ease-out'
}

interface GhostTween {
  fromS: number
  toS: number
  startMs: number
  durationMs: number
  easing: HourTransition['easing']
}

type FeatureCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, GeoJSON.GeoJsonProperties>

const HOUR_S = 3600
const easeOutCubic = (t: number) => 1 - (1 - t) ** 3
const emptyCollection = (): FeatureCollection => ({ type: 'FeatureCollection', features: [] })

export class MapController {
  private readonly map: MapLibreMap
  private readonly callbacks: MapCallbacks
  private theme: Theme
  private styleReady = false
  private plan: PlanView | null = null
  private heat: HeatmapView | null = null
  private hour = 0
  private hover: HoverTarget | null = null
  private active: CheckpointRef | null = null
  private tracks = new Map<string, RouteTrack>()
  private fittedPlanId: string | null = null
  private pendingPointer: MapMouseEvent | null = null
  private pointerFrame = 0
  /** Elapsed driving time (s) the truck marker is drawn at; tweened between hours. */
  private ghostElapsedS: number | null = null
  private ghostTween: GhostTween | null = null
  private ghostFrame = 0
  private readonly reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')

  constructor(container: HTMLElement, theme: Theme, callbacks: MapCallbacks) {
    this.theme = theme
    this.callbacks = callbacks
    this.map = new maplibregl.Map({
      container,
      style: BASEMAP_STYLES[theme],
      center: [-97, 39],
      zoom: 3.6,
      minZoom: 2.5,
      maxZoom: 15,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      fadeDuration: 0,
    })
    this.map.touchZoomRotate.disableRotation()
    this.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    this.map.addControl(
      new maplibregl.ScaleControl({ unit: 'imperial', maxWidth: 110 }),
      'bottom-right',
    )

    this.map.on('style.load', () => this.installStyle())
    this.map.on('mousemove', (event) => this.queuePointer(event))
    this.map.on('mouseout', () => this.callbacks.onHover(null, null))
    this.map.on('click', (event) => this.handleClick(event))
  }

  destroy(): void {
    cancelAnimationFrame(this.pointerFrame)
    cancelAnimationFrame(this.ghostFrame)
    this.map.remove()
  }

  resize(): void {
    this.map.resize()
  }

  // ------------------------------------------------------------------ public API
  setTheme(theme: Theme): void {
    if (theme === this.theme) return
    this.theme = theme
    this.styleReady = false
    this.map.setStyle(BASEMAP_STYLES[theme])
  }

  setPlan(view: PlanView | null): void {
    this.plan = view
    this.tracks = new Map(view?.scored.plan.routes.map((r) => [r.id, new RouteTrack(r)]) ?? [])
    if (!this.styleReady) return
    this.renderPlan()
    this.fitToPlan()
  }

  setHeatmap(view: HeatmapView | null): void {
    const sameData =
      this.heat && view && this.heat.frames === view.frames && this.heat.points === view.points
    this.heat = view
    if (!this.styleReady) return
    if (!sameData) this.renderHeatData()
    this.renderHeatStyle()
  }

  /** Called on every slider tick or playback step: paint-property changes only. */
  setHour(hour: number, transition?: HourTransition): void {
    this.hour = hour
    if (!this.styleReady) return
    if (this.map.getLayer(LYR.heat)) {
      this.map.setPaintProperty(LYR.heat, 'heatmap-weight', ['get', `h${hour}`])
    }
    if (transition) this.driveGhost(transition)
    else this.renderGhost()
  }

  setHover(target: HoverTarget | null): void {
    if (this.styleReady) {
      this.applyFeatureState(this.hover, { hover: false })
      this.applyFeatureState(target, { hover: true })
    }
    this.hover = target
  }

  setActiveCheckpoint(ref: CheckpointRef | null): void {
    if (this.styleReady) {
      this.applyFeatureState(this.active && { kind: 'checkpoint', ...this.active }, {
        active: false,
      })
      this.applyFeatureState(ref && { kind: 'checkpoint', ...ref }, { active: true })
    }
    this.active = ref
    if (ref && this.styleReady) this.ensureVisible(ref)
  }

  // ------------------------------------------------------------------ style setup
  private installStyle(): void {
    tintBasemap(this.map, this.theme)
    this.registerImages()
    const beforeLabels = firstSymbolLayerId(this.map)
    const palette = riskPalette()

    for (const id of Object.values(SRC)) {
      this.map.addSource(id, {
        type: 'geojson',
        data: emptyCollection(),
        ...(id === SRC.selected ? { lineMetrics: true } : {}),
      })
    }

    this.map.addLayer(
      {
        id: LYR.heat,
        type: 'heatmap',
        source: SRC.heat,
        maxzoom: HEATMAP_MAX_ZOOM,
        paint: {
          'heatmap-weight': ['get', `h${this.hour}`],
          'heatmap-intensity': 1 / UNIFORM_FIELD_DENSITY,
          'heatmap-opacity-transition': { duration: 200 },
        },
      },
      beforeLabels,
    )

    this.map.addLayer({
      id: LYR.casing,
      type: 'line',
      source: SRC.routes,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': cssColor('--route-casing'), 'line-width': 7, 'line-opacity': 0.55 },
    })
    this.map.addLayer({
      id: LYR.muted,
      type: 'line',
      source: SRC.routes,
      filter: ['!', ['get', 'selected']],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': cssColor('--route-muted'),
        'line-width': ['case', ['boolean', ['feature-state', 'hover'], false], 5, 3.5],
        'line-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 1, 0.8],
        'line-dasharray': [2, 1.4],
      },
    })
    this.map.addLayer({
      id: LYR.selectedCasing,
      type: 'line',
      source: SRC.selected,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': cssColor('--route-casing'), 'line-width': 10 },
    })
    this.map.addLayer({
      id: LYR.selected,
      type: 'line',
      source: SRC.selected,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-width': 6,
        'line-gradient': [
          'interpolate',
          ['linear'],
          ['line-progress'],
          0,
          palette[0],
          1,
          palette[0],
        ],
      },
    })
    this.map.addLayer({
      id: LYR.checkpoints,
      type: 'circle',
      source: SRC.checkpoints,
      paint: {
        'circle-color': [
          'match',
          ['get', 'level'],
          0,
          palette[0],
          1,
          palette[1],
          2,
          palette[2],
          3,
          palette[3],
          4,
          palette[4],
          cssColor('--risk-unknown'),
        ],
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          4,
          ['case', ['get', 'selected'], ['+', 3, ['*', 0.6, ['max', ['get', 'level'], 0]]], 2],
          10,
          ['case', ['get', 'selected'], ['+', 6, ['*', 1, ['max', ['get', 'level'], 0]]], 3],
        ],
        'circle-opacity': ['case', ['get', 'selected'], 1, 0.35],
        'circle-stroke-color': [
          'case',
          ['boolean', ['feature-state', 'active'], false],
          cssColor('--accent'),
          ['boolean', ['feature-state', 'hover'], false],
          cssColor('--text-1'),
          cssColor('--route-casing'),
        ],
        'circle-stroke-width': [
          'case',
          [
            'any',
            ['boolean', ['feature-state', 'active'], false],
            ['boolean', ['feature-state', 'hover'], false],
          ],
          3,
          1.5,
        ],
        'circle-stroke-opacity': ['case', ['get', 'selected'], 1, 0.35],
      },
    })
    this.map.addLayer({
      id: LYR.shields,
      type: 'symbol',
      source: SRC.routes,
      layout: {
        'symbol-placement': 'line-center',
        'icon-image': [
          'concat',
          'shield-',
          ['get', 'id'],
          ['case', ['get', 'selected'], '-on', '-off'],
        ],
        'icon-allow-overlap': true,
        'icon-rotation-alignment': 'viewport',
      },
    })
    this.map.addLayer({
      id: LYR.endpoints,
      type: 'symbol',
      source: SRC.endpoints,
      layout: { 'icon-image': ['get', 'icon'], 'icon-allow-overlap': true },
    })
    this.map.addLayer({
      id: LYR.ghost,
      type: 'symbol',
      source: SRC.ghost,
      layout: {
        'icon-image': 'truck',
        'icon-allow-overlap': true,
        'icon-rotate': ['get', 'bearing'],
        'icon-rotation-alignment': 'map',
      },
      paint: { 'icon-opacity': ['case', ['get', 'moving'], 1, 0.55] },
    })

    this.styleReady = true
    this.renderPlan()
    this.renderHeatData()
    this.renderHeatStyle()
    this.setHour(this.hour)
    this.setActiveCheckpoint(this.active)
    this.fitToPlan()
  }

  private registerImages(): void {
    const ink = cssColor('--text-1')
    const add = (name: string, image: ReturnType<typeof truckIcon>) => {
      if (this.map.hasImage(name)) this.map.removeImage(name)
      this.map.addImage(name, image, { pixelRatio: image.pixelRatio })
    }
    add(
      'truck',
      truckIcon({
        fill: cssColor('--accent'),
        ink: cssColor('--accent-ink'),
        halo: 'rgba(0,0,0,0.35)',
      }),
    )
    add('origin', endpointIcon('origin', { fill: ink, ink: cssColor('--bg-0') }))
    add('destination', endpointIcon('destination', { fill: ink, ink: cssColor('--bg-0') }))
    for (const letter of 'ABCDEFGH') {
      add(
        `shield-${letter}-on`,
        shieldIcon(letter, { fill: cssColor('--bg-3'), stroke: cssColor('--accent'), text: ink }),
      )
      add(
        `shield-${letter}-off`,
        shieldIcon(letter, {
          fill: cssColor('--bg-2'),
          stroke: cssColor('--route-muted'),
          text: ink,
        }),
      )
    }
  }

  // ------------------------------------------------------------------ rendering
  private source(id: string): GeoJSONSource {
    return this.map.getSource(id) as GeoJSONSource
  }

  private renderPlan(): void {
    const view = this.plan
    if (!view) {
      for (const id of [SRC.routes, SRC.selected, SRC.checkpoints, SRC.ghost, SRC.endpoints]) {
        this.source(id).setData(emptyCollection())
      }
      return
    }
    const { scored, selectedRouteId } = view
    const palette = riskPalette()

    this.source(SRC.routes).setData({
      type: 'FeatureCollection',
      features: scored.routes.map((r, i) => ({
        type: 'Feature',
        id: i,
        properties: { id: r.route.id, selected: r.route.id === selectedRouteId },
        geometry: { type: 'LineString', coordinates: r.route.geometry },
      })),
    })

    const selected = scored.routes.find((r) => r.route.id === selectedRouteId)
    this.source(SRC.selected).setData(
      selected
        ? {
            type: 'Feature',
            properties: {},
            geometry: { type: 'LineString', coordinates: selected.route.geometry },
          }
        : emptyCollection(),
    )
    if (selected) {
      const stops = riskGradientStops(selected.route.checkpoints, (i) => {
        const level = selected.checkpoints[i]?.risk?.level
        return level === undefined ? cssColor('--risk-unknown') : palette[level]!
      })
      this.map.setPaintProperty(LYR.selected, 'line-gradient', [
        'interpolate',
        ['linear'],
        ['line-progress'],
        ...stops,
      ] as ExpressionSpecification)
    }

    this.source(SRC.checkpoints).setData({
      type: 'FeatureCollection',
      features: scored.routes.flatMap((r, routeIndex) =>
        r.checkpoints.map(({ checkpoint, risk }) => ({
          type: 'Feature' as const,
          id: routeIndex * CHECKPOINT_ID_STRIDE + checkpoint.index,
          properties: {
            routeId: r.route.id,
            index: checkpoint.index,
            level: risk?.level ?? UNKNOWN_LEVEL,
            selected: r.route.id === selectedRouteId,
          },
          geometry: { type: 'Point' as const, coordinates: [checkpoint.lon, checkpoint.lat] },
        })),
      ),
    })

    const { origin, destination } = scored.plan.inputs
    this.source(SRC.endpoints).setData({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { icon: 'origin' },
          geometry: { type: 'Point', coordinates: [origin.lon, origin.lat] },
        },
        {
          type: 'Feature',
          properties: { icon: 'destination' },
          geometry: { type: 'Point', coordinates: [destination.lon, destination.lat] },
        },
      ],
    })

    // Sources were replaced: re-apply interaction state to the new features.
    this.setHover(this.hover)
    this.setActiveCheckpoint(this.active)
    this.renderGhost()
  }

  private renderHeatData(): void {
    const heat = this.heat
    this.source(SRC.heat).setData(
      heat
        ? {
            type: 'FeatureCollection',
            features: heat.points.map((coordinates, i) => {
              const properties: Record<string, number> = {}
              heat.frames.forEach((weights, hour) => {
                properties[`h${hour}`] = Math.round(weights[i]! * 1000) / 1000
              })
              return { type: 'Feature', properties, geometry: { type: 'Point', coordinates } }
            }),
          }
        : emptyCollection(),
    )
  }

  private renderHeatStyle(): void {
    const heat = this.heat
    if (!heat) return
    this.map.setLayoutProperty(LYR.heat, 'visibility', heat.visible ? 'visible' : 'none')
    this.map.setPaintProperty(LYR.heat, 'heatmap-opacity', heat.opacity)
    this.map.setPaintProperty(LYR.heat, 'heatmap-color', heatmapColorRamp(heat.variable))

    const meanLat = heat.points.reduce((sum, p) => sum + p[1]!, 0) / Math.max(heat.points.length, 1)
    const radiusZ0 =
      (KERNEL_SPACING_RATIO * heat.spacingM) /
      (METERS_PER_PIXEL_Z0 * Math.cos((meanLat * Math.PI) / 180))
    // Exponential base 2 makes the kernel track ground distance exactly at every zoom.
    this.map.setPaintProperty(LYR.heat, 'heatmap-radius', [
      'interpolate',
      ['exponential', 2],
      ['zoom'],
      0,
      radiusZ0,
      HEATMAP_MAX_ZOOM,
      radiusZ0 * 2 ** HEATMAP_MAX_ZOOM,
    ])
  }

  /** Elapsed driving time at the current forecast hour, or null without a selected route. */
  private targetElapsedS(): number | null {
    const plan = this.plan?.scored.plan
    if (!plan || !this.selectedTrack()) return null
    const offsetS = (Date.parse(plan.heatmap.base_time) - Date.parse(plan.departure.utc)) / 1000
    return offsetS + this.hour * HOUR_S
  }

  private selectedTrack(): RouteTrack | undefined {
    const id = this.plan?.selectedRouteId
    return id ? this.tracks.get(id) : undefined
  }

  /** Jump the truck to the current hour (plan or route changed). */
  private renderGhost(): void {
    cancelAnimationFrame(this.ghostFrame)
    this.ghostTween = null
    this.drawGhost(this.targetElapsedS())
  }

  /** Drive the truck along the road from where it is now to the current hour. */
  private driveGhost({ durationMs, easing }: HourTransition): void {
    const toS = this.targetElapsedS()
    const fromS = this.ghostElapsedS
    if (toS === null || fromS === null || durationMs <= 0 || this.reducedMotion?.matches) {
      this.renderGhost()
      return
    }
    this.ghostTween = { fromS, toS, startMs: performance.now(), durationMs, easing }
    cancelAnimationFrame(this.ghostFrame)
    this.ghostFrame = requestAnimationFrame((now) => this.stepGhost(now))
  }

  private stepGhost(now: number): void {
    const tween = this.ghostTween
    if (!tween) return
    const t = Math.min((now - tween.startMs) / tween.durationMs, 1)
    const eased = tween.easing === 'linear' ? t : easeOutCubic(t)
    this.drawGhost(tween.fromS + (tween.toS - tween.fromS) * eased)
    if (t < 1) this.ghostFrame = requestAnimationFrame((next) => this.stepGhost(next))
    else this.ghostTween = null
  }

  private drawGhost(elapsedS: number | null): void {
    this.ghostElapsedS = elapsedS
    const track = this.selectedTrack()
    if (elapsedS === null || !track) {
      this.source(SRC.ghost).setData(emptyCollection())
      return
    }
    const [lon, lat, bearing] = track.pointAt(track.fractionAtElapsed(elapsedS))
    this.source(SRC.ghost).setData({
      type: 'Feature',
      properties: { bearing, moving: elapsedS > 0 && elapsedS < track.durationS },
      geometry: { type: 'Point', coordinates: [lon, lat] },
    })
  }

  private fitToPlan(): void {
    const plan = this.plan?.scored.plan
    if (!plan || plan.plan_id === this.fittedPlanId) return
    this.fittedPlanId = plan.plan_id
    const coords = plan.routes.flatMap((r) => r.geometry)
    const lons = coords.map((c) => c[0]!)
    const lats = coords.map((c) => c[1]!)
    const bounds: LngLatBoundsLike = [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ]
    this.map.fitBounds(bounds, {
      padding: { top: 70, bottom: 50, left: 60, right: 70 },
      duration: 900,
    })
  }

  private ensureVisible(ref: CheckpointRef): void {
    const checkpoint = this.plan?.scored.plan.routes.find((r) => r.id === ref.routeId)?.checkpoints[
      ref.index
    ]
    if (!checkpoint) return
    const point = this.map.project([checkpoint.lon, checkpoint.lat])
    const { clientWidth, clientHeight } = this.map.getContainer()
    const margin = 80
    if (
      point.x < margin ||
      point.y < margin ||
      point.x > clientWidth - margin ||
      point.y > clientHeight - margin
    ) {
      this.map.easeTo({ center: [checkpoint.lon, checkpoint.lat], duration: 500 })
    }
  }

  // ------------------------------------------------------------------ interaction
  private applyFeatureState(target: HoverTarget | null, state: Record<string, boolean>): void {
    const plan = this.plan?.scored.plan
    if (!target || !plan) return
    const routeIndex = plan.routes.findIndex((r) => r.id === target.routeId)
    if (routeIndex === -1) return
    if (target.kind === 'checkpoint') {
      this.map.setFeatureState(
        { source: SRC.checkpoints, id: routeIndex * CHECKPOINT_ID_STRIDE + target.index },
        state,
      )
    } else {
      this.map.setFeatureState({ source: SRC.routes, id: routeIndex }, state)
    }
  }

  private hitTest(event: MapMouseEvent) {
    if (!this.styleReady) return null
    const { x, y } = event.point
    const features = this.map.queryRenderedFeatures(
      [
        [x - HIT_TOLERANCE_PX, y - HIT_TOLERANCE_PX],
        [x + HIT_TOLERANCE_PX, y + HIT_TOLERANCE_PX],
      ],
      { layers: INTERACTIVE_LAYERS },
    )
    const checkpoint = features.find((f) => f.layer.id === LYR.checkpoints && f.properties.selected)
    if (checkpoint) {
      return {
        kind: 'checkpoint' as const,
        routeId: String(checkpoint.properties.routeId),
        index: Number(checkpoint.properties.index),
      }
    }
    const muted = features.find((f) => f.layer.id === LYR.muted)
    if (muted) return { kind: 'route' as const, routeId: String(muted.properties.id) }
    const selected = features.find((f) => f.layer.id === LYR.selected)
    if (selected && this.plan?.selectedRouteId)
      return { kind: 'route' as const, routeId: this.plan.selectedRouteId }
    return null
  }

  /** Coalesce pointer moves to one hit test per animation frame. */
  private queuePointer(event: MapMouseEvent): void {
    this.pendingPointer = event
    if (this.pointerFrame) return
    this.pointerFrame = requestAnimationFrame(() => {
      this.pointerFrame = 0
      const pending = this.pendingPointer
      if (!pending) return
      const target = this.hitTest(pending)
      this.map.getCanvas().style.cursor = target ? 'pointer' : ''
      this.callbacks.onHover(target, target ? pending.point : null)
    })
  }

  private handleClick(event: MapMouseEvent): void {
    const target = this.hitTest(event)
    if (target?.kind === 'checkpoint')
      this.callbacks.onOpenCheckpoint({ routeId: target.routeId, index: target.index })
    else if (target?.kind === 'route') this.callbacks.onSelectRoute(target.routeId)
  }
}

// ------------------------------------------------------------------ colour helpers
type Palette = [low: string, moderate: string, high: string, severe: string, noTravel: string]

function riskPalette(): Palette {
  return [0, 1, 2, 3, 4].map((level) => cssColor(`--risk-${level}`)) as Palette
}

function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16))
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** Density → colour, with each risk colour starting exactly at its rule threshold. */
export function heatmapColorRamp(variable: HeatmapVariable): ExpressionSpecification {
  const scale = VARIABLE_SCALES[variable]
  const [t1, t2, t3, t4] = scale.thresholds.map((v) => v / scale.max) as [
    number,
    number,
    number,
    number,
  ]
  const floor = Math.min(HEATMAP_FLOOR, t1 * 0.5)
  const [low, moderate, high, severe, noTravel] = riskPalette()
  return [
    'interpolate',
    ['linear'],
    ['heatmap-density'],
    0,
    'rgba(0, 0, 0, 0)',
    floor,
    withAlpha(low, 0),
    t1 * 0.999,
    withAlpha(low, 0.4),
    t1,
    withAlpha(moderate, 0.75),
    t2,
    withAlpha(high, 0.85),
    t3,
    withAlpha(severe, 0.9),
    t4,
    withAlpha(noTravel, 0.95),
    1,
    noTravel,
  ]
}
