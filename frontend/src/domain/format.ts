import type { LocalTime } from '@/api/types'

const numberFormat = new Intl.NumberFormat('en-US')

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) return `${minutes} min`
  return `${hours} h ${String(minutes).padStart(2, '0')} m`
}

export function formatMiles(miles: number, digits = 0): string {
  return `${miles.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })} mi`
}

export function formatPounds(pounds: number): string {
  return `${numberFormat.format(Math.round(pounds))} lb`
}

const clockFormatters = new Map<string, Intl.DateTimeFormat>()

function clockFormatter(timeZone: string, withDay: boolean): Intl.DateTimeFormat {
  const key = `${timeZone}|${withDay}`
  let formatter = clockFormatters.get(key)
  if (!formatter) {
    formatter = new Intl.DateTimeFormat('en-US', {
      timeZone,
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
      timeZoneName: 'short',
      ...(withDay ? { weekday: 'short' } : {}),
    })
    clockFormatters.set(key, formatter)
  }
  return formatter
}

/** "Tue 14:05 CST" — a moment shown in the zone it happens in. */
export function formatLocal(time: LocalTime, { withDay = true } = {}): string {
  return clockFormatter(time.tz, withDay).format(new Date(time.utc)).replace(',', '')
}

/** Format a UTC instant in an explicit zone. */
export function formatInstant(
  utc: Date | string,
  timeZone: string,
  { withDay = true } = {},
): string {
  return clockFormatter(timeZone, withDay).format(new Date(utc)).replace(',', '')
}

export function formatHourOffset(hours: number): string {
  return hours === 0 ? 'Departure' : `+${hours} h`
}
