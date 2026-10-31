import type { Map as MapLibreMap } from 'maplibre-gl'

import type { Theme } from '@/state/store'

/** Keyless vector basemaps (CARTO, © OpenStreetMap contributors). */
export const BASEMAP_STYLES: Record<Theme, string> = {
  night: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  day: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
}

const TINTS: Record<Theme, { background: string; water: string; land: string }> = {
  night: { background: '#071d25', water: '#04131a', land: '#0a2430' },
  day: { background: '#eef3f3', water: '#cddfe3', land: '#e6eded' },
}

/**
 * Re-tint the stock basemap toward the console palette so the map reads as part of the
 * product, not a generic tile layer. Unknown layer ids are simply skipped.
 */
export function tintBasemap(map: MapLibreMap, theme: Theme): void {
  const tint = TINTS[theme]
  for (const layer of map.getStyle().layers ?? []) {
    try {
      if (layer.type === 'background') {
        map.setPaintProperty(layer.id, 'background-color', tint.background)
      } else if (layer.type === 'fill' && /water/.test(layer.id)) {
        map.setPaintProperty(layer.id, 'fill-color', tint.water)
      } else if (layer.type === 'fill' && /landcover|landuse|park/.test(layer.id)) {
        map.setPaintProperty(layer.id, 'fill-color', tint.land)
      }
    } catch {
      /* layer without that paint property: leave as is */
    }
  }
}

/** Id of the first label layer, so data layers can be slotted beneath place names. */
export function firstSymbolLayerId(map: MapLibreMap): string | undefined {
  return map.getStyle().layers?.find((layer) => layer.type === 'symbol')?.id
}
