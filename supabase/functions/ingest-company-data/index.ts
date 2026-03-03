/**
 * BEI Brain S023B — Edge Function: ingest-company-data
 *
 * Receives batch of company data rows, embeds content,
 * upserts to `company_data` table with change detection via row_hash.
 *
 * Features:
 * - row_hash change detection (skip unchanged rows)
 * - Circuit breaker on OpenAI failures
 * - Batch processing with per-row error isolation
 */
import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

let consecutiveFailures = 0;
const CIRCUIT_BREAKER_THRESHOLD = 5;

interface CompanyDataRow {
  domain: string;
  entity_type: string;
  entity_id: string;
  content: string;
  structured_data: Record<string, unknown>;
  source_file: string;
  row_hash: string;
}

async function generateEmbedding(text: string): Promise<number[] | null> {
  if (consecutiveFailures >= CIRCUIT_BREAKER_THRESHOLD) {
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
      throw new Error(`OpenAI ${resp.status}`);
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
    const { rows }: { rows: CompanyDataRow[] } = await req.json();

    if (!rows || !Array.isArray(rows)) {
      return new Response(
        JSON.stringify({ error: "rows array required" }),
        { status: 400 }
      );
    }

    let inserted = 0;
    let skipped = 0;
    let failed = 0;

    for (const row of rows) {
      try {
        // Check if row already exists with same hash
        const { data: existing } = await supabase
          .from("company_data")
          .select("row_hash")
          .eq("entity_type", row.entity_type)
          .eq("entity_id", row.entity_id)
          .maybeSingle();

        if (existing?.row_hash === row.row_hash) {
          skipped++;
          continue;
        }

        // Generate embedding
        const embedding = await generateEmbedding(row.content);
        const embeddingStatus = embedding
          ? "complete"
          : consecutiveFailures >= CIRCUIT_BREAKER_THRESHOLD
            ? "pending"
            : "failed";

        const { error } = await supabase.from("company_data").upsert(
          {
            domain: row.domain,
            entity_type: row.entity_type,
            entity_id: row.entity_id,
            content: row.content,
            embedding,
            embedding_status: embeddingStatus,
            structured_data: row.structured_data,
            source_file: row.source_file,
            row_hash: row.row_hash,
          },
          { onConflict: "entity_type,entity_id" }
        );

        if (error) {
          console.error(`Row ${row.entity_id} failed:`, error);
          failed++;
        } else {
          inserted++;
        }
      } catch (e) {
        console.error(`Row ${row.entity_id} error:`, e);
        failed++;
      }
    }

    return new Response(
      JSON.stringify({
        ok: true,
        total: rows.length,
        inserted,
        skipped,
        failed,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (e) {
    console.error("ingest-company-data error:", e);
    return new Response(
      JSON.stringify({ error: String(e) }),
      { status: 500 }
    );
  }
});
