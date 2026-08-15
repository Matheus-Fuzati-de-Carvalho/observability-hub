export type PiiType = 'email' | 'cpf' | 'cnpj' | 'telefone_br' | 'cep' | 'cartao_credito'

export interface PiiScanRequest {
  sample_percent: number
  match_threshold_pct: number
}

export interface PiiEstimateResponse {
  estimated_bytes: number
  estimated_bytes_human: string
  estimated_cost_usd: number
  sql: string | null
}

export interface PiiTypeMatch {
  pii_type: PiiType
  match_count: number
  match_ratio: number
  flagged: boolean
}

export interface PiiColumnResult {
  column_name: string
  data_type: string
  name_match_types: PiiType[]
  sample_non_null_count: number | null
  sample_matches: PiiTypeMatch[]
  flagged: boolean
  confidence: 'high' | 'medium' | null
}

export interface PiiExcludedColumn {
  column_name: string
  reason: string
}

export interface PiiScanResponse {
  project_id: string
  dataset_id: string
  table_id: string
  executed_at: string
  is_view: boolean
  parameters: PiiScanRequest
  sql: string | null
  columns: PiiColumnResult[]
  excluded_columns: PiiExcludedColumn[]
  warning: string | null
}
