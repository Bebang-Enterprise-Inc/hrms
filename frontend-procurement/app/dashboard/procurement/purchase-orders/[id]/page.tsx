/**
 * Purchase Order Detail Page
 * View PO with dual approval workflow (Mae + Butch for >500K)
 * Shows items, approval timeline, linked GRs and Invoices
 *
 * Copy to: bei-tasks/src/app/dashboard/procurement/purchase-orders/[id]/page.tsx
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
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import {
  ArrowLeft,
  Building2,
  Calendar,
  FileText,
  Package,
  Receipt,
  Truck,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Edit,
  Send,
  User,
  FileCheck,
  FileX,
} from 'lucide-react';
import { format } from 'date-fns';
import {
  usePurchaseOrder,
  usePurchaseOrderItems,
  usePurchaseOrderGRs,
  usePurchaseOrderInvoices,
  usePurchaseOrderHistory,
  useSubmitPOForApproval,
  useApprovePO,
  useRejectPO,
} from '@/hooks/use-procurement';

// Currency formatter
const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: 'PHP',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

// Date formatter
const formatDate = (date: string | null) => {
  if (!date) return '-';
  return format(new Date(date), 'MMM d, yyyy');
};

const formatDateTime = (date: string | null) => {
  if (!date) return '-';
  return format(new Date(date), 'MMM d, yyyy h:mm a');
};

// Status badge colors
const statusColors: Record<string, string> = {
  Draft: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
  'Pending Mae Approval': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  'Pending Butch Approval': 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  Approved: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  'Sent to Supplier': 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  'Partially Received': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  'Fully Received': 'bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200',
  Cancelled: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  Rejected: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

// Dual Approval Status Component
function DualApprovalStatus({
  requiresDual,
  maeApproval,
  butchApproval,
  maeDate,
  butchDate,
  maeComment,
  butchComment,
}: {
  requiresDual: boolean;
  maeApproval: string;
  butchApproval: string;
  maeDate?: string;
  butchDate?: string;
  maeComment?: string;
  butchComment?: string;
}) {
  const getStatusIcon = (status: string) => {
    if (status === 'Approved') return <CheckCircle className="h-5 w-5 text-green-600" />;
    if (status === 'Rejected') return <XCircle className="h-5 w-5 text-red-600" />;
    return <Clock className="h-5 w-5 text-gray-400" />;
  };

  const getStatusColor = (status: string) => {
    if (status === 'Approved') return 'border-green-500 bg-green-50 dark:bg-green-950/20';
    if (status === 'Rejected') return 'border-red-500 bg-red-50 dark:bg-red-950/20';
    return 'border-gray-300 bg-gray-50 dark:bg-gray-900/20';
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CheckCircle className="h-5 w-5" />
          Approval Status
          {requiresDual && (
            <Badge variant="outline" className="ml-2 border-orange-500 text-orange-600">
              Dual Approval Required (&gt;500K)
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          {requiresDual
            ? 'This PO requires both Mae and Butch (CFO) approval'
            : 'This PO requires Mae approval only'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className={`grid gap-4 ${requiresDual ? 'md:grid-cols-2' : 'md:grid-cols-1'}`}>
          {/* Mae Approval */}
          <div className={`p-4 rounded-lg border-2 ${getStatusColor(maeApproval)}`}>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                {getStatusIcon(maeApproval)}
                <div>
                  <p className="font-semibold">Mae Karazi</p>
                  <p className="text-sm text-muted-foreground">Procurement Head</p>
                </div>
              </div>
              <Badge
                className={
                  maeApproval === 'Approved'
                    ? 'bg-green-600'
                    : maeApproval === 'Rejected'
                    ? 'bg-red-600'
                    : 'bg-gray-500'
                }
              >
                {maeApproval || 'Pending'}
              </Badge>
            </div>
            {maeDate && (
              <p className="text-xs text-muted-foreground mt-2">
                {formatDateTime(maeDate)}
              </p>
            )}
            {maeComment && (
              <p className="text-sm mt-2 p-2 bg-white/50 dark:bg-black/20 rounded">
                "{maeComment}"
              </p>
            )}
          </div>

          {/* Butch Approval (only for >500K) */}
          {requiresDual && (
            <div className={`p-4 rounded-lg border-2 ${getStatusColor(butchApproval)}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  {getStatusIcon(butchApproval)}
                  <div>
                    <p className="font-semibold">Butch Formoso</p>
                    <p className="text-sm text-muted-foreground">CFO</p>
                  </div>
                </div>
                <Badge
                  className={
                    butchApproval === 'Approved'
                      ? 'bg-green-600'
                      : butchApproval === 'Rejected'
                      ? 'bg-red-600'
                      : 'bg-gray-500'
                  }
                >
                  {butchApproval || 'Pending'}
                </Badge>
              </div>
              {butchDate && (
                <p className="text-xs text-muted-foreground mt-2">
                  {formatDateTime(butchDate)}
                </p>
              )}
              {butchComment && (
                <p className="text-sm mt-2 p-2 bg-white/50 dark:bg-black/20 rounded">
                  "{butchComment}"
                </p>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// Approval Timeline Component
function ApprovalTimeline({ history }: { history: any[] }) {
  if (!history || history.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p>No activity yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {history.map((event, index) => (
        <div key={index} className="flex gap-4">
          <div className="flex flex-col items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center ${
                event.action === 'Approved'
                  ? 'bg-green-100 text-green-600'
                  : event.action === 'Rejected'
                  ? 'bg-red-100 text-red-600'
                  : event.action === 'Submitted'
                  ? 'bg-blue-100 text-blue-600'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              {event.action === 'Approved' ? (
                <CheckCircle className="h-4 w-4" />
              ) : event.action === 'Rejected' ? (
                <XCircle className="h-4 w-4" />
              ) : event.action === 'Submitted' ? (
                <Send className="h-4 w-4" />
              ) : (
                <User className="h-4 w-4" />
              )}
            </div>
            {index < history.length - 1 && (
              <div className="w-0.5 h-full bg-gray-200 dark:bg-gray-700 mt-1" />
            )}
          </div>
          <div className="flex-1 pb-4">
            <div className="flex items-center justify-between">
              <p className="font-medium">{event.action}</p>
              <span className="text-xs text-muted-foreground">
                {formatDateTime(event.timestamp)}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{event.user}</p>
            {event.comment && (
              <p className="text-sm mt-1 p-2 bg-muted rounded">{event.comment}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// Supplier Document Status
function SupplierDocStatus({ hasBir, hasSec }: { hasBir: boolean; hasSec: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`flex items-center gap-1 text-xs ${hasBir ? 'text-green-600' : 'text-red-500'}`}>
        {hasBir ? <FileCheck className="h-3 w-3" /> : <FileX className="h-3 w-3" />}
        BIR 2307
      </div>
      <div className={`flex items-center gap-1 text-xs ${hasSec ? 'text-green-600' : 'text-red-500'}`}>
        {hasSec ? <FileCheck className="h-3 w-3" /> : <FileX className="h-3 w-3" />}
        SEC
      </div>
    </div>
  );
}

export default function PurchaseOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const poId = params.id as string;

  const [approvalDialogOpen, setApprovalDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [exceptionDialogOpen, setExceptionDialogOpen] = useState(false);
  const [exceptionReason, setExceptionReason] = useState('');
  const [exceptionType, setExceptionType] = useState('Service PO');

  const requestExceptionMutation = useMutation({
    mutationFn: (data: { purchase_order: string; reason: string; exception_type: string }) =>
      fetchAPI('/exceptions/request', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-order', poId] });
      toast.success('Exception requested successfully');
      setExceptionDialogOpen(false);
      setExceptionReason('');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to request exception');
    },
  });

  const handleRequestException = () => {
    if (!exceptionReason.trim()) return;
    requestExceptionMutation.mutate({
      purchase_order: poId as string,
      reason: exceptionReason,
      exception_type: exceptionType,
    });
  };

  const [rejectReason, setRejectReason] = useState('');

  const { data: po, isLoading } = usePurchaseOrder(poId);
  const { data: items } = usePurchaseOrderItems(poId);
  const { data: goodsReceipts } = usePurchaseOrderGRs(poId);
  const { data: invoices } = usePurchaseOrderInvoices(poId);
  const { data: history } = usePurchaseOrderHistory(poId);

  const submitMutation = useSubmitPOForApproval();
  const approveMutation = useApprovePO();
  const rejectMutation = useRejectPO();

  const handleSubmitForApproval = async () => {
    try {
      await submitMutation.mutateAsync(poId);
    } catch (error: any) {
      toast.error(error.message || 'Failed to submit PO');
    }
  };

  const handleApprove = async () => {
    if (!po) return;
    const level = po.status === 'Pending Mae Approval' ? 'mae' : 'butch';
    try {
      await approveMutation.mutateAsync({ name: poId, level, comment });
      setComment('');
      setApprovalDialogOpen(false);
    } catch (error: any) {
      toast.error(error.message || 'Failed to approve PO');
    }
  };

  const handleReject = async () => {
    if (!po) return;
    const rejector = po.status === 'Pending Mae Approval' ? 'mae' : 'butch';
    try {
      await rejectMutation.mutateAsync({ name: poId, reason: rejectReason, rejector });
      setRejectReason('');
      setRejectDialogOpen(false);
    } catch (error: any) {
      toast.error(error.message || 'Failed to reject PO');
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

  if (!po) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <FileText className="h-16 w-16 text-muted-foreground" />
        <h2 className="text-xl font-semibold">Purchase Order not found</h2>
        <Link href="/dashboard/procurement/purchase-orders">
          <Button variant="outline">Back to Purchase Orders</Button>
        </Link>
      </div>
    );
  }

  const isPendingApproval =
    po.status === 'Pending Mae Approval' || po.status === 'Pending Butch Approval';
  const isDraft = po.status === 'Draft';
  const isApproved = po.status === 'Approved' || po.status === 'Sent to Supplier';
  const canEdit = isDraft;

  // Calculate totals from items
  const subtotal = items?.reduce((sum: number, item: any) => sum + (item.amount || 0), 0) || 0;
  const taxAmount = po.tax_amount || 0;
  const grandTotal = po.grand_total || subtotal + taxAmount;

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/procurement/purchase-orders">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight">{po.po_no}</h1>
              <Badge className={statusColors[po.status] || 'bg-gray-100'}>{po.status}</Badge>
              {po.requires_dual_approval && (
                <Badge variant="outline" className="border-orange-500 text-orange-600">
                  &gt;500K
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground">Created {formatDate(po.po_date)}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {canEdit && (
            <Link href={`/dashboard/procurement/purchase-orders/${poId}/edit`}>
              <Button variant="outline">
                <Edit className="mr-2 h-4 w-4" />
                Edit
              </Button>
            </Link>
          )}
                    {isApproved && (
            <Button variant="outline" onClick={() => setExceptionDialogOpen(true)}>
              <AlertTriangle className="mr-2 h-4 w-4 text-orange-500" />
              Request Exception
            </Button>
          )}
          {isDraft && (
            <Button onClick={handleSubmitForApproval} disabled={submitMutation.isPending}>
              <Send className="mr-2 h-4 w-4" />
              {submitMutation.isPending ? 'Submitting...' : 'Submit for Approval'}
            </Button>
          )}
          {isPendingApproval && (
            <>
              <Button variant="outline" onClick={() => setRejectDialogOpen(true)}>
                <XCircle className="mr-2 h-4 w-4" />
                Reject
              </Button>
              <Button onClick={() => setApprovalDialogOpen(true)}>
                <CheckCircle className="mr-2 h-4 w-4" />
                Approve
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Warning for >500K */}
      {po.requires_dual_approval && isPendingApproval && (
        <Card className="border-orange-300 bg-orange-50 dark:bg-orange-950/20">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertTriangle className="h-5 w-5 text-orange-600" />
            <div>
              <p className="font-medium text-orange-800 dark:text-orange-200">
                Dual Approval Required
              </p>
              <p className="text-sm text-orange-600 dark:text-orange-300">
                This PO is over PHP 500,000 and requires both Mae Karazi AND Butch Formoso (CFO) approval.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                <Building2 className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-muted-foreground">Supplier</p>
                <Link
                  href={`/dashboard/procurement/suppliers/${po.supplier}`}
                  className="font-medium hover:underline truncate block"
                >
                  {po.supplier_name}
                </Link>
                <SupplierDocStatus hasBir={po.supplier_has_bir} hasSec={po.supplier_has_sec} />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600">
                <Calendar className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Expected Delivery</p>
                <p className="font-medium">{formatDate(po.delivery_date)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600">
                <Package className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Items</p>
                <p className="font-medium">{items?.length || 0} line items</p>
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
                <p className="text-sm text-muted-foreground">Grand Total</p>
                <p className="text-xl font-bold">{formatCurrency(grandTotal)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Dual Approval Status */}
      <DualApprovalStatus
        requiresDual={po.requires_dual_approval}
        maeApproval={po.mae_approval}
        butchApproval={po.butch_approval}
        maeDate={po.mae_approval_date}
        butchDate={po.butch_approval_date}
        maeComment={po.mae_comment}
        butchComment={po.butch_comment}
      />

      {/* Main Content Tabs */}
      <Tabs defaultValue="items" className="space-y-4">
        <TabsList>
          <TabsTrigger value="items">Items</TabsTrigger>
          <TabsTrigger value="history">Activity Log</TabsTrigger>
          <TabsTrigger value="receipts">
            Goods Receipts
            {goodsReceipts?.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {goodsReceipts.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="invoices">
            Invoices
            {invoices?.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {invoices.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="items" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>PO Line Items</CardTitle>
              <CardDescription>Items included in this purchase order</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px]">#</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead>UOM</TableHead>
                    <TableHead className="text-right">Unit Price</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                        No items added yet
                      </TableCell>
                    </TableRow>
                  ) : (
                    items?.map((item: any, index: number) => (
                      <TableRow key={item.name || index}>
                        <TableCell className="font-medium">{index + 1}</TableCell>
                        <TableCell>
                          <span className="font-medium">{item.item_code}</span>
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate">
                          {item.description || item.item_name}
                        </TableCell>
                        <TableCell className="text-right">{item.qty}</TableCell>
                        <TableCell>{item.uom}</TableCell>
                        <TableCell className="text-right">{formatCurrency(item.rate)}</TableCell>
                        <TableCell className="text-right font-medium">
                          {formatCurrency(item.amount)}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>

              {/* Totals */}
              <div className="border-t p-4">
                <div className="flex justify-end">
                  <div className="w-[300px] space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Subtotal</span>
                      <span>{formatCurrency(subtotal)}</span>
                    </div>
                    {taxAmount > 0 && (
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Tax</span>
                        <span>{formatCurrency(taxAmount)}</span>
                      </div>
                    )}
                    <Separator />
                    <div className="flex justify-between font-bold text-lg">
                      <span>Grand Total</span>
                      <span>{formatCurrency(grandTotal)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Activity Log</CardTitle>
              <CardDescription>History of all actions on this PO</CardDescription>
            </CardHeader>
            <CardContent>
              <ApprovalTimeline history={history || []} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="receipts" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Goods Receipts</CardTitle>
                  <CardDescription>Deliveries received against this PO</CardDescription>
                </div>
                {isApproved && (
                  <Link href={`/dashboard/procurement/goods-receipts/new?po=${poId}`}>
                    <Button>
                      <Truck className="mr-2 h-4 w-4" />
                      Record Receipt
                    </Button>
                  </Link>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>GR Number</TableHead>
                    <TableHead>Receipt Date</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Ordered Qty</TableHead>
                    <TableHead className="text-right">Received Qty</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {goodsReceipts?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        <Truck className="h-8 w-8 mx-auto mb-2 opacity-50" />
                        <p>No goods receipts yet</p>
                      </TableCell>
                    </TableRow>
                  ) : (
                    goodsReceipts?.map((gr: any) => (
                      <TableRow key={gr.name}>
                        <TableCell>
                          <Link
                            href={`/dashboard/procurement/goods-receipts/${gr.name}`}
                            className="font-medium hover:underline"
                          >
                            {gr.gr_number}
                          </Link>
                        </TableCell>
                        <TableCell>{formatDate(gr.receipt_date)}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{gr.status}</Badge>
                        </TableCell>
                        <TableCell className="text-right">{gr.total_ordered_qty}</TableCell>
                        <TableCell className="text-right">{gr.total_received_qty}</TableCell>
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
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Invoices</CardTitle>
                  <CardDescription>Supplier invoices linked to this PO</CardDescription>
                </div>
                {isApproved && (
                  <Link href={`/dashboard/procurement/invoices/new?po=${poId}`}>
                    <Button>
                      <Receipt className="mr-2 h-4 w-4" />
                      Record Invoice
                    </Button>
                  </Link>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice Number</TableHead>
                    <TableHead>Supplier Invoice</TableHead>
                    <TableHead>Invoice Date</TableHead>
                    <TableHead>Due Date</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoices?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        <Receipt className="h-8 w-8 mx-auto mb-2 opacity-50" />
                        <p>No invoices yet</p>
                      </TableCell>
                    </TableRow>
                  ) : (
                    invoices?.map((invoice: any) => (
                      <TableRow key={invoice.name}>
                        <TableCell>
                          <Link
                            href={`/dashboard/procurement/invoices/${invoice.name}`}
                            className="font-medium hover:underline"
                          >
                            {invoice.invoice_number}
                          </Link>
                        </TableCell>
                        <TableCell>{invoice.supplier_invoice_no}</TableCell>
                        <TableCell>{formatDate(invoice.invoice_date)}</TableCell>
                        <TableCell>{formatDate(invoice.due_date)}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{invoice.payment_status}</Badge>
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

      {/* Approval Dialog */}
      <Dialog open={approvalDialogOpen} onOpenChange={setApprovalDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve {po.po_no}</DialogTitle>
            <DialogDescription>
              You are approving this PO as{' '}
              {po.status === 'Pending Mae Approval' ? 'Mae Karazi (Procurement Head)' : 'Butch Formoso (CFO)'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg">
              <div className="flex justify-between mb-2">
                <span className="text-muted-foreground">Supplier</span>
                <span className="font-medium">{po.supplier_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Amount</span>
                <span className="font-bold text-lg">{formatCurrency(grandTotal)}</span>
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Comment (Optional)</label>
              <Textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add any notes for this approval..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApprovalDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleApprove} disabled={approveMutation.isPending}>
              <CheckCircle className="mr-2 h-4 w-4" />
              {approveMutation.isPending ? 'Approving...' : 'Approve'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

            {/* Exception Request Dialog */}
      <Dialog open={exceptionDialogOpen} onOpenChange={setExceptionDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Request Match Exception</DialogTitle>
            <DialogDescription>
              Request an exception for the 3-way match rule for PO {po?.po_no}. This will require management approval.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Exception Type</label>
              <Select value={exceptionType} onValueChange={setExceptionType}>
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Service PO">Service PO</SelectItem>
                  <SelectItem value="Advance Payment">Advance Payment</SelectItem>
                  <SelectItem value="Emergency">Emergency</SelectItem>
                  <SelectItem value="Utility">Utility</SelectItem>
                  <SelectItem value="Other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Reason *</label>
              <Textarea
                value={exceptionReason}
                onChange={(e) => setExceptionReason(e.target.value)}
                placeholder="Explain why this PO requires a match exception..."
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExceptionDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleRequestException}
              disabled={!exceptionReason.trim() || requestExceptionMutation.isPending}
            >
              {requestExceptionMutation.isPending ? 'Submitting...' : 'Submit Request'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Reject Dialog */}
      <Dialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject {po.po_no}</DialogTitle>
            <DialogDescription>
              Please provide a reason for rejecting this purchase order.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg">
              <div className="flex justify-between mb-2">
                <span className="text-muted-foreground">Supplier</span>
                <span className="font-medium">{po.supplier_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Amount</span>
                <span className="font-bold text-lg">{formatCurrency(grandTotal)}</span>
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Rejection Reason *</label>
              <Textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Explain why this PO is being rejected..."
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={!rejectReason.trim() || rejectMutation.isPending}
            >
              <XCircle className="mr-2 h-4 w-4" />
              {rejectMutation.isPending ? 'Rejecting...' : 'Reject PO'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
