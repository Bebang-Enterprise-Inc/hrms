"use client";
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useSOA, useSendSOAMutation } from '@/hooks/use-procurement';
import { toast } from 'sonner';

export default function SOADetailPage({ params }: { params: { id: string } }) {
  const { data: soa, isLoading } = useSOA(params.id);
  const sendMutation = useSendSOAMutation();

  const handleSend = () => {
    sendMutation.mutate({ soa_name: params.id }, {
      onSuccess: () => toast.success('SOA Sent'),
      onError: (err) => toast.error(err.message)
    });
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold">SOA Detail: {params.id}</h1>
      <Card>
        <CardHeader><CardTitle>Actions</CardTitle></CardHeader>
        <CardContent>
          <Button onClick={handleSend} disabled={sendMutation.isPending || isLoading}>Send SOA to Store</Button>
          <pre className="mt-4">{JSON.stringify(soa?.data, null, 2)}</pre>
        </CardContent>
      </Card>
    </div>
  );
}