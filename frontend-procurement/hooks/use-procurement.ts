/**
 * Procurement Module Hooks
 * React Query hooks for all procurement endpoints
 *
 * Copy this file to: bei-tasks/src/hooks/use-procurement.ts
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

// API base - adjust based on environment
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/procurement';

// =============================================================================
// TYPE DEFINITIONS
// =============================================================================

export interface Supplier {
  name: string;
  supplier_code: string;
  supplier_name: string;
  status: 'Active' | 'Inactive' | 'Blacklisted';
  category?: string;
  email?: string;
  contact_person?: string;
  phone?: string;
  total_orders: number;
  total_amount: number;
  bir_2307?: string;
  sec_certificate?: string;
  rating?: number;
}

export interface PurchaseOrder {
  name: string;
  po_no: string;
  po_date: string;
  status: string;
  supplier: string;
  supplier_name: string;
  grand_total: number;
  requires_dual_approval: boolean;
  mae_approval: string;
  butch_approval: string;
  delivery_date?: string;
}

export interface Invoice {
  name: string;
  invoice_number: string;
  supplier_invoice_no: string;
  invoice_date: string;
  due_date: string;
  status: string;
  supplier: string;
  supplier_name: string;
  purchase_order: string;
  po_number: string;
  grand_total: number;
  balance_due: number;
  payment_status: string;
  match_status: string;
  po_amount?: number;
  gr_amount?: number;
  po_gr_variance?: number;
  gr_inv_variance?: number;
}

export interface GoodsReceipt {
  name: string;
  gr_number: string;
  receipt_date: string;
  status: string;
  supplier: string;
  supplier_name: string;
  purchase_order: string;
  po_number: string;
  total_ordered_qty: number;
  total_received_qty: number;
  inspection_notes?: string;
}

export interface PaymentRequest {
  name: string;
  request_number: string;
  request_date: string;
  status: string;
  supplier: string;
  supplier_name: string;
  payment_amount: number;
  payment_method: 'Bank Transfer' | 'Check';
  invoice: string;
  ceo_required: boolean;
  payment_date?: string;
  check_number?: string;
}

export interface DashboardKPIs {
  total_outstanding: number;
  overdue_amount: number;
  mtd_po_value: number;
  mtd_po_count: number;
  pending_po_approvals: number;
  pending_payment_approvals: number;
  active_suppliers: number;
  avg_payment_days: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// =============================================================================
// FETCH UTILITIES
// =============================================================================

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    credentials: 'include',
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.message || `HTTP ${res.status}`);
  }

  return res.json();
}

// =============================================================================
// SUPPLIER HOOKS
// =============================================================================

export function useSuppliers(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: string;
}) {
  const queryParams = new URLSearchParams();
  if (params?.page) queryParams.set('page', String(params.page));
  if (params?.pageSize) queryParams.set('page_size', String(params.pageSize));
  if (params?.search) queryParams.set('search', params.search);
  if (params?.status) queryParams.set('filters', JSON.stringify({ status: params.status }));

  return useQuery({
    queryKey: ['suppliers', params],
    queryFn: () => fetchAPI<PaginatedResponse<Supplier>>(`/suppliers?${queryParams}`),
  });
}

export function useSupplier(name: string) {
  return useQuery({
    queryKey: ['supplier', name],
    queryFn: () => fetchAPI<Supplier>(`/suppliers/${name}`),
    enabled: !!name,
  });
}

export function useSupplierMetrics(name: string) {
  return useQuery({
    queryKey: ['supplier-metrics', name],
    queryFn: () => fetchAPI<any>(`/suppliers/${name}/metrics`),
    enabled: !!name,
  });
}

export function useCreateSupplier() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Supplier>) =>
      fetchAPI<{ success: boolean; name: string }>('/suppliers', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      toast.success('Supplier created successfully');
    },
    onError: (error: Error) => {
      toast.error(`Failed to create supplier: ${error.message}`);
    },
  });
}

export function useUpdateSupplier() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: Partial<Supplier> }) =>
      fetchAPI<{ success: boolean }>(`/suppliers/${name}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, { name }) => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      queryClient.invalidateQueries({ queryKey: ['supplier', name] });
      toast.success('Supplier updated successfully');
    },
    onError: (error: Error) => {
      toast.error(`Failed to update supplier: ${error.message}`);
    },
  });
}

// =============================================================================
// PURCHASE ORDER HOOKS
// =============================================================================

export function usePurchaseOrders(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: string;
  supplier?: string;
  pendingApproval?: boolean;
}) {
  const queryParams = new URLSearchParams();
  if (params?.page) queryParams.set('page', String(params.page));
  if (params?.pageSize) queryParams.set('page_size', String(params.pageSize));
  if (params?.search) queryParams.set('search', params.search);

  const filters: Record<string, any> = {};
  if (params?.status) filters.status = params.status;
  if (params?.supplier) filters.supplier = params.supplier;
  if (params?.pendingApproval) filters.pending_approval = true;
  if (Object.keys(filters).length) queryParams.set('filters', JSON.stringify(filters));

  return useQuery({
    queryKey: ['purchase-orders', params],
    queryFn: () => fetchAPI<PaginatedResponse<PurchaseOrder>>(`/purchase-orders?${queryParams}`),
  });
}

export function usePurchaseOrder(name: string) {
  return useQuery({
    queryKey: ['purchase-order', name],
    queryFn: () => fetchAPI<PurchaseOrder>(`/purchase-orders/${name}`),
    enabled: !!name,
  });
}

export function usePendingPOApprovals() {
  return useQuery({
    queryKey: ['pending-po-approvals'],
    queryFn: () => fetchAPI<{
      pending_mae: PurchaseOrder[];
      pending_butch: PurchaseOrder[];
      total_pending: number;
    }>('/purchase-orders/pending-approvals'),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) =>
      fetchAPI<{ success: boolean; name: string }>('/purchase-orders', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      toast.success('Purchase Order created');
    },
    onError: (error: Error) => {
      toast.error(`Failed to create PO: ${error.message}`);
    },
  });
}

export function useSubmitPOForApproval() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name: string) =>
      fetchAPI<{ success: boolean }>(`/purchase-orders/${name}/submit`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      queryClient.invalidateQueries({ queryKey: ['pending-po-approvals'] });
      toast.success('PO submitted for approval');
    },
    onError: (error: Error) => {
      toast.error(`Failed to submit PO: ${error.message}`);
    },
  });
}

export function useApprovePO() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, level, comment }: { name: string; level: 'mae' | 'butch'; comment?: string }) =>
      fetchAPI<{ success: boolean; message: string }>(`/purchase-orders/${name}/approve/${level}`, {
        method: 'POST',
        body: JSON.stringify({ comment }),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      queryClient.invalidateQueries({ queryKey: ['pending-po-approvals'] });
      toast.success(data.message);
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve PO: ${error.message}`);
    },
  });
}

export function useRejectPO() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, reason, rejector }: { name: string; reason: string; rejector?: 'mae' | 'butch' }) =>
      fetchAPI<{ success: boolean }>(`/purchase-orders/${name}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason, rejector }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      queryClient.invalidateQueries({ queryKey: ['pending-po-approvals'] });
      toast.success('PO rejected');
    },
    onError: (error: Error) => {
      toast.error(`Failed to reject PO: ${error.message}`);
    },
  });
}

// =============================================================================
// INVOICE HOOKS
// =============================================================================

export function useInvoices(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: string;
  paymentStatus?: string;
  overdue?: boolean;
}) {
  const queryParams = new URLSearchParams();
  if (params?.page) queryParams.set('page', String(params.page));
  if (params?.pageSize) queryParams.set('page_size', String(params.pageSize));
  if (params?.search) queryParams.set('search', params.search);

  const filters: Record<string, any> = {};
  if (params?.status) filters.status = params.status;
  if (params?.paymentStatus) filters.payment_status = params.paymentStatus;
  if (params?.overdue) filters.overdue = true;
  if (Object.keys(filters).length) queryParams.set('filters', JSON.stringify(filters));

  return useQuery({
    queryKey: ['invoices', params],
    queryFn: () => fetchAPI<PaginatedResponse<Invoice>>(`/invoices?${queryParams}`),
  });
}

export function useInvoice(name: string) {
  return useQuery({
    queryKey: ['invoice', name],
    queryFn: () => fetchAPI<Invoice>(`/invoices/${name}`),
    enabled: !!name,
  });
}

export function useCreateInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) =>
      fetchAPI<{ success: boolean; name: string }>('/invoices', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success('Invoice created');
    },
    onError: (error: Error) => {
      toast.error(`Failed to create invoice: ${error.message}`);
    },
  });
}

export function useVerifyInvoiceMatch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name: string) =>
      fetchAPI<{ success: boolean; message: string; po_gr_variance?: number; gr_inv_variance?: number }>(
        `/invoices/${name}/verify`,
        { method: 'POST' }
      ),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      if (data.success) {
        toast.success(data.message);
      } else {
        toast.warning(data.message);
      }
    },
    onError: (error: Error) => {
      toast.error(`Failed to verify invoice: ${error.message}`);
    },
  });
}

// =============================================================================
// PAYMENT REQUEST HOOKS
// =============================================================================

export function usePaymentRequests(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: string;
  pendingApproval?: boolean;
}) {
  const queryParams = new URLSearchParams();
  if (params?.page) queryParams.set('page', String(params.page));
  if (params?.pageSize) queryParams.set('page_size', String(params.pageSize));
  if (params?.search) queryParams.set('search', params.search);

  const filters: Record<string, any> = {};
  if (params?.status) filters.status = params.status;
  if (params?.pendingApproval) filters.pending_approval = true;
  if (Object.keys(filters).length) queryParams.set('filters', JSON.stringify(filters));

  return useQuery({
    queryKey: ['payment-requests', params],
    queryFn: () => fetchAPI<PaginatedResponse<PaymentRequest>>(`/payment-requests?${queryParams}`),
  });
}

export function usePaymentRequest(name: string) {
  return useQuery({
    queryKey: ['payment-request', name],
    queryFn: () => fetchAPI<PaymentRequest & { approval_status: any }>(`/payment-requests/${name}`),
    enabled: !!name,
  });
}

export function usePendingPaymentApprovals() {
  return useQuery({
    queryKey: ['pending-payment-approvals'],
    queryFn: () => fetchAPI<{
      review: PaymentRequest[];
      budget: PaymentRequest[];
      cfo: PaymentRequest[];
      ceo: PaymentRequest[];
      total_pending: number;
    }>('/payment-requests/pending-approvals'),
    refetchInterval: 30000,
  });
}

export function useCreatePaymentRequest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) =>
      fetchAPI<{ success: boolean; name: string }>('/payment-requests', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
      toast.success('Payment request created');
    },
    onError: (error: Error) => {
      toast.error(`Failed to create payment request: ${error.message}`);
    },
  });
}

export function useApprovePayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, level, comment }: { name: string; level: 'review' | 'budget' | 'cfo' | 'ceo'; comment?: string }) =>
      fetchAPI<{ success: boolean; message: string }>(`/payment-requests/${name}/approve/${level}`, {
        method: 'POST',
        body: JSON.stringify({ comment }),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
      queryClient.invalidateQueries({ queryKey: ['pending-payment-approvals'] });
      toast.success(data.message);
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve payment: ${error.message}`);
    },
  });
}

export function useRejectPayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, level, reason }: { name: string; level: string; reason: string }) =>
      fetchAPI<{ success: boolean }>(`/payment-requests/${name}/reject`, {
        method: 'POST',
        body: JSON.stringify({ level, reason }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
      queryClient.invalidateQueries({ queryKey: ['pending-payment-approvals'] });
      toast.success('Payment request rejected');
    },
    onError: (error: Error) => {
      toast.error(`Failed to reject payment: ${error.message}`);
    },
  });
}

export function useMarkPaymentComplete() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, transactionRef, proof }: { name: string; transactionRef?: string; proof?: string }) =>
      fetchAPI<{ success: boolean }>(`/payment-requests/${name}/complete`, {
        method: 'POST',
        body: JSON.stringify({ transaction_reference: transactionRef, payment_proof: proof }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
      toast.success('Payment marked as complete');
    },
    onError: (error: Error) => {
      toast.error(`Failed to mark payment complete: ${error.message}`);
    },
  });
}

// =============================================================================
// DASHBOARD HOOKS
// =============================================================================

export function useDashboardKPIs() {
  return useQuery({
    queryKey: ['dashboard-kpis'],
    queryFn: () => fetchAPI<DashboardKPIs>('/dashboard/kpis'),
    refetchInterval: 60000, // Refresh every minute
  });
}

export function useOutstandingBySupplier() {
  return useQuery({
    queryKey: ['outstanding-by-supplier'],
    queryFn: () => fetchAPI<any[]>('/dashboard/outstanding-by-supplier'),
    refetchInterval: 60000,
  });
}

export function useAgingAnalysis() {
  return useQuery({
    queryKey: ['aging-analysis'],
    queryFn: () => fetchAPI<{
      current: number;
      days_1_30: number;
      days_31_60: number;
      days_61_90: number;
      over_90: number;
      total: number;
    }>('/dashboard/aging'),
  });
}

export function useMonthlyPOTrend(months: number = 6) {
  return useQuery({
    queryKey: ['monthly-po-trend', months],
    queryFn: () => fetchAPI<{ month: string; po_count: number; po_value: number }[]>(
      `/dashboard/po-trend?months=${months}`
    ),
  });
}

export function usePaymentSchedule() {
  return useQuery({
    queryKey: ['payment-schedule'],
    queryFn: () => fetchAPI<any[]>('/dashboard/payment-schedule'),
    refetchInterval: 60000,
  });
}

export function useSupplierPerformance() {
  return useQuery({
    queryKey: ['supplier-performance'],
    queryFn: () => fetchAPI<any[]>('/dashboard/supplier-performance'),
  });
}

// =============================================================================
// ADDITIONAL SUPPLIER HOOKS
// =============================================================================

export function useSupplierPurchaseOrders(supplierId: string) {
  return useQuery({
    queryKey: ['supplier-purchase-orders', supplierId],
    queryFn: () => fetchAPI<PaginatedResponse<PurchaseOrder>>(`/suppliers/${supplierId}/purchase-orders`),
    enabled: !!supplierId,
  });
}

export function useSupplierInvoices(supplierId: string) {
  return useQuery({
    queryKey: ['supplier-invoices', supplierId],
    queryFn: () => fetchAPI<PaginatedResponse<Invoice>>(`/suppliers/${supplierId}/invoices`),
    enabled: !!supplierId,
  });
}

// =============================================================================
// GOODS RECEIPT HOOKS
// =============================================================================

export function useGoodsReceipts(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: string;
  supplier?: string;
}) {
  const queryParams = new URLSearchParams();
  if (params?.page) queryParams.set('page', String(params.page));
  if (params?.pageSize) queryParams.set('page_size', String(params.pageSize));
  if (params?.search) queryParams.set('search', params.search);

  const filters: Record<string, any> = {};
  if (params?.status) filters.status = params.status;
  if (params?.supplier) filters.supplier = params.supplier;
  if (Object.keys(filters).length) queryParams.set('filters', JSON.stringify(filters));

  return useQuery({
    queryKey: ['goods-receipts', params],
    queryFn: () => fetchAPI<PaginatedResponse<GoodsReceipt>>(`/goods-receipts?${queryParams}`),
  });
}

export function useGoodsReceipt(name: string) {
  return useQuery({
    queryKey: ['goods-receipt', name],
    queryFn: () => fetchAPI<GoodsReceipt>(`/goods-receipts/${name}`),
    enabled: !!name,
  });
}

export function useCreateGoodsReceipt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) =>
      fetchAPI<{ success: boolean; name: string }>('/goods-receipts', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goods-receipts'] });
      toast.success('Goods Receipt created');
    },
    onError: (error: Error) => {
      toast.error(`Failed to create Goods Receipt: ${error.message}`);
    },
  });
}

export function useCompleteInspection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, result, notes }: { id: string; result: 'pass' | 'fail'; notes?: string }) =>
      fetchAPI<{ success: boolean }>(`/goods-receipts/${id}/complete-inspection`, {
        method: 'POST',
        body: JSON.stringify({ result, notes }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goods-receipts'] });
      toast.success('Inspection completed');
    },
    onError: (error: Error) => {
      toast.error(`Failed to complete inspection: ${error.message}`);
    },
  });
}

// =============================================================================
// ADDITIONAL INVOICE HOOKS
// =============================================================================

export function useApproveVariance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) =>
      fetchAPI<{ success: boolean }>(`/invoices/${id}/approve-variance`, {
        method: 'POST',
        body: JSON.stringify({ notes }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      toast.success('Variance approved');
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve variance: ${error.message}`);
    },
  });
}

// =============================================================================
// INDIVIDUAL PAYMENT APPROVAL HOOKS (4-level workflow)
// =============================================================================

export function useApprovePaymentReview() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      fetchAPI<{ success: boolean; message: string }>(`/payment-requests/${id}/approve/review`, {
        method: 'POST',
        body: JSON.stringify({ notes }),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
      queryClient.invalidateQueries({ queryKey: ['pending-payment-approvals'] });
      toast.success(data.message || 'Review approval complete');
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve: ${error.message}`);
    },
  });
}

export function useApprovePaymentBudget() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      fetchAPI<{ success: boolean; message: string }>(`/payment-requests/${id}/approve/budget`, {
        method: 'POST',
        body: JSON.stringify({ notes }),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
      queryClient.invalidateQueries({ queryKey: ['pending-payment-approvals'] });
      toast.success(data.message || 'Budget approval complete');
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve: ${error.message}`);
    },
  });
}

export function useApprovePaymentCFO() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      fetchAPI<{ success: boolean; message: string }>(`/payment-requests/${id}/approve/cfo`, {
        method: 'POST',
        body: JSON.stringify({ notes }),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
      queryClient.invalidateQueries({ queryKey: ['pending-payment-approvals'] });
      toast.success(data.message || 'CFO approval complete');
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve: ${error.message}`);
    },
  });
}

export function useApprovePaymentCEO() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      fetchAPI<{ success: boolean; message: string }>(`/payment-requests/${id}/approve/ceo`, {
        method: 'POST',
        body: JSON.stringify({ notes }),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
      queryClient.invalidateQueries({ queryKey: ['pending-payment-approvals'] });
      toast.success(data.message || 'CEO approval complete');
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve: ${error.message}`);
    },
  });
}

// =============================================================================
// PURCHASE REQUISITION HOOKS
// =============================================================================

export interface PurchaseRequisition {
  name: string;
  pr_number: string;
  pr_date: string;
  status: 'Draft' | 'Pending Approval' | 'Approved' | 'Rejected' | 'Converted to PO';
  requester: string;
  requester_name: string;
  department: string;
  total_amount: number;
  items_count: number;
  justification?: string;
  approved_by?: string;
  approved_date?: string;
  rejection_reason?: string;
  converted_po?: string;
}

export interface PurchaseRequisitionItem {
  name: string;
  item_code?: string;
  item_name: string;
  description?: string;
  qty: number;
  uom: string;
  estimated_rate: number;
  amount: number;
}

export interface PurchaseRequisitionDetail extends PurchaseRequisition {
  items: PurchaseRequisitionItem[];
}

export function usePurchaseRequisitions(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: string;
  department?: string;
  requester?: string;
}) {
  const queryParams = new URLSearchParams();
  if (params?.page) queryParams.set('page', String(params.page));
  if (params?.pageSize) queryParams.set('page_size', String(params.pageSize));
  if (params?.search) queryParams.set('search', params.search);

  const filters: Record<string, any> = {};
  if (params?.status) filters.status = params.status;
  if (params?.department) filters.department = params.department;
  if (params?.requester) filters.requester = params.requester;
  if (Object.keys(filters).length) queryParams.set('filters', JSON.stringify(filters));

  return useQuery({
    queryKey: ['purchase-requisitions', params],
    queryFn: () => fetchAPI<PaginatedResponse<PurchaseRequisition>>(`/purchase-requisitions?${queryParams}`),
  });
}

export function usePurchaseRequisition(name: string) {
  return useQuery({
    queryKey: ['purchase-requisition', name],
    queryFn: () => fetchAPI<PurchaseRequisitionDetail>(`/purchase-requisitions/${name}`),
    enabled: !!name,
  });
}

export function usePurchaseRequisitionStats() {
  return useQuery({
    queryKey: ['purchase-requisition-stats'],
    queryFn: () => fetchAPI<{
      total: number;
      pending_approval: number;
      approved_this_month: number;
      total_amount_this_month: number;
    }>('/purchase-requisitions/stats'),
    refetchInterval: 60000,
  });
}

export function useCreatePurchaseRequisition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      department: string;
      justification?: string;
      items: Omit<PurchaseRequisitionItem, 'name' | 'amount'>[];
    }) =>
      fetchAPI<{ success: boolean; name: string; pr_number: string }>('/purchase-requisitions', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-requisitions'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-requisition-stats'] });
      toast.success('Purchase Requisition created');
    },
    onError: (error: Error) => {
      toast.error(`Failed to create PR: ${error.message}`);
    },
  });
}

export function useUpdatePurchaseRequisition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: Partial<PurchaseRequisitionDetail> }) =>
      fetchAPI<{ success: boolean }>(`/purchase-requisitions/${name}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, { name }) => {
      queryClient.invalidateQueries({ queryKey: ['purchase-requisitions'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-requisition', name] });
      toast.success('Purchase Requisition updated');
    },
    onError: (error: Error) => {
      toast.error(`Failed to update PR: ${error.message}`);
    },
  });
}

export function useSubmitPRForApproval() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name: string) =>
      fetchAPI<{ success: boolean; message: string }>(`/purchase-requisitions/${name}/submit`, {
        method: 'POST',
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['purchase-requisitions'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-requisition-stats'] });
      toast.success(data.message || 'PR submitted for approval');
    },
    onError: (error: Error) => {
      toast.error(`Failed to submit PR: ${error.message}`);
    },
  });
}

export function useApprovePR() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, comment }: { name: string; comment?: string }) =>
      fetchAPI<{ success: boolean; message: string }>(`/purchase-requisitions/${name}/approve`, {
        method: 'POST',
        body: JSON.stringify({ comment }),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['purchase-requisitions'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-requisition-stats'] });
      toast.success(data.message || 'PR approved');
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve PR: ${error.message}`);
    },
  });
}

export function useRejectPR() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, reason }: { name: string; reason: string }) =>
      fetchAPI<{ success: boolean }>(`/purchase-requisitions/${name}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-requisitions'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-requisition-stats'] });
      toast.success('PR rejected');
    },
    onError: (error: Error) => {
      toast.error(`Failed to reject PR: ${error.message}`);
    },
  });
}

export function useConvertPRToPO() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, supplier }: { name: string; supplier: string }) =>
      fetchAPI<{ success: boolean; po_name: string; po_number: string }>(
        `/purchase-requisitions/${name}/convert-to-po`,
        {
          method: 'POST',
          body: JSON.stringify({ supplier }),
        }
      ),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['purchase-requisitions'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-requisition-stats'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      toast.success(`Converted to PO: ${data.po_number}`);
    },
    onError: (error: Error) => {
      toast.error(`Failed to convert PR to PO: ${error.message}`);
    },
  });
}

// =============================================================================
// PURCHASE ORDER DETAIL HOOKS
// =============================================================================

export interface POItem {
  name: string;
  item_code: string;
  item_name?: string;
  description?: string;
  qty: number;
  uom: string;
  rate: number;
  amount: number;
}

export interface POHistory {
  action: string;
  user: string;
  timestamp: string;
  comment?: string;
}

export interface PurchaseOrderDetail extends PurchaseOrder {
  supplier_has_bir: boolean;
  supplier_has_sec: boolean;
  tax_amount: number;
  mae_approval_date?: string;
  butch_approval_date?: string;
  mae_comment?: string;
  butch_comment?: string;
  remarks?: string;
}

export function usePurchaseOrderItems(poId: string) {
  return useQuery({
    queryKey: ['purchase-order-items', poId],
    queryFn: () => fetchAPI<POItem[]>(`/purchase-orders/${poId}/items`),
    enabled: !!poId,
  });
}

export function usePurchaseOrderGRs(poId: string) {
  return useQuery({
    queryKey: ['purchase-order-grs', poId],
    queryFn: () => fetchAPI<GoodsReceipt[]>(`/purchase-orders/${poId}/goods-receipts`),
    enabled: !!poId,
  });
}

export function usePurchaseOrderInvoices(poId: string) {
  return useQuery({
    queryKey: ['purchase-order-invoices', poId],
    queryFn: () => fetchAPI<Invoice[]>(`/purchase-orders/${poId}/invoices`),
    enabled: !!poId,
  });
}

export function usePurchaseOrderHistory(poId: string) {
  return useQuery({
    queryKey: ['purchase-order-history', poId],
    queryFn: () => fetchAPI<POHistory[]>(`/purchase-orders/${poId}/history`),
    enabled: !!poId,
  });
}

export function useUpdatePurchaseOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: any }) =>
      fetchAPI<{ success: boolean }>(`/purchase-orders/${name}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, { name }) => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-order', name] });
      queryClient.invalidateQueries({ queryKey: ['purchase-order-items', name] });
      toast.success('Purchase Order updated');
    },
    onError: (error: Error) => {
      toast.error(`Failed to update PO: ${error.message}`);
    },
  });
}

// =============================================================================
// ITEMS HOOKS (for PO creation)
// =============================================================================

export interface Item {
  name: string;
  item_code: string;
  item_name: string;
  description?: string;
  item_group?: string;
  stock_uom: string;
  standard_rate: number;
  is_stock_item: boolean;
}

export function useItems(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  itemGroup?: string;
}) {
  const queryParams = new URLSearchParams();
  if (params?.page) queryParams.set('page', String(params.page));
  if (params?.pageSize) queryParams.set('page_size', String(params.pageSize));
  if (params?.search) queryParams.set('search', params.search);
  if (params?.itemGroup) queryParams.set('item_group', params.itemGroup);

  return useQuery({
    queryKey: ['items', params],
    queryFn: () => fetchAPI<PaginatedResponse<Item>>(`/items?${queryParams}`),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });
}

export function useItem(name: string) {
  return useQuery({
    queryKey: ['item', name],
    queryFn: () => fetchAPI<Item>(`/items/${name}`),
    enabled: !!name,
  });
}

export function useORAgingAnalysis() {
  return useQuery({
    queryKey: ['or-aging-analysis'],
    queryFn: () => fetchAPI<{
      days_0_7: number;
      days_8_14: number;
      days_15_30: number;
      over_30: number;
    }>('/purchase-orders/or-aging-summary'), // Endpoint in procurement.py
  });
}

// Phase 2 Hooks

export function useClearAdvanceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { advance_payment: string; goods_receipt: string; amount_to_clear: number }) =>
      fetchAPI('/advances/clear', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['advances'] }),
  });
}

export function useUndeliverableAdvanceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { advance_payment: string; amount: number; reason: string }) =>
      fetchAPI('/advances/undeliverable', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['advances'] }),
  });
}

export function useSOAList(params?: any) {
  return useQuery({
    queryKey: ['soa-list', params],
    queryFn: () => fetchAPI<any>('/soa'),
  });
}

export function useSOA(name: string) {
  return useQuery({
    queryKey: ['soa', name],
    queryFn: () => fetchAPI<any>(`/soa/detail?name=${name}`),
    enabled: !!name,
  });
}

export function useSendSOAMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { soa_name: string }) =>
      fetchAPI('/soa/send', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['soa'] }),
  });
}

export function useBillingRates() {
  return useQuery({
    queryKey: ['billing-rates'],
    queryFn: () => fetchAPI<any>('/billing/rates'),
  });
}

export function useApproveRateMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { rate_id: string }) =>
      fetchAPI('/billing/rates/approve', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['billing-rates'] }),
  });
}
