import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/app/layout'
import { AdminPage } from '@/features/admin/AdminPage'
import { RequireAdmin } from '@/features/admin/RequireAdmin'
import { AuthCallbackPage } from '@/features/auth/AuthCallbackPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CatalogDatasetPage } from '@/features/catalog/CatalogDatasetPage'
import { CatalogOverviewPage } from '@/features/catalog/CatalogOverviewPage'
import { SearchPage } from '@/features/catalog/SearchPage'
import { BudgetPage } from '@/features/finops/BudgetPage'
import { FinOpsPage } from '@/features/finops/FinOpsPage'
import { DatasetFreshnessPage } from '@/features/freshness/DatasetFreshnessPage'
import { FreshnessPage } from '@/features/freshness/FreshnessPage'
import { OrphansPage } from '@/features/lineage/OrphansPage'
import { BucketsPage } from '@/features/storage/BucketsPage'
import { WastePage } from '@/features/storage/WastePage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<CatalogOverviewPage />} />
          <Route path="datasets/:datasetId" element={<CatalogDatasetPage />} />
          <Route path="freshness" element={<FreshnessPage />} />
          <Route path="freshness/:datasetId" element={<DatasetFreshnessPage />} />
          <Route path="orphans" element={<OrphansPage />} />
          <Route path="finops" element={<FinOpsPage />} />
          <Route path="finops/budget" element={<BudgetPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="storage" element={<BucketsPage />} />
          <Route path="storage/waste" element={<WastePage />} />
          <Route element={<RequireAdmin />}>
            <Route path="admin" element={<AdminPage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  )
}
