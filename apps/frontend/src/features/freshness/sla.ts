import type { SLAStatus } from '@/types/freshness'

export const SLA_LABELS: Record<SLAStatus, string> = {
  ok: 'Até 12h',
  warning_12_24: '12h a 24h',
  warning_24_48: '24h a 48h',
  warning_48_7d: '48h a 7d',
  warning_7d_1m: '7d a 1m',
  stale: '>1 mês',
}

export const SLA_TEXT_COLOR: Record<SLAStatus, string> = {
  ok: 'text-status-ok',
  warning_12_24: 'text-status-ok',
  warning_24_48: 'text-status-warn',
  warning_48_7d: 'text-status-warn',
  warning_7d_1m: 'text-status-error',
  stale: 'text-status-error',
}

export const SLA_SHORT_LABELS: Record<SLAStatus, string> = {
  ok: '≤12h',
  warning_12_24: '12-24h',
  warning_24_48: '24-48h',
  warning_48_7d: '48h-7d',
  warning_7d_1m: '7d-1m',
  stale: '>1m',
}

export const SLA_ORDER: SLAStatus[] = [
  'ok',
  'warning_12_24',
  'warning_24_48',
  'warning_48_7d',
  'warning_7d_1m',
  'stale',
]
