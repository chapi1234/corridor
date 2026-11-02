import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'

import { formatLocal, formatMiles } from '@/domain/format'
import { FACTOR_LABEL, LEVEL_META, UNKNOWN_META, cssColor } from '@/domain/levels'
import type { ScoredPlan, ScoredRoute } from '@/domain/scoring'
import { elapsedAtHour, mileAtElapsed } from '@/domain/timeline'
import { useScoredPlan } from '@/state/selectors'
import { useAppStore, type CheckpointRef } from '@/state/store'
import { RouteShield } from '@/ui/RouteShield'

import { ownedSpans, spanAt, type RibbonSpan } from './ribbonLayout'
import styles from './RiskRibbon.module.css'

const ROW_H = 22
const ROW_GAP = 8
const AXIS_H = 16
const AXIS_STEPS_MI = [25, 50, 100, 200, 250, 500, 1000] as const

interface Row {
  route: ScoredRoute
  spans: RibbonSpan[]
}

/** Every route as a strip of risk by mile, on a shared mile axis — the "where" of the risk. */
export function RiskRibbon() {
  const scored = useScoredPlan()
  if (!scored) return null
  return <Ribbon scored={scored} />
}

function Ribbon({ scored }: { scored: ScoredPlan }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [width, setWidth] = useState(0)
  const selectedRouteId = useAppStore((s) => s.selectedRouteId)
  const hover = useAppStore((s) => s.hover)
  const hour = useAppStore((s) => s.forecastHour)
  const theme = useAppStore((s) => s.theme)

  const rows = useMemo<Row[]>(() => {
    const byId = new Map(scored.routes.map((r) => [r.route.id, r]))
    return scored.ranking.order
      .map((id) => byId.get(id))
      .filter((r): r is ScoredRoute => r !== undefined)
      .map((route) => ({ route, spans: ownedSpans(route) }))
  }, [scored])
  const maxMi = Math.max(...rows.map((r) => r.route.route.distance_mi), 1)
  const height = AXIS_H + rows.length * (ROW_H + ROW_GAP)
  const hoveredCheckpoint = hover?.kind === 'checkpoint' ? hover : null

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry?.contentRect.width ?? 0))
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || width === 0) return
    draw(canvas, { rows, width, height, maxMi, selectedRouteId, hoveredCheckpoint, hour, scored })
    // `theme` invalidates the resolved CSS colours.
  }, [rows, width, height, maxMi, selectedRouteId, hoveredCheckpoint, hour, scored, theme])

  const hitTest = (event: MouseEvent<HTMLCanvasElement>): CheckpointRef | null => {
    const rect = event.currentTarget.getBoundingClientRect()
    const y = event.clientY - rect.top - AXIS_H
    const rowIndex = Math.floor(y / (ROW_H + ROW_GAP))
    const row = rows[rowIndex]
    if (!row || y - rowIndex * (ROW_H + ROW_GAP) > ROW_H) return null
    const mile = ((event.clientX - rect.left) / rect.width) * maxMi
    if (mile > row.route.route.distance_mi) return null
    const index = spanAt(row.spans, mile)
    return index === null ? null : { routeId: row.route.route.id, index }
  }

  const readout = hoveredCheckpoint ? describe(scored, hoveredCheckpoint) : null

  return (
    <section className={styles.ribbon} aria-label="Risk by mile for each route">
      <div className={styles.labels} style={{ paddingTop: AXIS_H }}>
        {rows.map(({ route }) => (
          <button
            key={route.route.id}
            type="button"
            className={styles.rowLabel}
            style={{ height: ROW_H, marginBottom: ROW_GAP }}
            aria-pressed={route.route.id === selectedRouteId}
            onClick={() => useAppStore.getState().selectRoute(route.route.id)}
          >
            <RouteShield
              id={route.route.id}
              size={18}
              selected={route.route.id === selectedRouteId}
            />
            <span className="num">{formatMiles(route.route.distance_mi)}</span>
          </button>
        ))}
      </div>
      <div className={styles.plot}>
        <canvas
          ref={canvasRef}
          className={styles.canvas}
          style={{ height }}
          onPointerMove={(event) => {
            const ref = hitTest(event)
            useAppStore.getState().setHover(ref ? { kind: 'checkpoint', ...ref } : null)
          }}
          onPointerLeave={() => useAppStore.getState().setHover(null)}
          onClick={(event) => {
            const ref = hitTest(event)
            if (ref) useAppStore.getState().openCheckpointDetail(ref)
          }}
        />
        <p className={styles.readout} aria-live="polite">
          {readout ?? 'Hover a strip to inspect a checkpoint · click to open it'}
        </p>
      </div>
    </section>
  )
}

function describe(scored: ScoredPlan, ref: CheckpointRef): string | null {
  const entry = scored.routes.find((r) => r.route.id === ref.routeId)?.checkpoints[ref.index]
  if (!entry) return null
  const { checkpoint, risk } = entry
  const level = risk ? LEVEL_META[risk.level].label : UNKNOWN_META.label
  const driver = risk ? ` · ${FACTOR_LABEL[risk.driver]}` : ''
  return `Route ${ref.routeId} · mile ${Math.round(checkpoint.mile)} · ${level}${driver} · ETA ${formatLocal(checkpoint.eta)}`
}

interface DrawInput {
  rows: Row[]
  width: number
  height: number
  maxMi: number
  selectedRouteId: string | null
  hoveredCheckpoint: CheckpointRef | null
  hour: number
  scored: ScoredPlan
}

function draw(canvas: HTMLCanvasElement, input: DrawInput): void {
  const { rows, width, height, maxMi, selectedRouteId, hoveredCheckpoint, hour, scored } = input
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.round(width * dpr)
  canvas.height = Math.round(height * dpr)
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)

  const colors = {
    levels: ([0, 1, 2, 3, 4] as const).map((l) => cssColor(LEVEL_META[l].cssVar)),
    unknown: cssColor(UNKNOWN_META.cssVar),
    grid: cssColor('--line-1'),
    axis: cssColor('--text-3'),
    accent: cssColor('--accent'),
    rest: cssColor('--rest'),
    ink: cssColor('--text-1'),
    bg: cssColor('--bg-0'),
  }
  const x = (mile: number) => (mile / maxMi) * width

  // Mile axis: the finest round step that keeps labels at least ~48 px apart.
  const step = AXIS_STEPS_MI.find((s) => x(s) >= 48) ?? AXIS_STEPS_MI.at(-1)!
  ctx.font = '10px "IBM Plex Mono", monospace'
  ctx.textBaseline = 'top'
  for (let mile = 0; mile <= maxMi; mile += step) {
    const px = Math.round(x(mile)) + 0.5
    ctx.fillStyle = colors.grid
    ctx.fillRect(px, AXIS_H - 4, 1, height - AXIS_H + 4)
    ctx.fillStyle = colors.axis
    ctx.textAlign = mile === 0 ? 'left' : px > width - 30 ? 'right' : 'center'
    ctx.fillText(mile === 0 ? 'MI 0' : String(mile), px, 0)
  }

  const elapsedS = elapsedAtHour(scored.plan, hour)
  rows.forEach(({ route, spans }, rowIndex) => {
    const top = AXIS_H + rowIndex * (ROW_H + ROW_GAP)
    const selected = route.route.id === selectedRouteId
    ctx.globalAlpha = selected || selectedRouteId === null ? 1 : 0.55
    const barTop = selected ? top : top + 4
    const barH = selected ? ROW_H : ROW_H - 8

    for (const span of spans) {
      const level = route.checkpoints[span.index]?.risk?.level
      const left = x(span.startMi)
      const spanWidth = Math.max(x(span.endMi) - left, 1)
      if (level === undefined) {
        ctx.fillStyle = colors.unknown
        ctx.fillRect(left, barTop, spanWidth, barH)
        hatch(ctx, left, barTop, spanWidth, barH, colors.bg)
      } else {
        ctx.fillStyle = colors.levels[level]!
        ctx.fillRect(left, barTop, spanWidth, barH)
        if (level === 4) hatch(ctx, left, barTop, spanWidth, barH, colors.bg)
      }
    }
    ctx.globalAlpha = 1

    if (selected) {
      ctx.strokeStyle = colors.accent
      ctx.lineWidth = 1
      ctx.strokeRect(0.5, top + 0.5, x(route.route.distance_mi) - 1, ROW_H - 1)
    }

    // Mandatory rest stops: a services-blue pin at the mile where the driver stops.
    for (const rest of route.route.rest_stops) {
      const px = Math.round(x(rest.mile))
      ctx.fillStyle = colors.rest
      ctx.fillRect(px - 1, barTop, 2, barH)
      ctx.fillRect(px - 3, top - 3, 6, rest.kind === 'reset' ? 6 : 4)
    }

    // Truck position at the current forecast hour.
    if (elapsedS > 0 && elapsedS < route.route.duration_s) {
      const px = x(mileAtElapsed(route.route, elapsedS))
      ctx.fillStyle = colors.ink
      ctx.beginPath()
      ctx.moveTo(px - 4, top - 3)
      ctx.lineTo(px + 4, top - 3)
      ctx.lineTo(px, top + 3)
      ctx.closePath()
      ctx.fill()
      ctx.fillRect(px - 0.75, top, 1.5, ROW_H)
    }
  })

  // Crosshair on the hovered checkpoint (from the ribbon or the map).
  if (hoveredCheckpoint) {
    const row = rows.find((r) => r.route.route.id === hoveredCheckpoint.routeId)
    const checkpoint = row?.route.route.checkpoints[hoveredCheckpoint.index]
    if (checkpoint) {
      const px = Math.round(x(checkpoint.mile)) + 0.5
      ctx.strokeStyle = colors.ink
      ctx.setLineDash([3, 3])
      ctx.beginPath()
      ctx.moveTo(px, AXIS_H - 4)
      ctx.lineTo(px, height)
      ctx.stroke()
      ctx.setLineDash([])
    }
  }
}

/** Diagonal hatch used for No Travel and missing data, so they never rely on colour alone. */
function hatch(
  ctx: CanvasRenderingContext2D,
  left: number,
  top: number,
  w: number,
  h: number,
  color: string,
): void {
  ctx.save()
  ctx.beginPath()
  ctx.rect(left, top, w, h)
  ctx.clip()
  ctx.strokeStyle = color
  ctx.globalAlpha = 0.35
  ctx.lineWidth = 1.5
  for (let offset = -h; offset < w; offset += 6) {
    ctx.beginPath()
    ctx.moveTo(left + offset, top + h)
    ctx.lineTo(left + offset + h, top)
    ctx.stroke()
  }
  ctx.restore()
}
