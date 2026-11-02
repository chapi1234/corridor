import { useId, type ReactNode } from 'react'

import styles from './Switch.module.css'

interface SwitchProps {
  label: string
  description?: ReactNode
  checked: boolean
  onChange(checked: boolean): void
}

/** On/off setting with a visible label and an optional explanation. */
export function Switch({ label, description, checked, onChange }: SwitchProps) {
  const id = useId()
  return (
    <div className={styles.row}>
      <div className={styles.text}>
        <label htmlFor={id} className="label">
          {label}
        </label>
        {description && (
          <span id={`${id}-description`} className={styles.description}>
            {description}
          </span>
        )}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={description ? `${id}-description` : undefined}
        className={styles.switch}
        onClick={() => onChange(!checked)}
      >
        <span className={styles.thumb} />
      </button>
    </div>
  )
}
