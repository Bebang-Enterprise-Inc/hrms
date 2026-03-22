/**
 * New Invoice Page
 * Create an invoice against a PO/GR with 3-way match
 *
 * Copy to: bei-tasks/src/app/dashboard/procurement/invoices/new/page.tsx
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  ArrowLeft,
  Receipt,
  Search,
  FileText,
  AlertTriangle,
} from 'lucide-react';
import {
  useCreateInvoice,
  usePurchaseOrders,
  usePurchaseOrder,
  usePurchaseOrderItems,
  usePurchaseOrderGRs,
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

// Form schema
const invoiceItemSchema = z.object({
  item_code: z.string(),
  item_name: z.string(),
  qty: z.coerce.number().min(0),
  uom: z.string(),
  rate: z.coerce.number().min(0),
  amount: z.number(),
});

const invoiceSchema = z.object({
  purchase_order: z.string().min(1, 'Purchase Order is required'),
  goods_receipt: z.string().optional(),
  supplier_invoice_no: z.string().min(1, 'Supplier invoice number is required'),
  invoice_date: z.string().min(1, 'Invoice date is required'),
  due_date: z.string().min(1, 'Due date is required'),
  notes: z.string().optional(),
  items: z.array(invoiceItemSchema),
});

type InvoiceFormData = z.infer<typeof invoiceSchema>;

export default function NewInvoicePage() {
  const router = useRouter();\n  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const preSelectedPO = searchParams.get('po');

  const [searchPO, setSearchPO] = useState('');

  const createInvoice = useCreateInvoice();

  const { data: posData } = usePurchaseOrders({
    status: 'Approved',
    search: searchPO || undefined,
    pageSize: 50,
  });

  const form = useForm<InvoiceFormData>({
    resolver: zodResolver(invoiceSchema),
    defaultValues: {
      purchase_order: preSelectedPO || '',
      goods_receipt: '',
      supplier_invoice_no: '',
      invoice_date: new Date().toISOString().split('T')[0],
      due_date: '',
      notes: '',
      items: [],
    },
  });

  const selectedPOId = form.watch('purchase_order');
  const { data: selectedPO } = usePurchaseOrder(selectedPOId);
  const { data: poItems } = usePurchaseOrderItems(selectedPOId);
  const { data: poGRs } = usePurchaseOrderGRs(selectedPOId);

  // Populate items when PO is selected
  useEffect(() => {
    if (poItems && poItems.length > 0) {
      form.setValue(
        'items',
        poItems.map((item: any) => ({
          item_code: item.item_code,
          item_name: item.item_name || item.description,
          qty: item.qty,
          uom: item.uom,
          rate: item.rate,
          amount: item.amount || item.qty * item.rate,
        }))
      );
    }
  }, [poItems, form]);

  // Set due date based on payment terms
  useEffect(() => {
    if (selectedPO?.payment_terms && form.watch('invoice_date')) {
      const invoiceDate = new Date(form.watch('invoice_date'));
      let daysToAdd = 30; // Default Net 30

      switch (selectedPO.payment_terms) {
        case 'COD':
          daysToAdd = 0;
          break;
        case 'Net 7':
          daysToAdd = 7;
          break;
        case 'Net 15':
          daysToAdd = 15;
          break;
        case 'Net 30':
          daysToAdd = 30;
          break;
        case 'Net 45':
          daysToAdd = 45;
          break;
        case 'Net 60':
          daysToAdd = 60;
          break;
      }

      invoiceDate.setDate(invoiceDate.getDate() + daysToAdd);
      form.setValue('due_date', invoiceDate.toISOString().split('T')[0]);
    }
  }, [selectedPO?.payment_terms, form.watch('invoice_date')]);

  const { fields } = useFieldArray({
    control: form.control,
    name: 'items',
  });

  // Calculate totals
  const items = form.watch('items');
  const subtotal = items.reduce((sum, item) => sum + (item.amount || 0), 0);
  const taxRate = 0.12;
  const taxAmount = subtotal * taxRate;
  const grandTotal = subtotal + taxAmount;

  // Get PO and GR amounts for 3-way match preview
  const poAmount = selectedPO?.grand_total || 0;
  const grAmount = poGRs?.reduce((sum: number, gr: any) => {
    // Calculate GR amount based on received quantities and rates
    return sum + (gr.total_received_qty || 0) * (selectedPO?.items_avg_rate || 0);
  }, 0) || poAmount;

  const onSubmit = async (data: InvoiceFormData) => {
    try {
      const result = await createInvoice.mutateAsync({
        ...data,
        net_total: subtotal,
        tax_amount: taxAmount,
        grand_total: grandTotal,
      });
      toast.success('Invoice created successfully');
      router.push(`/dashboard/procurement/invoices/${result.name}`);
    } catch (error: any) {
      toast.error(error.message || 'Failed to create invoice');
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/procurement/invoices">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">New Invoice</h1>
          <p className="text-muted-foreground">
            Record supplier invoice for 3-way matching
          </p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Main Form */}
            <div className="lg:col-span-2 space-y-6">
              {/* PO Selection */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Select Purchase Order
                  </CardTitle>
                  <CardDescription>
                    Link this invoice to a purchase order for 3-way matching
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {!selectedPOId && (
                    <>
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                          placeholder="Search PO by number or supplier..."
                          value={searchPO}
                          onChange={(e) => setSearchPO(e.target.value)}
                          className="pl-9"
                        />
                      </div>
                      <div className="max-h-[200px] overflow-y-auto border rounded-lg">
                        {posData?.data?.map((po) => (
                          <div
                            key={po.name}
                            className="p-3 border-b last:border-b-0 cursor-pointer hover:bg-muted/50"
                            onClick={() => form.setValue('purchase_order', po.name)}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="font-medium">{po.po_no}</p>
                                <p className="text-sm text-muted-foreground">{po.supplier_name}</p>
                              </div>
                              <p className="text-sm font-medium">
                                {formatCurrency(po.grand_total || 0)}
                              </p>
                            </div>
                          </div>
                        ))}
                        {posData?.data?.length === 0 && (
                          <div className="p-4 text-center text-muted-foreground">
                            No approved POs found
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  {selectedPO && (
                    <div className="p-4 bg-muted rounded-lg">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-semibold">{selectedPO.po_no}</p>
                          <p className="text-sm text-muted-foreground">{selectedPO.supplier_name}</p>
                          <p className="text-sm font-medium mt-1">
                            PO Amount: {formatCurrency(selectedPO.grand_total || 0)}
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            form.setValue('purchase_order', '');
                            form.setValue('items', []);
                          }}
                        >
                          Change
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* GR Selection */}
                  {poGRs && poGRs.length > 0 && (
                    <FormField
                      control={form.control}
                      name="goods_receipt"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Link to Goods Receipt (Optional)</FormLabel>
                          <div className="space-y-2">
                            {poGRs.map((gr: any) => (
                              <div
                                key={gr.name}
                                className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                                  field.value === gr.name
                                    ? 'border-primary bg-primary/5'
                                    : 'hover:bg-muted/50'
                                }`}
                                onClick={() => field.onChange(gr.name)}
                              >
                                <div className="flex items-center justify-between">
                                  <div>
                                    <p className="font-medium">{gr.gr_number}</p>
                                    <p className="text-xs text-muted-foreground">
                                      {gr.receipt_date}
                                    </p>
                                  </div>
                                  <Badge variant="secondary">{gr.status}</Badge>
                                </div>
                              </div>
                            ))}
                          </div>
                        </FormItem>
                      )}
                    />
                  )}
                </CardContent>
              </Card>

              {/* Invoice Details */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Receipt className="h-5 w-5" />
                    Invoice Details
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="supplier_invoice_no"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Supplier Invoice # *</FormLabel>
                          <FormControl>
                            <Input placeholder="Invoice number from supplier" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="invoice_date"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Invoice Date *</FormLabel>
                          <FormControl>
                            <Input type="date" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="due_date"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Due Date *</FormLabel>
                          <FormControl>
                            <Input type="date" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                  <FormField
                    control={form.control}
                    name="notes"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Notes</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="Any notes about this invoice..."
                            className="min-h-[60px]"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              {/* Items */}
              {fields.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Invoice Items</CardTitle>
                    <CardDescription>
                      Verify quantities and rates match the supplier invoice
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Item Code</TableHead>
                          <TableHead>Description</TableHead>
                          <TableHead className="text-right w-[80px]">Qty</TableHead>
                          <TableHead className="text-right w-[100px]">Rate</TableHead>
                          <TableHead className="text-right">Amount</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {fields.map((field, index) => {
                          const qty = form.watch(`items.${index}.qty`);
                          const rate = form.watch(`items.${index}.rate`);
                          const amount = qty * rate;

                          // Update amount when qty or rate changes
                          if (amount !== form.watch(`items.${index}.amount`)) {
                            form.setValue(`items.${index}.amount`, amount);
                          }

                          return (
                            <TableRow key={field.id}>
                              <TableCell className="font-medium">
                                {form.watch(`items.${index}.item_code`)}
                              </TableCell>
                              <TableCell>
                                {form.watch(`items.${index}.item_name`)}
                              </TableCell>
                              <TableCell>
                                <FormField
                                  control={form.control}
                                  name={`items.${index}.qty`}
                                  render={({ field }) => (
                                    <FormItem>
                                      <FormControl>
                                        <Input
                                          type="number"
                                          min="0"
                                          className="h-8 w-16 text-right"
                                          {...field}
                                        />
                                      </FormControl>
                                    </FormItem>
                                  )}
                                />
                              </TableCell>
                              <TableCell>
                                <FormField
                                  control={form.control}
                                  name={`items.${index}.rate`}
                                  render={({ field }) => (
                                    <FormItem>
                                      <FormControl>
                                        <Input
                                          type="number"
                                          min="0"
                                          step="0.01"
                                          className="h-8 w-24 text-right"
                                          {...field}
                                        />
                                      </FormControl>
                                    </FormItem>
                                  )}
                                />
                              </TableCell>
                              <TableCell className="text-right font-medium">
                                {formatCurrency(amount)}
                              </TableCell>
                            </TableRow>
                          );
                        })}
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
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">VAT (12%)</span>
                            <span>{formatCurrency(taxAmount)}</span>
                          </div>
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
              )}
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">3-Way Match Preview</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">PO Amount</span>
                      <span>{formatCurrency(poAmount)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">GR Amount</span>
                      <span>{formatCurrency(grAmount)}</span>
                    </div>
                    <Separator />
                    <div className="flex justify-between text-sm font-medium">
                      <span>Invoice Amount</span>
                      <span>{formatCurrency(grandTotal)}</span>
                    </div>
                  </div>

                  {Math.abs(grandTotal - poAmount) > 0.01 && selectedPOId && (
                    <div className="p-3 bg-yellow-50 dark:bg-yellow-950/20 rounded-lg border border-yellow-200">
                      <div className="flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                        <div className="text-sm">
                          <p className="font-medium text-yellow-800 dark:text-yellow-200">
                            Variance Detected
                          </p>
                          <p className="text-yellow-600 dark:text-yellow-300 text-xs">
                            Invoice differs from PO by {formatCurrency(Math.abs(grandTotal - poAmount))}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  <Separator />

                  <div className="space-y-3">
                    <Button
                      type="submit"
                      className="w-full"
                      disabled={createInvoice.isPending || !selectedPOId}
                    >
                      {createInvoice.isPending ? 'Creating...' : 'Create Invoice'}
                    </Button>
                    <Link href="/dashboard/procurement/invoices" className="block">
                      <Button type="button" variant="outline" className="w-full">
                        Cancel
                      </Button>
                    </Link>
                  </div>

                  <p className="text-xs text-muted-foreground text-center">
                    Invoice will be auto-matched after creation.
                  </p>
                </CardContent>
              </Card>

              {selectedPO && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Payment Terms</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Badge variant="outline" className="w-full justify-center">
                      {selectedPO.payment_terms || 'Net 30'}
                    </Badge>
                    <p className="text-xs text-muted-foreground text-center mt-2">
                      Due date calculated automatically
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </form>
      </Form>
    </div>
  );
}
