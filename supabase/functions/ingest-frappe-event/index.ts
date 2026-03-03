/**
 * BEI Brain S023B — Edge Function: ingest-frappe-event
 *
 * Receives Frappe doc_event payloads from brain_sync.py hook.
 * Conditionally embeds content (skips high-volume DocTypes).
 * Stores in `frappe_events` table.
 *
 * Features:
 * - Smart embedding decision per DocType volume tier
 * - Circuit breaker on OpenAI failures (BLOCKER 1)
 * - Graceful degradation: stores without embedding on failure
 */
import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// Circuit breaker
let consecutiveFailures = 0;
const CIRCUIT_BREAKER_THRESHOLD = 5;

interface FrappeEventPayload {
  doctype: string;
  docname: string;
  event_type: string;
  domain: string;
  flow: string;
  content: string;
  importance_score: number;
  actor: string;
  event_data: Record<string, unknown>;
  embedding_skipped?: boolean;
  hook_version?: string;
}

async function generateEmbedding(text: string): Promise<number[] | null> {
  if (consecutiveFailures >= CIRCUIT_BREAKER_THRESHOLD) {
    console.warn("Circuit breaker OPEN — skipping embedding");
    return null;
  }
  try {
    const resp = await fetch("https://api.openai.com/v1/embeddings", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        input: text,
        model: "text-embedding-3-small",
      }),
    });
    if (!resp.ok) {
      throw new Error(`OpenAI ${resp.status}: ${await resp.text()}`);
    }
    const data = await resp.json();
    consecutiveFailures = 0;
    return data.data[0].embedding;
  } catch (e) {
    consecutiveFailures++;
    console.error("Embedding failed:", e);
    return null;
  }
}

serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
      },
    });
  }

  try {
    const payload: FrappeEventPayload = await req.json();

    const {
      doctype,
      docname,
      event_type,
      domain,
      flow,
      content,
      importance_score,
      actor,
      event_data,
      embedding_skipped,
      hook_version,
    } = payload;

    if (!doctype || !docname || !event_type || !content) {
      return new Response(
        JSON.stringify({ error: "doctype, docname, event_type, content required" }),
        { status: 400 }
      );
    }

    // Determine if we should embed
    let embedding: number[] | null = null;
    let embeddingStatus: string;

    if (embedding_skipped) {
      embeddingStatus = "skipped";
    } else {
      embedding = await generateEmbedding(content);
      if (embedding) {
        embeddingStatus = "complete";
      } else if (consecutiveFailures >= CIRCUIT_BREAKER_THRESHOLD) {
        embeddingStatus = "pending";
      } else {
        embeddingStatus = "failed";
      }
    }

    const { error } = await supabase.from("frappe_events").insert({
      doctype,
      docname,
      event_type,
      domain,
      flow,
      content,
      embedding,
      embedding_status: embeddingStatus,
      event_data,
      actor,
      importance_score: Math.min(10, Math.max(1, importance_score || 5)),
      embedding_skipped: embedding_skipped || false,
      embedding_model: embedding ? "text-embedding-3-small" : null,
      hook_version: hook_version || "1.0",
    });

    if (error) {
      throw error;
    }

    return new Response(
      JSON.stringify({
        ok: true,
        docname,
        embedding_status: embeddingStatus,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (e) {
    console.error("ingest-frappe-event error:", e);
    return new Response(
      JSON.stringify({ error: String(e) }),
      { status: 500 }
    );
  }
});
