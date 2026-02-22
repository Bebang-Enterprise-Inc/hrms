"use client";
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useBillingRates, useApproveRateMutation } from '@/hooks/use-procurement';
import { toast } from 'sonner';

export default function BillingRatesPage() {
  const { data: rates, isLoading } = useBillingRates();
  const approveMutation = useApproveRateMutation();

  const handleApprove = (id: string) => {
    approveMutation.mutate({ rate_id: id }, {
      onSuccess: () => toast.success('Rate approved'),
      onError: (err) => toast.error(err.message)
    });
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold">Delivery Rate Approvals</h1>
      <Card>
        <CardHeader><CardTitle>Pending Rates</CardTitle></CardHeader>
        <CardContent>
          <Button onClick={() => handleApprove('RATE-001')} disabled={approveMutation.isPending}>Approve Rate (Test)</Button>
          {isLoading ? <p>Loading...</p> : <pre className="mt-4">{JSON.stringify(rates?.data, null, 2)}</pre>}
        </CardContent>
      </Card>
    </div>
  );
}