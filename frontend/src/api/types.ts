/** Friendly aliases over the generated OpenAPI types (run `pnpm gen:api` after API changes). */
import type { components } from './schema.gen'

type Schemas = components['schemas']

export type PlanRequest = Schemas['PlanRequestRequest']
export type PlanResponse = Schemas['PlanResponse']
export type Route = Schemas['Route']
export type Checkpoint = Schemas['Checkpoint']
export type RestStop = Schemas['RestStop']
export type RouteAlert = Schemas['RouteAlert']
export type Advisory = Schemas['Advisory']
export type CheckpointRisk = Schemas['Risk']
export type CheckpointWeather = Schemas['Weather']
export type HourlyWindow = Schemas['HourlyWindow']
export type Heatmap = Schemas['Heatmap']
export type Recommendation = Schemas['Recommendation']
export type RouteSummary = Schemas['RouteSummary']
export type LocalTime = Schemas['LocalTime']
export type PlanWarning = Schemas['Warning']
export type PlaceResult = Schemas['PlaceResult']
export type IntervalMi = Schemas['IntervalMiEnum']
export type RouteTag = Schemas['TagsEnum']
export type Factor = Schemas['DriverEnum']
export type LoadRule = Schemas['LoadRuleEnum']
export type CriterionSlug = Schemas['DecidingCriterionEnum']

/** A place the user has chosen: a resolved label and coordinates. */
export interface Place {
  label: string
  lat: number
  lon: number
}

/** RFC 9457 problem details returned by the API for every error. */
export interface Problem {
  type: string
  title: string
  status: number
  detail: string
  errors?: Record<string, string[]>
}
