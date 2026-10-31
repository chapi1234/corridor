/** Helpers for "YYYY-MM-DDTHH:MM" wall-clock strings, as used by <input type="datetime-local">. */

const pad = (n: number) => String(n).padStart(2, '0')

export function toLocalInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function nextFullHour(now = new Date()): string {
  const next = new Date(now)
  next.setHours(next.getHours() + 1, 0, 0, 0)
  return toLocalInputValue(next)
}

export function shiftHours(value: string, hours: number): string {
  const date = new Date(value)
  date.setHours(date.getHours() + hours)
  return toLocalInputValue(date)
}

export function tomorrowAt(hour: number, now = new Date()): string {
  const date = new Date(now)
  date.setDate(date.getDate() + 1)
  date.setHours(hour, 0, 0, 0)
  return toLocalInputValue(date)
}
