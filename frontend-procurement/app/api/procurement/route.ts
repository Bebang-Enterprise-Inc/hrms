/**
 * Procurement API Proxy Route
 * Proxies requests to Frappe backend
 *
 * Copy this file to: bei-tasks/src/app/api/procurement/route.ts
 */

import { NextRequest, NextResponse } from 'next/server';

const FRAPPE_URL = process.env.FRAPPE_URL || 'https://hq.bebang.ph';
const FRAPPE_API_KEY = process.env.FRAPPE_API_KEY;
const FRAPPE_API_SECRET = process.env.FRAPPE_API_SECRET;

// Build authorization header
function getAuthHeader() {
  if (FRAPPE_API_KEY && FRAPPE_API_SECRET) {
    return `token ${FRAPPE_API_KEY}:${FRAPPE_API_SECRET}`;
  }
  return '';
}

// Map our API routes to Frappe methods
const ROUTE_MAP: Record<string, string> = {
  // Suppliers
  'GET /suppliers': 'hrms.api.procurement.get_suppliers',
  'POST /suppliers': 'hrms.api.procurement.create_supplier',
  'GET /suppliers/:id': 'hrms.api.procurement.get_supplier',
  'PUT /suppliers/:id': 'hrms.api.procurement.update_supplier',
  'GET /suppliers/:id/metrics': 'hrms.api.procurement.get_supplier_metrics',

  // Purchase Orders
  'GET /purchase-orders': 'hrms.api.procurement.get_purchase_orders',
  'POST /purchase-orders': 'hrms.api.procurement.create_purchase_order',
  'GET /purchase-orders/pending-approvals': 'hrms.api.procurement.get_pending_po_approvals',
  'GET /purchase-orders/:id': 'hrms.api.procurement.get_purchase_order',
  'POST /purchase-orders/:id/submit': 'hrms.api.procurement.submit_po_for_approval',
  'POST /purchase-orders/:id/approve/mae': 'hrms.api.procurement.approve_po_mae',
  'POST /purchase-orders/:id/approve/butch': 'hrms.api.procurement.approve_po_butch',
  'POST /purchase-orders/:id/reject': 'hrms.api.procurement.reject_po',

  // Invoices
  'GET /invoices': 'hrms.api.procurement.get_invoices',
  'POST /invoices': 'hrms.api.procurement.create_invoice',
  'GET /invoices/:id': 'hrms.api.procurement.get_invoice',
  'POST /invoices/:id/verify': 'hrms.api.procurement.verify_invoice_match',
  'POST /invoices/:id/approve-variance': 'hrms.api.procurement.approve_invoice_variance',

  // Payment Requests
  'GET /payment-requests': 'hrms.api.procurement.get_payment_requests',
  'POST /payment-requests': 'hrms.api.procurement.create_payment_request',
  'GET /payment-requests/pending-approvals': 'hrms.api.procurement.get_pending_payment_approvals',
  'GET /payment-requests/:id': 'hrms.api.procurement.get_payment_request',
  'POST /payment-requests/:id/submit': 'hrms.api.procurement.submit_payment_for_approval',
  'POST /payment-requests/:id/approve/review': 'hrms.api.procurement.approve_payment_review',
  'POST /payment-requests/:id/approve/budget': 'hrms.api.procurement.approve_payment_budget',
  'POST /payment-requests/:id/approve/cfo': 'hrms.api.procurement.approve_payment_cfo',
  'POST /payment-requests/:id/approve/ceo': 'hrms.api.procurement.approve_payment_ceo',
  'POST /payment-requests/:id/reject': 'hrms.api.procurement.reject_payment_request',
  'POST /payment-requests/:id/complete': 'hrms.api.procurement.mark_payment_complete',

  
  // Phase 2 Endpoints
  'POST /advances/clear': 'hrms.api.procurement.tag_advance_to_gr',
  'POST /advances/undeliverable': 'hrms.api.procurement.mark_advance_undeliverable',
  'GET /soa': 'hrms.api.soa.get_soa_list',
  'GET /soa/detail': 'hrms.api.soa.get_soa',
  'POST /soa/send': 'hrms.api.soa.send_soa_to_store',
  'GET /billing/rates': 'hrms.api.billing.get_rates_for_approval',
  'POST /billing/rates/approve': 'hrms.api.billing.approve_rate',
  // Dashboard
  'GET /dashboard/kpis': 'hrms.api.procurement.get_dashboard_kpis',
  'GET /dashboard/outstanding-by-supplier': 'hrms.api.procurement.get_outstanding_by_supplier',
  'GET /dashboard/aging': 'hrms.api.procurement.get_aging_analysis',
  'GET /purchase-orders/or-aging-summary': 'hrms.api.procurement.get_or_aging_summary',
  'GET /dashboard/po-trend': 'hrms.api.procurement.get_monthly_po_trend',
  'GET /dashboard/payment-schedule': 'hrms.api.procurement.get_payment_schedule',
  'GET /dashboard/supplier-performance': 'hrms.api.procurement.get_supplier_performance',
};

// Match a route pattern
function matchRoute(method: string, path: string): { method: string; params: Record<string, string> } | null {
  const routeKey = `${method} ${path}`;

  // Direct match
  if (ROUTE_MAP[routeKey]) {
    return { method: ROUTE_MAP[routeKey], params: {} };
  }

  // Pattern match with :id
  for (const [pattern, frappeMethod] of Object.entries(ROUTE_MAP)) {
    const [patternMethod, patternPath] = pattern.split(' ');
    if (patternMethod !== method) continue;

    const patternParts = patternPath.split('/');
    const pathParts = path.split('/');

    if (patternParts.length !== pathParts.length) continue;

    const params: Record<string, string> = {};
    let match = true;

    for (let i = 0; i < patternParts.length; i++) {
      if (patternParts[i].startsWith(':')) {
        params[patternParts[i].slice(1)] = pathParts[i];
      } else if (patternParts[i] !== pathParts[i]) {
        match = false;
        break;
      }
    }

    if (match) {
      return { method: frappeMethod, params };
    }
  }

  return null;
}

// Call Frappe API
async function callFrappe(method: string, args: Record<string, any> = {}): Promise<Response> {
  const url = `${FRAPPE_URL}/api/method/${method}`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': getAuthHeader(),
    },
    body: JSON.stringify(args),
  });

  const data = await response.json();

  if (!response.ok) {
    return NextResponse.json(
      { error: data.exc || data.message || 'Frappe API error' },
      { status: response.status }
    );
  }

  // Frappe wraps response in { message: ... }
  return NextResponse.json(data.message ?? data);
}

// Main handler
export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const path = url.pathname.replace('/api/procurement', '') || '/';
  const searchParams = Object.fromEntries(url.searchParams);

  const match = matchRoute('GET', path);
  if (!match) {
    return NextResponse.json({ error: 'Route not found' }, { status: 404 });
  }

  return callFrappe(match.method, { ...searchParams, ...match.params });
}

export async function POST(request: NextRequest) {
  const url = new URL(request.url);
  const path = url.pathname.replace('/api/procurement', '') || '/';

  let body = {};
  try {
    body = await request.json();
  } catch {
    // Empty body is OK for some endpoints
  }

  const match = matchRoute('POST', path);
  if (!match) {
    return NextResponse.json({ error: 'Route not found' }, { status: 404 });
  }

  return callFrappe(match.method, { ...body, ...match.params });
}

export async function PUT(request: NextRequest) {
  const url = new URL(request.url);
  const path = url.pathname.replace('/api/procurement', '') || '/';

  let body = {};
  try {
    body = await request.json();
  } catch {
    // Empty body is OK
  }

  const match = matchRoute('PUT', path);
  if (!match) {
    return NextResponse.json({ error: 'Route not found' }, { status: 404 });
  }

  return callFrappe(match.method, { data: body, ...match.params });
}
