"use client";
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useSOAList } from '@/hooks/use-procurement';

export default function SOAListPage() {
  const { data: soas, isLoading } = useSOAList();
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold">Statements of Account</h1>
      <Card>
        <CardHeader><CardTitle>SOA List</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? <p>Loading...</p> : <pre>{JSON.stringify(soas?.data?.slice(0,2), null, 2)}</pre>}
        </CardContent>
      </Card>
    </div>
  );
}