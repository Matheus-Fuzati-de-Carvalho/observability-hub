import { AccessRequestAnalyticsSection } from '@/features/admin/AccessRequestAnalyticsSection'
import { FavoritesAnalyticsSection } from '@/features/admin/FavoritesAnalyticsSection'
import { LoginAnalyticsSection } from '@/features/admin/LoginAnalyticsSection'
import { NavigationAnalyticsSection } from '@/features/admin/NavigationAnalyticsSection'
import { PiiScanActivitySection } from '@/features/admin/PiiScanActivitySection'
import { ProfilingActivitySection } from '@/features/admin/ProfilingActivitySection'

export function AdminUsageTab() {
  return (
    <div className="flex flex-col gap-8">
      <LoginAnalyticsSection />
      <FavoritesAnalyticsSection />
      <ProfilingActivitySection />
      <AccessRequestAnalyticsSection />
      <NavigationAnalyticsSection />
      <PiiScanActivitySection />
    </div>
  )
}
