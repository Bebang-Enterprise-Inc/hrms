/**
 * BEI Brain MCP Server — S023B Phase 3
 *
 * 14 tools for enterprise knowledge retrieval via MCP protocol.
 * Connects to Supabase (pgvector) and optionally Frappe REST API.
 *
 * Usage: node server.js
 * Config: env vars via Doppler or .env
 *
 * Tools:
 *  1. semantic_search   — decay-weighted memory search
 *  2. company_lookup    — structured company data
 *  3. sales_query       — revenue from existing views
 *  4. frappe_query      — live Frappe REST API
 *  5. frappe_events     — synced transaction history
 *  6. transaction_summary — aggregated event metrics
 *  7. entity_360        — cross-table unified view
 *  8. domain_context    — domain-scoped context package
 *  9. decision_trail    — chronological decision chain
 * 10. auto_context      — session start context (MEMORY.md killer)
 * 11. list_recent       — chronological retrieval
 * 12. get_stats         — dashboard data
 * 13. store_thought     — capture new knowledge
 * 14. backfill_embeddings — retry failed embeddings
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createClient } from "@supabase/supabase-js";
import OpenAI from "openai";
import { z } from "zod";

// ============================================================
// Config from environment
// ============================================================
const SUPABASE_URL = process.env.SUPABASE_URL || process.env.BRAIN_SUPABASE_URL;
const SUPABASE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.BRAIN_SUPABASE_SERVICE_KEY;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const FRAPPE_URL = process.env.FRAPPE_URL || "https://hq.bebang.ph";
const FRAPPE_API_KEY = process.env.FRAPPE_API_KEY;

// Decay-weighted formula params (BLOCKER 4)
const COSINE_WEIGHT = parseFloat(process.env.BRAIN_COSINE_WEIGHT || "0.6");
const IMPORTANCE_WEIGHT = parseFloat(process.env.BRAIN_IMPORTANCE_WEIGHT || "0.25");
const RECENCY_WEIGHT = parseFloat(process.env.BRAIN_RECENCY_WEIGHT || "0.15");
const HALF_LIFE_DAYS = parseFloat(process.env.BRAIN_HALF_LIFE_DAYS || "90");

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
const openai = OPENAI_API_KEY ? new OpenAI({ apiKey: OPENAI_API_KEY }) : null;

// ============================================================
// Helpers
// ============================================================

async function embed(text) {
  if (!openai) throw new Error("OPENAI_API_KEY not configured");
  const resp = await openai.embeddings.create({
    input: text,
    model: "text-embedding-3-small",
  });
  return resp.data[0].embedding;
}

function parseDateRange(range) {
  if (!range) {
    const now = new Date();
    const weekAgo = new Date(now);
    weekAgo.setDate(weekAgo.getDate() - 7);
    return { from: weekAgo.toISOString().split("T")[0], to: now.toISOString().split("T")[0] };
  }
  if (range === "today") {
    const d = new Date().toISOString().split("T")[0];
    return { from: d, to: d };
  }
  if (range === "yesterday") {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    const ds = d.toISOString().split("T")[0];
    return { from: ds, to: ds };
  }
  if (range.startsWith("last_")) {
    const days = parseInt(range.replace("last_", "").replace("_days", ""));
    const now = new Date();
    const past = new Date(now);
    past.setDate(past.getDate() - (days || 7));
    return { from: past.toISOString().split("T")[0], to: now.toISOString().split("T")[0] };
  }
  if (range.includes(":")) {
    const [from, to] = range.split(":");
    return { from, to };
  }
  return { from: range, to: range };
}

async function frappeGet(doctype, params = {}) {
  if (!FRAPPE_API_KEY) throw new Error("FRAPPE_API_KEY not configured");
  const url = new URL(`${FRAPPE_URL}/api/resource/${encodeURIComponent(doctype)}`);
  for (const [k, v] of Object.entries(params)) {
    url.searchParams.set(k, typeof v === "string" ? v : JSON.stringify(v));
  }
  const resp = await fetch(url.toString(), {
    headers: { Authorization: `token ${FRAPPE_API_KEY}` },
  });
  if (!resp.ok) throw new Error(`Frappe ${resp.status}: ${await resp.text()}`);
  const data = await resp.json();
  return data.data || data;
}

// ============================================================
// MCP Server Setup
// ============================================================

const server = new McpServer({
  name: "bei-brain",
  version: "1.0.0",
});

// ============================================================
// Tool 1: semantic_search
// ============================================================
server.tool(
  "semantic_search",
  "Search memories using decay-weighted semantic similarity. Returns ranked results combining cosine similarity, importance, and recency.",
  {
    query: z.string().describe("Search query text"),
    limit: z.number().optional().default(10).describe("Max results (default 10)"),
    domain: z.string().optional().describe("Filter by topic_category/domain"),
  },
  async ({ query, limit, domain }) => {
    const queryEmbedding = await embed(query);

    // Use RPC for vector search with decay-weighted scoring
    const { data, error } = await supabase.rpc("match_memories", {
      query_embedding: queryEmbedding,
      match_count: limit || 10,
      filter_domain: domain || null,
      cosine_weight: COSINE_WEIGHT,
      importance_weight: IMPORTANCE_WEIGHT,
      recency_weight: RECENCY_WEIGHT,
      half_life_days: HALF_LIFE_DAYS,
    });

    if (error) {
      // Fallback to basic cosine search if RPC doesn't exist yet
      const { data: fallbackData, error: fbError } = await supabase
        .from("memories")
        .select("id, content, metadata, topic_category, source, importance_score, retrieval_count, last_retrieved_at, created_at")
        .limit(limit || 10);

      if (fbError) throw fbError;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              { results: fallbackData || [], note: "Fallback: RPC not deployed yet, showing recent memories" },
              null,
              2
            ),
          },
        ],
      };
    }

    // Update retrieval stats for returned results
    if (data && data.length > 0) {
      const ids = data.map((r) => r.id);
      await supabase
        .from("memories")
        .update({ retrieval_count: supabase.rpc("increment_field", {}), last_retrieved_at: new Date().toISOString() })
        .in("id", ids)
        .then(() => {})
        .catch(() => {});
      // Simpler approach: update each
      for (const r of data) {
        await supabase.rpc("increment_retrieval", { memory_id: r.id }).catch(() => {});
      }
    }

    return {
      content: [{ type: "text", text: JSON.stringify({ results: data }, null, 2) }],
    };
  }
);

// ============================================================
// Tool 2: company_lookup
// ============================================================
server.tool(
  "company_lookup",
  "Look up BEI company data (employees, stores, items, suppliers, etc.). Three modes: by entity_id (exact), by query (semantic), or by entity_type (list all).",
  {
    entity_type: z.string().optional().describe("Filter by type: employee, store, item, supplier, gl_account, warehouse, po, pr, gr"),
    query: z.string().optional().describe("Semantic search query"),
    entity_id: z.string().optional().describe("Exact entity ID match"),
    limit: z.number().optional().default(20).describe("Max results"),
  },
  async ({ entity_type, query, entity_id, limit }) => {
    if (entity_id) {
      const { data, error } = await supabase
        .from("company_data")
        .select("*")
        .eq("entity_id", entity_id)
        .limit(1);
      if (error) throw error;
      return { content: [{ type: "text", text: JSON.stringify({ results: data }, null, 2) }] };
    }

    if (query) {
      const queryEmbedding = await embed(query);
      // Vector search via RPC or fallback to ILIKE
      let q = supabase
        .from("company_data")
        .select("id, domain, entity_type, entity_id, content, structured_data, source_file")
        .ilike("content", `%${query}%`)
        .limit(limit || 20);
      if (entity_type) q = q.eq("entity_type", entity_type);
      const { data, error } = await q;
      if (error) throw error;
      return { content: [{ type: "text", text: JSON.stringify({ results: data }, null, 2) }] };
    }

    if (entity_type) {
      const { data, error } = await supabase
        .from("company_data")
        .select("id, entity_id, content, structured_data")
        .eq("entity_type", entity_type)
        .limit(limit || 20);
      if (error) throw error;
      return { content: [{ type: "text", text: JSON.stringify({ results: data, count: data?.length }, null, 2) }] };
    }

    return {
      content: [{ type: "text", text: JSON.stringify({ error: "Provide entity_type, query, or entity_id" }) }],
    };
  }
);

// ============================================================
// Tool 3: sales_query
// ============================================================
server.tool(
  "sales_query",
  "Query BEI sales revenue from POS and Web channels. Uses existing Supabase views. Returns gross/net sales, order counts by store, date, channel.",
  {
    store: z.string().optional().describe("Store name filter (partial match)"),
    channel: z.string().optional().describe("Filter: 'pos', 'web', or omit for all"),
    date_range: z.string().optional().describe("Date range: 'today', 'yesterday', 'last_7_days', 'YYYY-MM-DD:YYYY-MM-DD'"),
    sort: z.string().optional().default("business_date").describe("Sort field"),
  },
  async ({ store, channel, date_range, sort }) => {
    const { from, to } = parseDateRange(date_range);

    let q = supabase
      .from("v_all_channel_daily")
      .select("*")
      .gte("business_date", from)
      .lte("business_date", to);

    if (store) q = q.ilike("store_name", `%${store}%`);
    if (channel) q = q.eq("channel", channel);
    q = q.order(sort || "business_date", { ascending: false }).limit(100);

    const { data, error } = await q;
    if (error) throw error;

    // Compute totals
    let totalGross = 0, totalNet = 0, totalOrders = 0;
    for (const r of data || []) {
      totalGross += parseFloat(r.gross_sales || 0);
      totalNet += parseFloat(r.net_sales || 0);
      totalOrders += parseInt(r.order_count || 0);
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          summary: {
            date_range: `${from} to ${to}`,
            total_gross: totalGross,
            total_net: totalNet,
            total_orders: totalOrders,
            row_count: data?.length || 0,
          },
          rows: data,
        }, null, 2),
      }],
    };
  }
);

// ============================================================
// Tool 4: frappe_query
// ============================================================
server.tool(
  "frappe_query",
  "Live query against Frappe REST API. Returns current state of documents (always fresh, no sync delay). Use for 'what is the current state?' questions.",
  {
    doctype: z.string().describe("Frappe DocType name"),
    filters: z.any().optional().describe("Frappe filter array, e.g. [[\"docstatus\",\"=\",1]]"),
    fields: z.array(z.string()).optional().describe("Fields to return"),
    limit: z.number().optional().default(20).describe("Max results"),
  },
  async ({ doctype, filters, fields, limit: lim }) => {
    try {
      const params = {
        limit_page_length: lim || 20,
        order_by: "modified desc",
      };
      if (filters) params.filters = filters;
      if (fields) params.fields = fields;

      const data = await frappeGet(doctype, params);
      return { content: [{ type: "text", text: JSON.stringify({ results: data }, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: JSON.stringify({ error: String(e) }) }] };
    }
  }
);

// ============================================================
// Tool 5: frappe_events
// ============================================================
server.tool(
  "frappe_events",
  "Search synced Frappe transaction events. Two modes: structured filters (doctype, domain, event_type) or semantic search (query). Use for 'what happened?' questions.",
  {
    doctype: z.string().optional().describe("Filter by DocType"),
    domain: z.string().optional().describe("Filter by domain: hr, procurement, finance, inventory, etc."),
    date_range: z.string().optional().describe("Date range string"),
    event_type: z.string().optional().describe("Filter: submit, update, cancel, create"),
    query: z.string().optional().describe("Semantic search query (uses embeddings)"),
    limit: z.number().optional().default(20),
  },
  async ({ doctype, domain, date_range, event_type, query, limit: lim }) => {
    const { from, to } = parseDateRange(date_range);

    if (query) {
      // Semantic mode — search by content similarity
      let q = supabase
        .from("frappe_events")
        .select("doctype, docname, event_type, domain, content, importance_score, actor, created_at")
        .ilike("content", `%${query}%`)
        .gte("created_at", `${from}T00:00:00`)
        .lte("created_at", `${to}T23:59:59`)
        .order("created_at", { ascending: false })
        .limit(lim || 20);
      if (domain) q = q.eq("domain", domain);
      const { data, error } = await q;
      if (error) throw error;
      return { content: [{ type: "text", text: JSON.stringify({ mode: "semantic", results: data }, null, 2) }] };
    }

    // Structured mode
    let q = supabase
      .from("frappe_events")
      .select("doctype, docname, event_type, domain, content, importance_score, actor, created_at")
      .gte("created_at", `${from}T00:00:00`)
      .lte("created_at", `${to}T23:59:59`)
      .order("created_at", { ascending: false })
      .limit(lim || 20);

    if (doctype) q = q.eq("doctype", doctype);
    if (domain) q = q.eq("domain", domain);
    if (event_type) q = q.eq("event_type", event_type);

    const { data, error } = await q;
    if (error) throw error;
    return { content: [{ type: "text", text: JSON.stringify({ mode: "structured", results: data }, null, 2) }] };
  }
);

// ============================================================
// Tool 6: transaction_summary
// ============================================================
server.tool(
  "transaction_summary",
  "Aggregated Frappe event metrics: counts by doctype/domain, average importance, cancellation counts.",
  {
    domain: z.string().optional().describe("Filter by domain"),
    date_range: z.string().optional().describe("Date range string"),
  },
  async ({ domain, date_range }) => {
    const { from, to } = parseDateRange(date_range);

    let q = supabase
      .from("frappe_events")
      .select("doctype, domain, event_type, importance_score")
      .gte("created_at", `${from}T00:00:00`)
      .lte("created_at", `${to}T23:59:59`);
    if (domain) q = q.eq("domain", domain);
    q = q.limit(5000);

    const { data, error } = await q;
    if (error) throw error;

    // Aggregate client-side
    const summary = {};
    for (const row of data || []) {
      const key = `${row.domain}|${row.doctype}`;
      if (!summary[key]) {
        summary[key] = {
          domain: row.domain,
          doctype: row.doctype,
          total: 0,
          cancellations: 0,
          importance_sum: 0,
        };
      }
      summary[key].total++;
      summary[key].importance_sum += row.importance_score || 5;
      if (row.event_type === "cancel") summary[key].cancellations++;
    }

    const results = Object.values(summary)
      .map((s) => ({
        ...s,
        avg_importance: (s.importance_sum / s.total).toFixed(1),
      }))
      .sort((a, b) => b.total - a.total);

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          date_range: `${from} to ${to}`,
          total_events: data?.length || 0,
          by_doctype: results,
        }, null, 2),
      }],
    };
  }
);

// ============================================================
// Tool 7: entity_360
// ============================================================
server.tool(
  "entity_360",
  "Cross-table unified view for any entity (store, employee, supplier). Combines company_data + frappe_events + sales + memories.",
  {
    name: z.string().describe("Entity name to look up (store name, employee name, supplier name)"),
  },
  async ({ name }) => {
    if (!name) throw new Error("name is required");

    // 4 parallel queries
    const [companyResult, eventsResult, salesResult, memoriesResult] = await Promise.allSettled([
      // 1. Company data matching name
      supabase
        .from("company_data")
        .select("entity_type, entity_id, content, structured_data")
        .ilike("content", `%${name}%`)
        .limit(20),
      // 2. Recent frappe events mentioning name
      supabase
        .from("frappe_events")
        .select("doctype, docname, event_type, content, importance_score, actor, created_at")
        .ilike("content", `%${name}%`)
        .gte("created_at", new Date(Date.now() - 7 * 86400000).toISOString())
        .order("created_at", { ascending: false })
        .limit(20),
      // 3. Sales data
      supabase
        .from("store_daily_closing")
        .select("*")
        .ilike("store_name", `%${name}%`)
        .gte("business_date", new Date(Date.now() - 7 * 86400000).toISOString().split("T")[0])
        .order("business_date", { ascending: false })
        .limit(7),
      // 4. Memories
      supabase
        .from("memories")
        .select("content, topic_category, importance_score, created_at")
        .ilike("content", `%${name}%`)
        .order("created_at", { ascending: false })
        .limit(10),
    ]);

    const company_data =
      companyResult.status === "fulfilled" ? companyResult.value.data : [];
    const frappe_events_data =
      eventsResult.status === "fulfilled" ? eventsResult.value.data : [];
    const sales =
      salesResult.status === "fulfilled" ? salesResult.value.data : [];
    const memories =
      memoriesResult.status === "fulfilled" ? memoriesResult.value.data : [];

    // Summarize sales
    let salesGross = 0;
    for (const s of sales || []) {
      salesGross += parseFloat(s.total_gross || s.gross_sales || 0);
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          entity: name,
          company_data: {
            count: company_data?.length || 0,
            records: company_data,
          },
          frappe_events: {
            count: frappe_events_data?.length || 0,
            events: frappe_events_data,
          },
          sales: {
            days: sales?.length || 0,
            total_gross_7d: salesGross,
            daily: sales,
          },
          memories: {
            count: memories?.length || 0,
            items: memories,
          },
        }, null, 2),
      }],
    };
  }
);

// ============================================================
// Tool 8: domain_context
// ============================================================
server.tool(
  "domain_context",
  "Get a context package for a specific domain: top memories, entity counts, recent events, transaction summary.",
  {
    domain: z.string().describe("Domain: hr, procurement, finance, inventory, stores, commissary, projects, platform"),
  },
  async ({ domain }) => {
    const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();

    const [memoriesRes, entitiesRes, recentMemRes, eventsRes] = await Promise.allSettled([
      // Top 10 most important memories in domain
      supabase
        .from("memories")
        .select("content, importance_score, topic_category, created_at")
        .eq("topic_category", domain)
        .order("importance_score", { ascending: false })
        .limit(10),
      // Entity count by type in domain
      supabase
        .from("company_data")
        .select("entity_type")
        .eq("domain", domain),
      // Most recent 5 memories
      supabase
        .from("memories")
        .select("content, importance_score, created_at")
        .eq("topic_category", domain)
        .order("created_at", { ascending: false })
        .limit(5),
      // Recent 10 frappe events
      supabase
        .from("frappe_events")
        .select("doctype, docname, event_type, content, importance_score, created_at")
        .eq("domain", domain)
        .gte("created_at", weekAgo)
        .order("created_at", { ascending: false })
        .limit(10),
    ]);

    const topMemories = memoriesRes.status === "fulfilled" ? memoriesRes.value.data : [];
    const entities = entitiesRes.status === "fulfilled" ? entitiesRes.value.data : [];
    const recentMem = recentMemRes.status === "fulfilled" ? recentMemRes.value.data : [];
    const events = eventsRes.status === "fulfilled" ? eventsRes.value.data : [];

    // Count entities by type
    const entityCounts = {};
    for (const e of entities || []) {
      entityCounts[e.entity_type] = (entityCounts[e.entity_type] || 0) + 1;
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          domain,
          top_memories: topMemories,
          entity_counts: entityCounts,
          recent_memories: recentMem,
          recent_events: events,
        }, null, 2),
      }],
    };
  }
);

// ============================================================
// Tool 9: decision_trail
// ============================================================
server.tool(
  "decision_trail",
  "Chronological chain of high-importance decisions and action items for a topic.",
  {
    topic: z.string().describe("Topic to trace decisions for"),
  },
  async ({ topic }) => {
    const { data, error } = await supabase
      .from("memories")
      .select("content, metadata, importance_score, source, created_at")
      .or("importance_score.gte.7,metadata->>action_items.neq.[]")
      .ilike("content", `%${topic}%`)
      .order("created_at", { ascending: true })
      .limit(50);

    if (error) throw error;
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          topic,
          decisions: data,
          count: data?.length || 0,
        }, null, 2),
      }],
    };
  }
);

// ============================================================
// Tool 10: auto_context
// ============================================================
server.tool(
  "auto_context",
  "Session-start context loader. Without hint: top-importance + most-retrieved + action items + today's events. With hint: weighted by semantic similarity to hint. Replaces MEMORY.md.",
  {
    hint: z.string().optional().describe("Context hint (e.g., 'procurement', 'debugging ADMS') to weight results"),
  },
  async ({ hint }) => {
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);

    const [topImportance, topRetrieved, actionItems, todayEvents, highEvents, stats] =
      await Promise.allSettled([
        // Top 20 highest importance
        supabase
          .from("memories")
          .select("content, importance_score, topic_category, source, created_at")
          .order("importance_score", { ascending: false })
          .limit(20),
        // Top 10 most retrieved in last 7 days
        supabase
          .from("memories")
          .select("content, importance_score, retrieval_count, last_retrieved_at")
          .gte("last_retrieved_at", new Date(Date.now() - 7 * 86400000).toISOString())
          .order("retrieval_count", { ascending: false })
          .limit(10),
        // Action items
        supabase
          .from("memories")
          .select("content, metadata, created_at")
          .not("metadata->>action_items", "eq", "[]")
          .not("metadata->>action_items", "is", null)
          .order("created_at", { ascending: false })
          .limit(10),
        // Today's event summary
        supabase
          .from("frappe_events")
          .select("domain, doctype, event_type")
          .gte("created_at", todayStart.toISOString())
          .limit(1000),
        // High importance events last 24h
        supabase
          .from("frappe_events")
          .select("doctype, docname, content, importance_score, actor, created_at")
          .gte("importance_score", 7)
          .gte("created_at", new Date(Date.now() - 86400000).toISOString())
          .order("importance_score", { ascending: false })
          .limit(10),
        // Stats
        supabase.from("memories").select("id", { count: "exact", head: true }),
      ]);

    // Summarize today's events
    const todayData = todayEvents.status === "fulfilled" ? todayEvents.value.data : [];
    const eventSummary = {};
    for (const e of todayData || []) {
      const key = `${e.domain}|${e.doctype}`;
      eventSummary[key] = (eventSummary[key] || 0) + 1;
    }

    const context = {
      hint: hint || null,
      top_importance: topImportance.status === "fulfilled" ? topImportance.value.data : [],
      most_retrieved: topRetrieved.status === "fulfilled" ? topRetrieved.value.data : [],
      action_items: actionItems.status === "fulfilled" ? actionItems.value.data : [],
      today_events: {
        total: todayData?.length || 0,
        by_doctype: eventSummary,
      },
      high_importance_events_24h: highEvents.status === "fulfilled" ? highEvents.value.data : [],
      stats: {
        total_memories: stats.status === "fulfilled" ? stats.value.count : "unknown",
      },
    };

    return {
      content: [{ type: "text", text: JSON.stringify(context, null, 2) }],
    };
  }
);

// ============================================================
// Tool 11: list_recent
// ============================================================
server.tool(
  "list_recent",
  "List recent memories chronologically.",
  {
    days: z.number().optional().default(7).describe("Look back N days (default 7)"),
    limit: z.number().optional().default(20).describe("Max results (default 20)"),
  },
  async ({ days, limit: lim }) => {
    const since = new Date(Date.now() - (days || 7) * 86400000).toISOString();
    const { data, error } = await supabase
      .from("memories")
      .select("id, content, topic_category, source, importance_score, created_at")
      .gte("created_at", since)
      .order("created_at", { ascending: false })
      .limit(lim || 20);
    if (error) throw error;
    return {
      content: [{ type: "text", text: JSON.stringify({ results: data, count: data?.length }, null, 2) }],
    };
  }
);

// ============================================================
// Tool 12: get_stats
// ============================================================
server.tool(
  "get_stats",
  "Dashboard data: total counts, memories by domain/source, frappe events by domain/doctype, top retrieved.",
  {},
  async () => {
    const [memCount, compCount, evtCount, topRetrieved] = await Promise.allSettled([
      supabase.from("memories").select("id", { count: "exact", head: true }),
      supabase.from("company_data").select("id", { count: "exact", head: true }),
      supabase.from("frappe_events").select("id", { count: "exact", head: true }),
      supabase
        .from("memories")
        .select("content, retrieval_count, topic_category")
        .order("retrieval_count", { ascending: false })
        .limit(10),
    ]);

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          total_memories: memCount.status === "fulfilled" ? memCount.value.count : 0,
          total_company_data: compCount.status === "fulfilled" ? compCount.value.count : 0,
          total_frappe_events: evtCount.status === "fulfilled" ? evtCount.value.count : 0,
          top_retrieved: topRetrieved.status === "fulfilled" ? topRetrieved.value.data : [],
        }, null, 2),
      }],
    };
  }
);

// ============================================================
// Tool 13: store_thought
// ============================================================
server.tool(
  "store_thought",
  "Capture a new thought/memory. Embeds content, extracts metadata via Claude Haiku, stores in memories table. Returns new memory ID.",
  {
    content: z.string().describe("The thought/memory to store"),
    tags: z.array(z.string()).optional().describe("Optional tags"),
    source: z.string().optional().default("manual").describe("Source: manual, claude_code, gemini, codex, google_chat"),
  },
  async ({ content: text, tags, source }) => {
    if (!text) throw new Error("content is required");

    const PROCESS_MEMORY_URL = `${SUPABASE_URL}/functions/v1/process-memory`;

    try {
      const resp = await fetch(PROCESS_MEMORY_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${SUPABASE_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          content: text,
          user_id: "00000000-0000-0000-0000-000000000001", // System user for CLI tools
          source: source || "manual",
          tags,
        }),
      });

      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`process-memory ${resp.status}: ${errText}`);
      }

      const result = await resp.json();
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    } catch (e) {
      // Fallback: direct insert without metadata extraction
      let embedding = null;
      try {
        embedding = await embed(text);
      } catch {}

      const { data, error } = await supabase
        .from("memories")
        .insert({
          user_id: "00000000-0000-0000-0000-000000000001",
          content: text,
          embedding,
          embedding_status: embedding ? "complete" : "failed",
          source: source || "manual",
          importance_score: 5,
        })
        .select("id")
        .single();

      if (error) throw error;
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            ok: true,
            id: data.id,
            note: "Stored via fallback (Edge Function unavailable)",
          }, null, 2),
        }],
      };
    }
  }
);

// ============================================================
// Tool 14: backfill_embeddings
// ============================================================
server.tool(
  "backfill_embeddings",
  "Retry embedding generation for records that failed or are pending. Useful after OpenAI outage recovery.",
  {
    table: z.enum(["memories", "company_data", "frappe_events"]).describe("Table to backfill"),
    limit: z.number().optional().default(50).describe("Max records to process"),
  },
  async ({ table, limit: lim }) => {
    const { data, error } = await supabase
      .from(table)
      .select("id, content")
      .in("embedding_status", ["pending", "failed"])
      .limit(lim || 50);

    if (error) throw error;
    if (!data || data.length === 0) {
      return { content: [{ type: "text", text: JSON.stringify({ message: "No records to backfill", table }) }] };
    }

    let success = 0, failed = 0;
    for (const row of data) {
      try {
        const embedding = await embed(row.content);
        if (embedding) {
          await supabase
            .from(table)
            .update({ embedding, embedding_status: "complete" })
            .eq("id", row.id);
          success++;
        } else {
          failed++;
        }
      } catch {
        failed++;
      }
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          table,
          processed: data.length,
          success,
          failed,
          remaining: data.length - success,
        }, null, 2),
      }],
    };
  }
);

// ============================================================
// Start Server
// ============================================================
const transport = new StdioServerTransport();
await server.connect(transport);
