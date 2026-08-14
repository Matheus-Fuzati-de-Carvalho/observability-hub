import { useMutation } from '@tanstack/react-query'
import { piiApi } from '@/lib/api/pii'
import type { PiiScanRequest } from '@/types/pii'

interface PiiTarget {
  projectId: string
  datasetId: string
  tableId: string
}

export function useEstimatePiiScan() {
  return useMutation({
    mutationFn: ({ projectId, datasetId, tableId, ...body }: PiiTarget & PiiScanRequest) =>
      piiApi.estimate(projectId, datasetId, tableId, body),
  })
}

export function useRunPiiScan() {
  return useMutation({
    mutationFn: ({ projectId, datasetId, tableId, ...body }: PiiTarget & PiiScanRequest) =>
      piiApi.run(projectId, datasetId, tableId, body),
  })
}
