/**
 * Supplier Detail Page
 * View and edit supplier details with document management
 *
 * Copy to: bei-tasks/src/app/dashboard/procurement/suppliers/[id]/page.tsx
 */

'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import {
  ArrowLeft,
  Building2,
  Phone,
  Mail,
  MapPin,
  FileCheck,
  FileX,
  Star,
  Edit,
  AlertTriangle,
  Calendar,
  DollarSign,
  Package,
  Receipt,
  Upload,
} from 'lucide-react';
import { useSupplier, useSupplierPurchaseOrders, useSupplierInvoices, useUpdateSupplier } from '@/hooks/use-procurement';
import { format } from 'date-fns';

// Currency formatter
const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: 'PHP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

// Date formatter
const formatDate = (date: string | null) => {
  if (!date) return '—';
  return format(new Date(date), 'MMM d, yyyy');
};

// Status badge colors
const statusColors: Record<string, string> = {
  Active: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  Inactive: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
  Blacklisted: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

const poStatusColors: Record<string, string> = {
  Draft: 'bg-gray-100 text-gray-800',
  'Pending Mae': 'bg-yellow-100 text-yellow-800',
  'Pending Butch': 'bg-orange-100 text-orange-800',
  Approved: 'bg-green-100 text-green-800',
  Rejected: 'bg-red-100 text-red-800',
  Closed: 'bg-blue-100 text-blue-800',
};

// Document status component
function DocStatus({ hasDoc, label, expiryDate }: { hasDoc: boolean; label: string; expiryDate?: string }) {
  const isExpired = expiryDate && new Date(expiryDate) < new Date();
  const isExpiringSoon = expiryDate && !isExpired &&
    new Date(expiryDate) < new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);

  return (
    <div className="flex items-center justify-between p-3 rounded-lg border">
      <div className="flex items-center gap-2">
        {hasDoc ? (
          <FileCheck className={`h-5 w-5 ${isExpired ? 'text-red-500' : isExpiringSoon ? 'text-yellow-500' : 'text-green-600'}`} />
        ) : (
          <FileX className="h-5 w-5 text-red-500" />
        )}
        <span className="font-medium">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        {hasDoc ? (
          <>
            {expiryDate && (
              <span className={`text-sm ${isExpired ? 'text-red-500' : isExpiringSoon ? 'text-yellow-500' : 'text-muted-foreground'}`}>
                {isExpired ? 'Expired' : `Expires ${formatDate(expiryDate)}`}
              </span>
            )}
            <Button variant="ghost" size="sm">
              <Upload className="h-4 w-4 mr-1" />
              Replace
            </Button>
          </>
        ) : (
          <Button variant="outline" size="sm">
            <Upload className="h-4 w-4 mr-1" />
            Upload
          </Button>
        )}
      </div>
    </div>
  );
}

export default function SupplierDetailPage() {
  const params = useParams();
  const router = useRouter();
  const supplierId = params.id as string;

  const [blacklistDialogOpen, setBlacklistDialogOpen] = useState(false);

  const { data: supplier, isLoading } = useSupplier(supplierId);
  const { data: purchaseOrders } = useSupplierPurchaseOrders(supplierId);
  const { data: invoices } = useSupplierInvoices(supplierId);
  const updateSupplier = useUpdateSupplier();

  const handleBlacklist = async () => {
    try {
      await updateSupplier.mutateAsync({
        id: supplierId,
        data: { status: 'Blacklisted' }
      });
      toast.success('Supplier has been blacklisted');
      setBlacklistDialogOpen(false);
    } catch {
      toast.error('Failed to blacklist supplier');
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 p-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-6 md:grid-cols-3">
          <Skeleton className="h-[200px]" />
          <Skeleton className="h-[200px]" />
          <Skeleton className="h-[200px]" />
        </div>
      </div>
    );
  }

  if (!supplier) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <Building2 className="h-16 w-16 text-muted-foreground" />
        <h2 className="text-xl font-semibold">Supplier not found</h2>
        <Link href="/dashboard/procurement/suppliers">
          <Button variant="outline">Back to Suppliers</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/procurement/suppliers">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight">{supplier.supplier_name}</h1>
              <Badge className={statusColors[supplier.status]}>{supplier.status}</Badge>
              {supplier.is_new_supplier && (
                <Badge variant="outline" className="border-blue-500 text-blue-500">New</Badge>
              )}
            </div>
            <p className="text-muted-foreground">{supplier.supplier_code}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Link href={`/dashboard/procurement/suppliers/${supplierId}/edit`}>
            <Button variant="outline">
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </Button>
          </Link>
          {supplier.status !== 'Blacklisted' && (
            <Button variant="destructive" onClick={() => setBlacklistDialogOpen(true)}>
              <AlertTriangle className="mr-2 h-4 w-4" />
              Blacklist
            </Button>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                <Package className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{supplier.total_orders}</p>
                <p className="text-sm text-muted-foreground">Total Orders</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600">
                <DollarSign className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{formatCurrency(supplier.total_amount)}</p>
                <p className="text-sm text-muted-foreground">Total Amount</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-100 text-yellow-600">
                <Receipt className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{formatCurrency(supplier.outstanding_amount || 0)}</p>
                <p className="text-sm text-muted-foreground">Outstanding</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600">
                <Star className="h-5 w-5 fill-current" />
              </div>
              <div>
                <p className="text-2xl font-bold">{supplier.rating?.toFixed(1) || '—'}</p>
                <p className="text-sm text-muted-foreground">Rating</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="details" className="space-y-4">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="orders">Purchase Orders</TabsTrigger>
          <TabsTrigger value="invoices">Invoices</TabsTrigger>
        </TabsList>

        <TabsContent value="details" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Contact Information */}
            <Card>
              <CardHeader>
                <CardTitle>Contact Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {supplier.email && (
                  <div className="flex items-center gap-3">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <a href={`mailto:${supplier.email}`} className="text-primary hover:underline">
                      {supplier.email}
                    </a>
                  </div>
                )}
                {supplier.phone && (
                  <div className="flex items-center gap-3">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span>{supplier.phone}</span>
                  </div>
                )}
                {supplier.address && (
                  <div className="flex items-start gap-3">
                    <MapPin className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <span>{supplier.address}</span>
                  </div>
                )}
                {supplier.contact_person && (
                  <div className="pt-2 border-t">
                    <p className="text-sm text-muted-foreground">Contact Person</p>
                    <p className="font-medium">{supplier.contact_person}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Business Information */}
            <Card>
              <CardHeader>
                <CardTitle>Business Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">TIN</p>
                    <p className="font-medium">{supplier.tin || '—'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">SEC Registration</p>
                    <p className="font-medium">{supplier.sec_registration_no || '—'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">VAT Status</p>
                    <p className="font-medium">{supplier.vat_status || '—'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">EWT Setting</p>
                    <p className="font-medium">
                      {supplier.ewt_applicable ? (
                        supplier.ewt_exempt ? 'Exempt' : 'Applicable'
                      ) : 'Not Applicable'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Payment Terms</p>
                    <p className="font-medium">{supplier.payment_terms || 'Not set'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Credit Limit</p>
                    <p className="font-medium">{supplier.credit_limit ? formatCurrency(supplier.credit_limit) : '—'}</p>
                  </div>
                </div>
                {supplier.bank_name && (
                  <div className="pt-2 border-t">
                    <p className="text-sm text-muted-foreground">Bank Details</p>
                    <p className="font-medium">{supplier.bank_name}</p>
                    <p className="text-sm">{supplier.bank_account_no}</p>
                    {supplier.bank_account_name && (
                      <p className="text-sm text-muted-foreground">({supplier.bank_account_name})</p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="documents" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Required Documents</CardTitle>
              <CardDescription>
                BIR 2307 and SEC Certificate are required for all suppliers
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <DocStatus
                hasDoc={!!supplier.bir_2307}
                label="BIR 2307 (Certificate of Creditable Tax Withheld)"
                expiryDate={supplier.bir_2307_expiry}
              />
              <DocStatus
                hasDoc={!!supplier.sec_certificate}
                label="SEC Certificate of Registration"
                expiryDate={supplier.sec_certificate_expiry}
              />
              <DocStatus
                hasDoc={!!supplier.mayors_permit}
                label="Mayor's Business Permit"
                expiryDate={supplier.mayors_permit_expiry}
              />
              <DocStatus
                hasDoc={!!supplier.dti_registration}
                label="DTI Registration (if sole proprietor)"
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="orders" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Purchase Orders</CardTitle>
              <CardDescription>
                Recent purchase orders from this supplier
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>PO Number</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {purchaseOrders?.data?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                        No purchase orders yet
                      </TableCell>
                    </TableRow>
                  ) : (
                    purchaseOrders?.data?.map((po: any) => (
                      <TableRow key={po.name}>
                        <TableCell>
                          <Link
                            href={`/dashboard/procurement/purchase-orders/${po.name}`}
                            className="font-medium text-primary hover:underline"
                          >
                            {po.po_number}
                          </Link>
                        </TableCell>
                        <TableCell>{formatDate(po.po_date)}</TableCell>
                        <TableCell>
                          <Badge className={poStatusColors[po.status] || 'bg-gray-100'}>
                            {po.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {formatCurrency(po.grand_total)}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="invoices" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Invoices</CardTitle>
              <CardDescription>
                Invoice history with this supplier
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice No</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Due Date</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoices?.data?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        No invoices yet
                      </TableCell>
                    </TableRow>
                  ) : (
                    invoices?.data?.map((invoice: any) => (
                      <TableRow key={invoice.name}>
                        <TableCell>
                          <Link
                            href={`/dashboard/procurement/invoices/${invoice.name}`}
                            className="font-medium text-primary hover:underline"
                          >
                            {invoice.invoice_number}
                          </Link>
                        </TableCell>
                        <TableCell>{formatDate(invoice.invoice_date)}</TableCell>
                        <TableCell>{formatDate(invoice.due_date)}</TableCell>
                        <TableCell>
                          <Badge variant={invoice.payment_status === 'Paid' ? 'default' : 'secondary'}>
                            {invoice.payment_status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {formatCurrency(invoice.grand_total)}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Blacklist Dialog */}
      <Dialog open={blacklistDialogOpen} onOpenChange={setBlacklistDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Blacklist Supplier</DialogTitle>
            <DialogDescription>
              Are you sure you want to blacklist {supplier.supplier_name}? This will prevent creating new purchase orders with this supplier.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBlacklistDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleBlacklist} disabled={updateSupplier.isPending}>
              {updateSupplier.isPending ? 'Blacklisting...' : 'Blacklist Supplier'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
