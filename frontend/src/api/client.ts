import type { PlaceResult, PlanRequest, PlanResponse, Problem } from './types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

export class ApiError extends Error {
  readonly status: number
  readonly problem: Problem | null

  constructor(status: number, problem: Problem | null) {
    super(problem?.detail ?? `Request failed (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
  }

  /** First message for a field, if the API rejected that field. */
  fieldError(field: string): string | undefined {
    return this.problem?.errors?.[field]?.[0]
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, {
      type: '/problems/network',
      title: 'Network error',
      status: 0,
      detail: 'Could not reach the server. Check your connection and try again.',
    })
  }
  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as Problem | null
    throw new ApiError(response.status, problem)
  }
  return (await response.json()) as T
}

export const api = {
  plan(body: PlanRequest, signal?: AbortSignal): Promise<PlanResponse> {
    return request('/api/v1/plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  },

  /** A plan exactly as it was computed, for shared links. */
  snapshot(planId: string, signal?: AbortSignal): Promise<PlanResponse> {
    return request(`/api/v1/plans/${encodeURIComponent(planId)}`, { signal })
  },

  async timezone(lat: number, lon: number, signal?: AbortSignal): Promise<string> {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) })
    const data = await request<{ tz: string }>(`/api/v1/timezone?${params}`, { signal })
    return data.tz
  },

  async geocode(query: string, signal?: AbortSignal): Promise<PlaceResult[]> {
    const params = new URLSearchParams({ q: query })
    const data = await request<{ results: PlaceResult[] }>(`/api/v1/geocode?${params}`, {
      signal,
    })
    return data.results
  },

  async reverse(lat: number, lon: number, signal?: AbortSignal): Promise<string | null> {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) })
    const data = await request<{ label: string | null }>(`/api/v1/reverse?${params}`, { signal })
    return data.label
  },
}
