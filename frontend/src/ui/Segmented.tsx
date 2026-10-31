import styles from './Segmented.module.css'

interface SegmentedProps<T extends string | number> {
  label: string
  value: T
  options: readonly { value: T; label: string }[]
  onChange(value: T): void
  size?: 'sm' | 'md'
}

/** Single-choice control with radio-group semantics. */
export function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
  size = 'md',
}: SegmentedProps<T>) {
  return (
    <div role="radiogroup" aria-label={label} className={`${styles.group} ${styles[size]}`}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          className={styles.option}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
