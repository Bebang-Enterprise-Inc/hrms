'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { BarChart3, ArrowRight } from 'lucide-react';

const REPORT_LINKS = [
  { title: 'Purchase Orders', href: '/dashboard/procurement/purchase-orders' },
  { title: 'Goods Receipts', href: '/dashboard/procurement/goods-receipts' },
  { title: 'Invoices', href: '/dashboard/procurement/invoices' },
  { title: 'Payments', href: '/dashboard/procurement/payments' },
];

export default function ProcurementReportsPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <BarChart3 className="h-6 w-6" />
        <h1 className="text-2xl font-semibold">Procurement Reports</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Report Entry Points</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {REPORT_LINKS.map((item) => (
            <Button key={item.href} asChild variant="outline" className="justify-between">
              <Link href={item.href}>
                {item.title}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

