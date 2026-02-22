/**
 * Procurement Executive Dashboard
 * "Out of this world" KPI dashboard with real-time metrics
 *
 * Copy to: bei-tasks/src/app/dashboard/procurement/page.tsx
 */

'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
  Area,
  AreaChart,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Clock,
  DollarSign,
  FileText,
  Users,
  Package,
  CreditCard,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';
import {
  useDashboardKPIs,
  useOutstandingBySupplier,
  useAgingAnalysis,
  useMonthlyPOTrend,
  usePaymentSchedule,
  usePendingPOApprovals,
  usePendingPaymentApprovals,\n  usePurchaseRequisitionStats,
} from '@/hooks/use-procurement';

// Currency formatter
const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: 'PHP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatCompact = (value: number) => {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(0)}K`;
  }
  return value.toString();
};

// Colors for charts
const COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#8b5cf6'];
const AGING_COLORS = {
  current: '#22c55e',
  days_1_30: '#84cc16',
  days_31_60: '#eab308',
  days_61_90: '#f97316',
  over_90: '#ef4444',
};

// KPI Card Component
function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
  variant = 'default',
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: any;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  variant?: 'default' | 'warning' | 'danger' | 'success';
}) {
  const bgColors = {
    default: 'bg-card',
    warning: 'bg-yellow-500/10 border-yellow-500/20',
    danger: 'bg-red-500/10 border-red-500/20',
    success: 'bg-green-500/10 border-green-500/20',
  };

  const iconColors = {
    default: 'text-primary',
    warning: 'text-yellow-500',
    danger: 'text-red-500',
    success: 'text-green-500',
  };

  return (
    <Card className={`${bgColors[variant]} transition-all hover:shadow-lg`}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold tracking-tight">{value}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground">{subtitle}</p>
            )}
            {trend && trendValue && (
              <div className="flex items-center gap-1 text-xs">
                {trend === 'up' && <TrendingUp className="h-3 w-3 text-green-500" />}
                {trend === 'down' && <TrendingDown className="h-3 w-3 text-red-500" />}
                <span className={trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : ''}>
                  {trendValue}
                </span>
              </div>
            )}
          </div>
          <div className={`p-3 rounded-xl bg-background/50 ${iconColors[variant]}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Pending Approvals Widget
function PendingApprovalsWidget() {
  const { data: poApprovals } = usePendingPOApprovals();
  const { data: paymentApprovals } = usePendingPaymentApprovals();
  const { data: prStats } = usePurchaseRequisitionStats();

  const totalPending = (poApprovals?.total_pending ?? 0) + (paymentApprovals?.total_pending ?? 0) + (prStats?.pending_approval ?? 0);

  return (
    <Card className="col-span-full lg:col-span-2">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div>
          <CardTitle className="text-lg">Pending Approvals</CardTitle>
          <CardDescription>Items requiring your attention</CardDescription>
        </div>
        <Badge variant={totalPending > 0 ? 'destructive' : 'secondary'}>
          {totalPending} pending
        </Badge>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="pr" className="w-full">
          <TabsList className="w-full">
            <TabsTrigger value="pr" className="flex-1">
              PRs ({prStats?.pending_approval ?? 0})
            </TabsTrigger>
            <TabsTrigger value="po" className="flex-1">
              POs ({poApprovals?.total_pending ?? 0})
            </TabsTrigger>
            <TabsTrigger value="payment" className="flex-1">
              Payments ({paymentApprovals?.total_pending ?? 0})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pr" className="mt-4">
            <ScrollArea className="h-[200px]">
              {prStats?.pending_approval && prStats.pending_approval > 0 ? (
                <div className="flex flex-col items-center justify-center h-full space-y-4 pt-10">
                  <p className="text-sm text-muted-foreground">You have {prStats.pending_approval} Purchase Requisitions waiting for approval.</p>
                  <Link href="/dashboard/procurement/purchase-requisitions?status=Pending+Approval">
                    <Button variant="outline" size="sm">Review PRs</Button>
                  </Link>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center p-4 pt-10">
                  <p className="text-sm text-muted-foreground">No PRs pending approval</p>
                </div>
              )}
            </ScrollArea>
          </TabsContent>

          <TabsContent value="po" className="mt-4">
            <ScrollArea className="h-[200px]">
              {poApprovals?.pending_mae?.map((po) => (
                <div key={po.name} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div>
                    <p className="font-medium">{po.po_no}</p>
                    <p className="text-sm text-muted-foreground">{po.supplier_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">{formatCurrency(po.grand_total)}</p>
                    <Badge variant="outline" className="text-xs">
                      {po.requires_dual_approval ? '>500K' : 'Mae'}
                    </Badge>
                  </div>
                </div>
              ))}
              {poApprovals?.pending_butch?.map((po) => (
                <div key={po.name} className="flex items-center justify-between py-2 border-b last:border-0 bg-orange-50 dark:bg-orange-950/20 -mx-4 px-4">
                  <div>
                    <p className="font-medium">{po.po_no}</p>
                    <p className="text-sm text-muted-foreground">{po.supplier_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">{formatCurrency(po.grand_total)}</p>
                    <Badge variant="secondary" className="text-xs bg-orange-500 text-white">
                      CFO (Butch)
                    </Badge>
                  </div>
                </div>
              ))}
              {!poApprovals?.total_pending && (
                <div className="flex flex-col items-center justify-center h-[150px] text-muted-foreground">
                  <CheckCircle2 className="h-8 w-8 mb-2 text-green-500" />
                  <p>All POs approved!</p>
                </div>
              )}
            </ScrollArea>
          </TabsContent>

          <TabsContent value="payment" className="mt-4">
            <ScrollArea className="h-[200px]">
              {Object.entries(paymentApprovals ?? {}).map(([level, requests]) => {
                if (level === 'total_pending' || !Array.isArray(requests)) return null;
                return requests.map((req: any) => (
                  <div key={req.name} className="flex items-center justify-between py-2 border-b last:border-0">
                    <div>
                      <p className="font-medium">{req.payment_request_no}</p>
                      <p className="text-sm text-muted-foreground">{req.supplier_name}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold">{formatCurrency(req.payment_amount)}</p>
                      <Badge variant="outline" className="text-xs capitalize">
                        {level}
                      </Badge>
                    </div>
                  </div>
                ));
              })}
              {!paymentApprovals?.total_pending && (
                <div className="flex flex-col items-center justify-center h-[150px] text-muted-foreground">
                  <CheckCircle2 className="h-8 w-8 mb-2 text-green-500" />
                  <p>All payments approved!</p>
                </div>
              )}
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

// Aging Chart
function AgingChart() {
  const { data: aging, isLoading } = useAgingAnalysis();

  if (isLoading) {
    return <Skeleton className="h-[300px] w-full" />;
  }

  const chartData = [
    { name: 'Current', value: aging?.current ?? 0, color: AGING_COLORS.current },
    { name: '1-30 Days', value: aging?.days_1_30 ?? 0, color: AGING_COLORS.days_1_30 },
    { name: '31-60 Days', value: aging?.days_31_60 ?? 0, color: AGING_COLORS.days_31_60 },
    { name: '61-90 Days', value: aging?.days_61_90 ?? 0, color: AGING_COLORS.days_61_90 },
    { name: '90+ Days', value: aging?.over_90 ?? 0, color: AGING_COLORS.over_90 },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">AP Aging Analysis</CardTitle>
        <CardDescription>Outstanding payables by age</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => formatCurrency(value)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 text-center">
          <p className="text-2xl font-bold">{formatCurrency(aging?.total ?? 0)}</p>
          <p className="text-sm text-muted-foreground">Total Outstanding</p>
        </div>
      </CardContent>
    </Card>
  );
}

// PO Trend Chart
function POTrendChart() {
  const { data: trend, isLoading } = useMonthlyPOTrend(6);

  if (isLoading) {
    return <Skeleton className="h-[300px] w-full" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Monthly PO Trend</CardTitle>
        <CardDescription>Purchase orders over the last 6 months</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v) => formatCompact(v)} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number, name: string) => [
                  name === 'po_value' ? formatCurrency(value) : value,
                  name === 'po_value' ? 'Value' : 'Count',
                ]}
              />
              <Area
                type="monotone"
                dataKey="po_value"
                stroke="#8b5cf6"
                fill="#8b5cf6"
                fillOpacity={0.2}
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// Outstanding by Supplier Chart
function OutstandingBySupplierChart() {
  const { data: suppliers, isLoading } = useOutstandingBySupplier();

  if (isLoading) {
    return <Skeleton className="h-[300px] w-full" />;
  }

  const top5 = suppliers?.slice(0, 5) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Outstanding by Supplier</CardTitle>
        <CardDescription>Top 5 suppliers with highest payables</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={top5} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis type="number" tickFormatter={(v) => formatCompact(v)} tick={{ fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="supplier_name"
                width={120}
                tick={{ fontSize: 11 }}
              />
              <Tooltip formatter={(value: number) => formatCurrency(value)} />
              <Bar dataKey="outstanding" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// Payment Schedule Widget
function PaymentScheduleWidget() {
  const { data: schedule, isLoading } = usePaymentSchedule();

  if (isLoading) {
    return <Skeleton className="h-[300px] w-full" />;
  }

  return (
    <Card className="col-span-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-lg">Upcoming Payments</CardTitle>
          <CardDescription>Invoices due in the next 30 days</CardDescription>
        </div>
        <Link href="/dashboard/procurement/invoices?filter=due">
          <Button variant="outline" size="sm">
            View All <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {schedule?.slice(0, 5).map((item: any) => (
            <div
              key={item.invoice}
              className={`flex items-center justify-between p-3 rounded-lg border ${
                item.days_until_due < 0
                  ? 'bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800'
                  : item.days_until_due <= 7
                  ? 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-800'
                  : 'bg-muted/50'
              }`}
            >
              <div className="flex items-center gap-4">
                <div
                  className={`p-2 rounded-full ${
                    item.days_until_due < 0
                      ? 'bg-red-500'
                      : item.days_until_due <= 7
                      ? 'bg-yellow-500'
                      : 'bg-green-500'
                  }`}
                >
                  <CreditCard className="h-4 w-4 text-white" />
                </div>
                <div>
                  <p className="font-medium">{item.invoice_no}</p>
                  <p className="text-sm text-muted-foreground">{item.supplier_name}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-semibold">{formatCurrency(item.balance_due)}</p>
                <p className="text-xs text-muted-foreground">
                  {item.days_until_due < 0 ? (
                    <span className="text-red-500 font-medium">
                      {Math.abs(item.days_until_due)} days overdue
                    </span>
                  ) : item.days_until_due === 0 ? (
                    <span className="text-yellow-500 font-medium">Due today</span>
                  ) : (
                    `Due in ${item.days_until_due} days`
                  )}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// Main Dashboard Component
export default function ProcurementDashboard() {
  const { data: kpis, isLoading, refetch } = useDashboardKPIs();

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Procurement Dashboard</h1>
          <p className="text-muted-foreground">Real-time overview of procurement operations</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          <>
            <Skeleton className="h-[140px]" />
            <Skeleton className="h-[140px]" />
            <Skeleton className="h-[140px]" />
            <Skeleton className="h-[140px]" />
          </>
        ) : (
          <>
            <KPICard
              title="Total Outstanding"
              value={formatCurrency(kpis?.total_outstanding ?? 0)}
              subtitle="Unpaid supplier invoices"
              icon={DollarSign}
              variant={kpis?.total_outstanding > 5000000 ? 'warning' : 'default'}
            />
            <KPICard
              title="Overdue Amount"
              value={formatCurrency(kpis?.overdue_amount ?? 0)}
              subtitle="Past due date"
              icon={AlertTriangle}
              variant={kpis?.overdue_amount > 0 ? 'danger' : 'success'}
            />
            <KPICard
              title="MTD PO Value"
              value={formatCurrency(kpis?.mtd_po_value ?? 0)}
              subtitle={`${kpis?.mtd_po_count ?? 0} orders this month`}
              icon={FileText}
            />
            <KPICard
              title="Avg Payment Days"
              value={`${kpis?.avg_payment_days?.toFixed(1) ?? 0} days`}
              subtitle="Last 30 days"
              icon={Clock}
              variant={kpis?.avg_payment_days > 30 ? 'warning' : 'success'}
            />
          </>
        )}
      </div>

      {/* Second Row - Approvals and Aging */}
      <div className="grid gap-4 lg:grid-cols-4">
        <PendingApprovalsWidget />
        <AgingChart />
      </div>

      {/* Third Row - Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        <POTrendChart />
        <OutstandingBySupplierChart />
      </div>

      {/* Fourth Row - Payment Schedule */}
      <PaymentScheduleWidget />

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Link href="/dashboard/procurement/suppliers">
              <Button variant="outline">
                <Users className="mr-2 h-4 w-4" />
                Manage Suppliers
              </Button>
            </Link>
            <Link href="/dashboard/procurement/purchase-orders/new">
              <Button variant="outline">
                <FileText className="mr-2 h-4 w-4" />
                New Purchase Order
              </Button>
            </Link>
            <Link href="/dashboard/procurement/goods-receipt/new">
              <Button variant="outline">
                <Package className="mr-2 h-4 w-4" />
                Record Goods Receipt
              </Button>
            </Link>
            <Link href="/dashboard/procurement/invoices/new">
              <Button variant="outline">
                <CreditCard className="mr-2 h-4 w-4" />
                Enter Invoice
              </Button>
            </Link>
            <Link href="/dashboard/procurement/payments/new">
              <Button>
                <DollarSign className="mr-2 h-4 w-4" />
                Request Payment
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
