import type { QualityFlag } from '@/types/profiling'

export interface HistoryColumnSnapshot {
  column_name: string
  completeness_pct: number
  quality_flag: QualityFlag
}

export interface ProfilingHistoryRun {
  executed_at: string
  executed_by: string
  overall_density: number
  estimated_duplicate_pct: number
  columns: HistoryColumnSnapshot[]
}

export interface ProfilingHistoryResponse {
  project_id: string
  dataset_id: string
  table_id: string
  runs: ProfilingHistoryRun[]
}
