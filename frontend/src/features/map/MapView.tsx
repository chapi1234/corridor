import { useEffect, useMemo, useRef, useState } from 'react'

import { buildFrames } from '@/domain/heatmap'
import { useScoredPlan } from '@/state/selectors'
import { useAppStore, type HoverTarget } from '@/state/store'

import { LayerControl } from './LayerControl'
import { Legend } from './Legend'
import { MapController } from './mapController'
import { MapTooltip } from './MapTooltip'
import styles from './MapView.module.css'

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null)
  const controllerRef = useRef<MapController | null>(null)
  const [tooltip, setTooltip] = useState<{ target: HoverTarget; x: number; y: number } | null>(null)

  const scored = useScoredPlan()
  const selectedRouteId = useAppStore((s) => s.selectedRouteId)
  const theme = useAppStore((s) => s.theme)
  const heatmap = useAppStore((s) => s.heatmap)

  // Create the map once; the controller lives for the component's lifetime.
  useEffect(() => {
    const store = useAppStore.getState()
    const controller = new MapController(containerRef.current!, store.theme, {
      onHover: (target, screen) => {
        useAppStore.getState().setHover(target)
        setTooltip(target && screen ? { target, x: screen.x, y: screen.y } : null)
      },
      onSelectRoute: (routeId) => useAppStore.getState().selectRoute(routeId),
      onOpenCheckpoint: (ref) => useAppStore.getState().openCheckpointDetail(ref),
    })
    controllerRef.current = controller

    // High-frequency state bypasses React rendering entirely.
    const unsubscribe = useAppStore.subscribe((state, previous) => {
      if (state.forecastHour !== previous.forecastHour) controller.setHour(state.forecastHour)
      if (state.hover !== previous.hover) controller.setHover(state.hover)
      if (state.openCheckpoint !== previous.openCheckpoint)
        controller.setActiveCheckpoint(state.openCheckpoint)
    })
    const resizeObserver = new ResizeObserver(() => controller.resize())
    resizeObserver.observe(containerRef.current!)

    return () => {
      unsubscribe()
      resizeObserver.disconnect()
      controller.destroy()
      controllerRef.current = null
    }
  }, [])

  useEffect(() => controllerRef.current?.setTheme(theme), [theme])

  useEffect(() => {
    controllerRef.current?.setPlan(scored ? { scored, selectedRouteId } : null)
  }, [scored, selectedRouteId, theme])

  const loadLb = scored?.loadLb
  const planHeatmap = scored?.plan.heatmap
  const frames = useMemo(
    () =>
      planHeatmap && loadLb !== undefined
        ? buildFrames(planHeatmap, heatmap.variable, loadLb)
        : null,
    [planHeatmap, heatmap.variable, loadLb],
  )

  useEffect(() => {
    controllerRef.current?.setHeatmap(
      frames && planHeatmap
        ? {
            frames,
            points: planHeatmap.points,
            spacingM: planHeatmap.spacing_m,
            variable: heatmap.variable,
            visible: heatmap.visible,
            opacity: heatmap.opacity,
          }
        : null,
    )
  }, [frames, planHeatmap, heatmap, theme])

  return (
    <div className={styles.wrap}>
      <div ref={containerRef} className={styles.map} aria-label="Route map" role="region" />
      {scored && (
        <>
          <LayerControl />
          <Legend />
        </>
      )}
      {tooltip && scored && <MapTooltip scored={scored} {...tooltip} />}
    </div>
  )
}
