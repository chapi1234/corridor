import { MapPin } from 'lucide-react'
import { useId, useState, type KeyboardEvent } from 'react'

import { useGeocode } from '@/api/queries'
import type { Place, PlaceResult } from '@/api/types'

import styles from './PlaceField.module.css'

interface PlaceFieldProps {
  label: string
  value: Place | null
  onChange(place: Place | null): void
  placeholder: string
  error?: string | undefined
  marker: 'origin' | 'destination'
}

/** Place autocomplete following the WAI-ARIA combobox pattern. */
export function PlaceField({
  label,
  value,
  onChange,
  placeholder,
  error,
  marker,
}: PlaceFieldProps) {
  const id = useId()
  const [text, setText] = useState(value?.label ?? '')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [syncedLabel, setSyncedLabel] = useState(value?.label)

  // Keep the input in sync when the value changes from outside (swap, URL, examples).
  if (value?.label !== syncedLabel) {
    setSyncedLabel(value?.label)
    setText(value?.label ?? '')
  }

  const query = useGeocode(open ? text : '')
  const results = query.data ?? []
  const listId = `${id}-list`

  function choose(result: PlaceResult) {
    onChange({ label: result.label, lat: result.lat, lon: result.lon })
    setText(result.label)
    setOpen(false)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(i + 1, results.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter' && open && results[active]) {
      event.preventDefault()
      choose(results[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = open && text.trim().length >= 2

  return (
    <div className={styles.field} data-invalid={Boolean(error)}>
      <label htmlFor={id} className="label">
        {label}
      </label>
      <div className={styles.inputWrap}>
        <span className={styles.marker} data-kind={marker} aria-hidden />
        <input
          id={id}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
          aria-invalid={Boolean(error)}
          autoComplete="off"
          spellCheck={false}
          className={styles.input}
          value={text}
          placeholder={placeholder}
          onChange={(event) => {
            setText(event.target.value)
            setActive(0)
            setOpen(true)
            if (value) onChange(null)
          }}
          onFocus={() => text && !value && setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
      </div>
      {showList && (
        <ul id={listId} role="listbox" className={styles.list}>
          {query.isFetching && results.length === 0 && (
            <li className={styles.status}>Searching…</li>
          )}
          {!query.isFetching && results.length === 0 && (
            <li className={styles.status}>No places found in the US or Canada</li>
          )}
          {results.map((result, index) => (
            <li
              key={`${result.id}-${index}`}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              className={styles.option}
              onMouseDown={(event) => {
                event.preventDefault()
                choose(result)
              }}
              onMouseEnter={() => setActive(index)}
            >
              <MapPin size={14} aria-hidden />
              <span className={styles.optionText}>
                <span>{result.label}</span>
                {result.sublabel && <span className={styles.sublabel}>{result.sublabel}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
      {error && <p className={styles.error}>{error}</p>}
    </div>
  )
}
