import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/app/layout'
import { CatalogDatasetPage } from '@/features/catalog/CatalogDatasetPage'
import { CatalogOverviewPage } from '@/features/catalog/CatalogOverviewPage'
import { SearchPage } from '@/features/catalog/SearchPage'
import { FreshnessPage } from '@/features/freshness/FreshnessPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<CatalogOverviewPage />} />
        <Route path="datasets/:datasetId" element={<CatalogDatasetPage />} />
        <Route path="freshness" element={<FreshnessPage />} />
        <Route path="search" element={<SearchPage />} />
      </Route>
    </Routes>
  )
}
