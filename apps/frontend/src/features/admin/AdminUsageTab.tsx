import { FavoritesAnalyticsSection } from '@/features/admin/FavoritesAnalyticsSection'
import { LoginAnalyticsSection } from '@/features/admin/LoginAnalyticsSection'
import { ProfilingActivitySection } from '@/features/admin/ProfilingActivitySection'

export function AdminUsageTab() {
  return (
    <div className="flex flex-col gap-8">
      <LoginAnalyticsSection />
      <FavoritesAnalyticsSection />
      <ProfilingActivitySection />
    </div>
  )
}
