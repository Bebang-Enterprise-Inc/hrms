"use client";
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useClearAdvanceMutation, useUndeliverableAdvanceMutation } from '@/hooks/use-procurement';
import { toast } from 'sonner';

export default function AdvancesPage() {
  const clearMutation = useClearAdvanceMutation();
  const undeliverableMutation = useUndeliverableAdvanceMutation();

  const handleClear = () => {
    clearMutation.mutate({ advance_payment: 'ADV-001', goods_receipt: 'GR-001', amount_to_clear: 100 }, {
      onSuccess: () => toast.success('Advance cleared'),
      onError: (err) => toast.error(err.message)
    });
  };

  const handleUndeliverable = () => {
    undeliverableMutation.mutate({ advance_payment: 'ADV-001', amount: 100, reason: 'Supplier bankrupt' }, {
      onSuccess: () => toast.success('Advance marked undeliverable'),
      onError: (err) => toast.error(err.message)
    });
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold">Outstanding Advances</h1>
      <Card>
        <CardHeader><CardTitle>Advance Actions</CardTitle></CardHeader>
        <CardContent className="space-x-4">
          <Button onClick={handleClear} disabled={clearMutation.isPending}>Clear Advance (Test)</Button>
          <Button variant="destructive" onClick={handleUndeliverable} disabled={undeliverableMutation.isPending}>Mark Undeliverable (Test)</Button>
        </CardContent>
      </Card>
    </div>
  );
}