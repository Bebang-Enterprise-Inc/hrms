"use client";

import { ComingSoonAnalyticsShell } from "@/components/analytics/coming-soon-shell";

export default function Page() {
  return (
    <ComingSoonAnalyticsShell
      title="Product Analytics"
      description="SKU-level velocity, category mix, and waste intelligence to drive assortment decisions across all 45+ stores."
      plannedMetrics={[
    "Top 20 / Bottom 20 SKUs by velocity (daily/weekly/monthly)",
    "Category mix vs targets by store-format",
    "Waste / spoilage rate per SKU per store",
    "New-product launch performance (first 30 days)",
    "Mix shift by store-cluster and by daypart",
      ]}
      roadmapSprint="S18X+"
    />
  );
}
