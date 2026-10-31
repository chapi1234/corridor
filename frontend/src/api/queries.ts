import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'

import { useDebouncedValue } from '@/lib/useDebouncedValue'

import { api, type ApiError } from './client'
import type { PlanRequest, PlanResponse } from './types'

const GEOCODE_DEBOUNCE_MS = 250
const MIN_QUERY_LENGTH = 2

export function useGeocode(query: string) {
  const debounced = useDebouncedValue(query.trim(), GEOCODE_DEBOUNCE_MS)
  return useQuery({
    queryKey: ['geocode', debounced],
    queryFn: ({ signal }) => api.geocode(debounced, signal),
    enabled: debounced.length >= MIN_QUERY_LENGTH,
    staleTime: 10 * 60_000,
    placeholderData: keepPreviousData,
  })
}

export function useReverseGeocode(point: { lat: number; lon: number } | null) {
  return useQuery({
    queryKey: ['reverse', point?.lat.toFixed(2), point?.lon.toFixed(2)],
    queryFn: ({ signal }) => api.reverse(point!.lat, point!.lon, signal),
    enabled: point !== null,
    staleTime: Infinity,
  })
}

export function usePlanMutation(onSuccess: (plan: PlanResponse, request: PlanRequest) => void) {
  return useMutation<PlanResponse, ApiError, PlanRequest>({
    mutationFn: (body) => api.plan(body),
    onSuccess: (plan, request) => onSuccess(plan, request),
  })
}
