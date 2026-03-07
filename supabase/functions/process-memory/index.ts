/**
 * BEI Brain S023B — Edge Function: process-memory
 *
 * Receives a thought/memory, embeds it via OpenAI, extracts metadata
 * via Claude Haiku, and stores in the `memories` table.
 *
 * Features:
 * - Idempotency via idempotency_key (BLOCKER 2)
 * - Promise.allSettled for parallel embed + classify (BLOCKER 2)
 * - Circuit breaker: marks embedding_status on failure (BLOCKER 1)
 * - Graceful degradation: stores even if embedding/metadata fails
 */
import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY")!;
const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// Circuit breaker state (in-memory, resets on cold start)
let consecutiveEmbedFailures = 0;
const CIRCUIT_BREAKER_THRESHOLD = 5;

interface ProcessMemoryRequest {
  content: string;
  user_id: string;
  source?: string;
  tags?: string[];
  idempotency_key?: string;
}

async function generateEmbedding(text: string): Promise<number[] | null> {
  if (consecutiveEmbedFailures >= CIRCUIT_BREAKER_THRESHOLD) {
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
    consecutiveEmbedFailures = 0;
    return data.data[0].embedding;
  } catch (e) {
    consecutiveEmbedFailures++;
    console.error("Embedding failed:", e);
    return null;
  }
}

interface ExtractedMetadata {
  people: string[];
  topics: string[];
  action_items: string[];
  importance: number;
}

async function extractMetadata(
  text: string
): Promise<ExtractedMetadata | null> {
  try {
    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 300,
        messages: [
          {
            role: "user",
            content: `Extract from this thought:
- people mentioned (names as array)
- topics (e.g., procurement, hr, finance, ops, tech — as array)
- action_items (if any — as array of strings)
- importance (1-10, where 10 = critical business decision)
Return JSON only, no markdown.
Thought: "${text}"`,
          },
        ],
      }),
    });
    if (!resp.ok) {
      throw new Error(`Anthropic ${resp.status}: ${await resp.text()}`);
    }
    const data = await resp.json();
    // Strip markdown code blocks if present (Haiku sometimes wraps in ```json...```)
    let rawText = data.content[0].text.trim();
    if (rawText.startsWith("```")) {
      rawText = rawText.replace(/^```(?:json)?\s*/, "").replace(/\s*```$/, "");
    }
    const parsed = JSON.parse(rawText);
    // Validate structure
    return {
      people: Array.isArray(parsed.people) ? parsed.people : [],
      topics: Array.isArray(parsed.topics) ? parsed.topics : [],
      action_items: Array.isArray(parsed.action_items)
        ? parsed.action_items
        : [],
      importance:
        typeof parsed.importance === "number"
          ? Math.min(10, Math.max(1, parsed.importance))
          : 5,
    };
  } catch (e) {
    console.error("Metadata extraction failed:", e);
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
    const body: ProcessMemoryRequest = await req.json();
    const { content, user_id, source, tags, idempotency_key } = body;

    if (!content || !user_id) {
      return new Response(
        JSON.stringify({ error: "content and user_id required" }),
        { status: 400 }
      );
    }

    // Idempotency check (BLOCKER 2)
    if (idempotency_key) {
      const { data: existing } = await supabase
        .from("memories")
        .select("id")
        .eq("idempotency_key", idempotency_key)
        .maybeSingle();
      if (existing) {
        return new Response(
          JSON.stringify({
            ok: true,
            id: existing.id,
            deduplicated: true,
          }),
          { status: 200 }
        );
      }
    }

    // Parallel embed + classify using Promise.allSettled (BLOCKER 2)
    const [embedResult, metaResult] = await Promise.allSettled([
      generateEmbedding(content),
      extractMetadata(content),
    ]);

    const embedding =
      embedResult.status === "fulfilled" ? embedResult.value : null;
    const metadata =
      metaResult.status === "fulfilled" ? metaResult.value : null;

    // Determine embedding status (BLOCKER 1)
    let embeddingStatus: string;
    if (embedding) {
      embeddingStatus = "complete";
    } else if (consecutiveEmbedFailures >= CIRCUIT_BREAKER_THRESHOLD) {
      embeddingStatus = "pending"; // circuit breaker open — backfill later
    } else {
      embeddingStatus = "failed";
    }

    const row: Record<string, unknown> = {
      user_id,
      content,
      embedding,
      embedding_status: embeddingStatus,
      metadata: metadata
        ? { people: metadata.people, topics: metadata.topics, action_items: metadata.action_items }
        : {},
      topic_category: metadata?.topics?.[0] || null,
      source: source || "manual",
      importance_score: metadata?.importance || 5,
      idempotency_key: idempotency_key || null,
    };

    const { data, error } = await supabase
      .from("memories")
      .insert(row)
      .select("id")
      .single();

    if (error) {
      throw error;
    }

    return new Response(
      JSON.stringify({
        ok: true,
        id: data.id,
        embedding_status: embeddingStatus,
        metadata: metadata || {},
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (e) {
    console.error("process-memory error:", e);
    const errMsg = e instanceof Error ? e.message : JSON.stringify(e);
    return new Response(
      JSON.stringify({ error: errMsg }),
      { status: 500 }
    );
  }
});
