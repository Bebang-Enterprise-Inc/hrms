/**
 * New Supplier Page
 * Create a new supplier with BIR/SEC document requirements
 *
 * Copy to: bei-tasks/src/app/dashboard/procurement/suppliers/new/page.tsx
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
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
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { ArrowLeft, Building2, Upload } from 'lucide-react';
import { useCreateSupplier } from '@/hooks/use-procurement';

// Form validation schema
const supplierSchema = z.object({
  supplier_name: z.string().min(2, 'Supplier name must be at least 2 characters'),
  supplier_code: z.string().optional(),
  status: z.enum(['Active', 'Inactive']),
  email: z.string().email('Invalid email address').optional().or(z.literal('')),
  phone: z.string().optional(),
  contact_person: z.string().optional(),
  address: z.string().optional(),
  tin: z.string().optional(),
  sec_registration_no: z.string().optional(),
  payment_terms: z.string().optional(),
  credit_limit: z.coerce.number().min(0).optional(),
  bank_name: z.string().optional(),
  bank_account_no: z.string().optional(),
  bank_account_name: z.string().optional(),
  vat_status: z.string().optional(),
  ewt_exempt: z.boolean().default(false),
  ewt_applicable: z.boolean().default(false),
});

type SupplierFormData = z.infer<typeof supplierSchema>;

export default function NewSupplierPage() {
  const router = useRouter();
  const createSupplier = useCreateSupplier();
  const [birFile, setBirFile] = useState<File | null>(null);
  const [secFile, setSecFile] = useState<File | null>(null);

  const form = useForm<SupplierFormData>({
    resolver: zodResolver(supplierSchema),
    defaultValues: {
      status: 'Active',
      supplier_name: '',
      email: '',
      phone: '',
      contact_person: '',
      address: '',
      tin: '',
      sec_registration_no: '',
      payment_terms: 'Net 30',
      credit_limit: 0,
      bank_name: '',
      bank_account_no: '',
      bank_account_name: '',
      vat_status: 'VAT Registered',
      ewt_exempt: false,
      ewt_applicable: false,
    },
  });

  const onSubmit = async (data: SupplierFormData) => {
    try {
      const result = await createSupplier.mutateAsync({
        ...data,
        is_new_supplier: 1,
      });

      // TODO: Upload BIR and SEC files if provided
      if (birFile || secFile) {
        // File upload logic would go here
        toast.info('Note: Document upload will be available soon');
      }

      toast.success('Supplier created successfully');
      router.push(`/dashboard/procurement/suppliers/${result.name}`);
    } catch (error: any) {
      toast.error(error.message || 'Failed to create supplier');
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/procurement/suppliers">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">New Supplier</h1>
          <p className="text-muted-foreground">
            Add a new supplier to the procurement system
          </p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                Basic Information
              </CardTitle>
              <CardDescription>
                Enter the supplier's company details
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="supplier_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Supplier Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="ABC Trading Corp." {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="supplier_code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Supplier Code</FormLabel>
                      <FormControl>
                        <Input placeholder="Auto-generated if blank" {...field} />
                      </FormControl>
                      <FormDescription>
                        Leave blank to auto-generate
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Status</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select status" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="Active">Active</SelectItem>
                          <SelectItem value="Inactive">Inactive</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="contact_person"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Contact Person</FormLabel>
                      <FormControl>
                        <Input placeholder="Juan Dela Cruz" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email</FormLabel>
                      <FormControl>
                        <Input type="email" placeholder="supplier@example.com" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone</FormLabel>
                      <FormControl>
                        <Input placeholder="+63 XXX XXX XXXX" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="address"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Address</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Full business address"
                        className="resize-none"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          {/* Tax & Legal Information */}
          <Card>
            <CardHeader>
              <CardTitle>Tax & Legal Information</CardTitle>
              <CardDescription>
                Required for BIR compliance and payments
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="tin"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>TIN (Tax Identification Number)</FormLabel>
                      <FormControl>
                        <Input placeholder="XXX-XXX-XXX-XXX" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="sec_registration_no"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>SEC Registration Number</FormLabel>
                      <FormControl>
                        <Input placeholder="CS20XXXXXXX" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="vat_status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>VAT Status</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select VAT Status" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="VAT Registered">VAT Registered</SelectItem>
                          <SelectItem value="Non-VAT Registered">Non-VAT Registered</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2 mt-4">
                <FormField
                  control={form.control}
                  name="ewt_applicable"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">EWT Applicable</FormLabel>
                        <FormDescription>
                          Is this supplier subject to Expanded Withholding Tax?
                        </FormDescription>
                      </div>
                      <FormControl>
                        <input
                          type="checkbox"
                          className="h-5 w-5 rounded border-gray-300 text-primary focus:ring-primary accent-primary"
                          checked={field.value}
                          onChange={(e) => field.onChange(e.target.checked)}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="ewt_exempt"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">EWT Exempt</FormLabel>
                        <FormDescription>
                          Is this supplier exempt from EWT?
                        </FormDescription>
                      </div>
                      <FormControl>
                        <input
                          type="checkbox"
                          className="h-5 w-5 rounded border-gray-300 text-primary focus:ring-primary accent-primary"
                          checked={field.value}
                          onChange={(e) => field.onChange(e.target.checked)}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>

              <Separator className="my-4" />

              {/* Document Uploads */}
              <div className="space-y-4">
                <h4 className="font-medium">Required Documents</h4>
                <p className="text-sm text-muted-foreground">
                  BIR 2307 and SEC Certificate are required before processing payments
                </p>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="border rounded-lg p-4 space-y-2">
                    <label className="text-sm font-medium">BIR 2307 Certificate</label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        onChange={(e) => setBirFile(e.target.files?.[0] || null)}
                        className="flex-1"
                      />
                    </div>
                    {birFile && (
                      <p className="text-xs text-muted-foreground">
                        Selected: {birFile.name}
                      </p>
                    )}
                  </div>

                  <div className="border rounded-lg p-4 space-y-2">
                    <label className="text-sm font-medium">SEC Certificate</label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        onChange={(e) => setSecFile(e.target.files?.[0] || null)}
                        className="flex-1"
                      />
                    </div>
                    {secFile && (
                      <p className="text-xs text-muted-foreground">
                        Selected: {secFile.name}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Payment Information */}
          <Card>
            <CardHeader>
              <CardTitle>Payment Information</CardTitle>
              <CardDescription>
                Bank details for payment processing (Bank Transfer or Check only)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="payment_terms"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Payment Terms</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select payment terms" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="COD">Cash on Delivery</SelectItem>
                          <SelectItem value="Net 15">Net 15</SelectItem>
                          <SelectItem value="Net 30">Net 30</SelectItem>
                          <SelectItem value="Net 45">Net 45</SelectItem>
                          <SelectItem value="Net 60">Net 60</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="credit_limit"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Credit Limit (PHP)</FormLabel>
                      <FormControl>
                        <Input type="number" placeholder="0" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="bank_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Bank Name</FormLabel>
                      <FormControl>
                        <Input placeholder="BDO, BPI, etc." {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="bank_account_no"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Bank Account Number</FormLabel>
                      <FormControl>
                        <Input placeholder="XXXX-XXXX-XXXX" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="bank_account_name"
                  render={({ field }) => (
                    <FormItem className="md:col-span-2">
                      <FormLabel>Bank Account Name</FormLabel>
                      <FormControl>
                        <Input placeholder="Account holder name" {...field} />
                      </FormControl>
                      <FormDescription>
                        Must match the supplier's registered business name
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex justify-end gap-4">
            <Link href="/dashboard/procurement/suppliers">
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </Link>
            <Button type="submit" disabled={createSupplier.isPending}>
              {createSupplier.isPending ? 'Creating...' : 'Create Supplier'}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
