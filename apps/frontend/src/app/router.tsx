import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/app/layout'
import { AuthCallbackPage } from '@/features/auth/AuthCallbackPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CatalogDatasetPage } from '@/features/catalog/CatalogDatasetPage'
import { CatalogOverviewPage } from '@/features/catalog/CatalogOverviewPage'
import { SearchPage } from '@/features/catalog/SearchPage'
import { FreshnessPage } from '@/features/freshness/FreshnessPage'

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
          <Route path="search" element={<SearchPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
