import * as Popover from '@radix-ui/react-popover'
import { Layers } from 'lucide-react'

import { VARIABLE_SCALES, type HeatmapVariable } from '@/domain/heatmap'
import { useAppStore } from '@/state/store'
import { Segmented } from '@/ui/Segmented'

import styles from './LayerControl.module.css'

const VARIABLES = (Object.keys(VARIABLE_SCALES) as HeatmapVariable[]).map((value) => ({
  value,
  label: VARIABLE_SCALES[value].label,
}))

export function LayerControl() {
  const heatmap = useAppStore((s) => s.heatmap)
  const updateHeatmap = useAppStore((s) => s.updateHeatmap)

  return (
    <Popover.Root>
      <Popover.Trigger className={styles.trigger} aria-label="Map layers">
        <Layers size={16} />
        <span>Layers</span>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className={styles.panel} side="bottom" align="end" sideOffset={6}>
          <label className={styles.toggleRow}>
            <input
              type="checkbox"
              checked={heatmap.visible}
              onChange={(event) => updateHeatmap({ visible: event.target.checked })}
            />
            <span>Weather heatmap</span>
            <kbd>H</kbd>
          </label>
          <div className={styles.group} aria-disabled={!heatmap.visible}>
            <span className="label">Show</span>
            <Segmented
              size="sm"
              label="Heatmap variable"
              value={heatmap.variable}
              options={VARIABLES}
              onChange={(variable) => updateHeatmap({ variable, visible: true })}
            />
          </div>
          <label className={styles.group}>
            <span className="label">Opacity</span>
            <input
              type="range"
              min={0.2}
              max={1}
              step={0.05}
              value={heatmap.opacity}
              onChange={(event) => updateHeatmap({ opacity: Number(event.target.value) })}
            />
          </label>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
