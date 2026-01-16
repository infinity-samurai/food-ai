/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type JobStatus = "queued" | "in_progress" | "done" | "failed";

type Nutrition = {
  calories_kcal?: number;
  carbs_g?: number;
  protein_g?: number;
  fat_g?: number;
  sat_fat_g?: number;
  fiber_g?: number;
  sugar_g?: number;
  sodium_mg?: number;
  cholesterol_mg?: number;
  vitamin_c_mg?: number;
  iron_mg?: number;
};

type NotFoodResult = {
  status?: "done";
  is_food: false;
  message?: string;
  confidence?: number;
};

type FoodResult = {
  status?: "done";
  is_food: true;
  dish?: string;
  model_dish_guess?: string;
  confidence?: number;
  portion?: { label?: string; grams_estimate?: number };
  nutrition?: Nutrition;
  macro_percent_of_calories?: { carbs_pct?: number; protein_pct?: number; fat_pct?: number };
  daily_value_percent?: Record<string, number | undefined>;
  ingredients?: string[];
  potential_allergens?: string[];
  warning?: string;
  notes?: string[];
  description?: string;
  health_note?: string;
};

type AnalysisResult = NotFoodResult | FoodResult;

type JobResponse = {
  jobId: string;
  status: JobStatus;
  error?: string | null;
  result?: AnalysisResult | null;
};

function apiBase() {
  return process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
}

function classNames(...xs: Array<string | false | null | undefined>) {
  return xs.filter(Boolean).join(" ");
}

function pct(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "-";
  // Clamp to [0, 1] in case a backend/model returns an out-of-range value.
  const c = Math.max(0, Math.min(1, v));
  return `${Math.round(c * 100)}%`;
}

function numberOrDash(v: unknown, unit?: string) {
  const n =
    typeof v === "number"
      ? v
      : typeof v === "string"
        ? Number(v)
        : Number.NaN;
  if (!Number.isFinite(n)) return "-";
  if (unit === "mg") return `${Math.round(n)}mg`;
  if (unit === "kcal") return `${Math.round(n)}`;
  return `${Math.round(n * 10) / 10}${unit ?? ""}`;
}

function errMessage(e: unknown) {
  if (e instanceof Error) return e.message;
  return String(e);
}

async function presignOrLocalUpload(file: File): Promise<{ key: string; source: "s3" | "local" }> {
  // Local upload first (your current requirement).
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${apiBase()}/v1/uploads/local`, { method: "POST", body: form });
  if (!res.ok) throw new Error("Local upload failed");
  const j = await res.json();
  return { key: j.key as string, source: "local" };
}

async function uploadFromUrl(url: string): Promise<{ key: string; source: "local" }> {
  const res = await fetch(`${apiBase()}/v1/uploads/from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error("URL upload failed");
  const j = await res.json();
  return { key: j.key as string, source: "local" };
}

async function createAnalyzeJob(key: string, source: "s3" | "local" | "url") {
  const res = await fetch(`${apiBase()}/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, source }),
  });
  if (!res.ok) throw new Error("Analyze request failed");
  return (await res.json()) as { jobId: string; status: JobStatus };
}

async function fetchJob(jobId: string): Promise<JobResponse> {
  const res = await fetch(`${apiBase()}/v1/jobs/${jobId}`);
  if (!res.ok) throw new Error("Failed to fetch job");
  return (await res.json()) as JobResponse;
}

function StatCard(props: { label: string; value: string; highlight?: boolean }) {
  return (
    <div
      className={classNames(
        "rounded-xl border border-zinc-200 bg-white px-4 py-3",
        props.highlight && "bg-sky-500 text-white border-sky-500"
      )}
    >
      <div className={classNames("text-[10px] font-semibold tracking-wide uppercase", props.highlight ? "text-white/90" : "text-zinc-500")}>
        {props.label}
      </div>
      <div className="mt-1 text-lg font-semibold">{props.value}</div>
    </div>
  );
}

function LoadingOverlay(props: { show: boolean }) {
  if (!props.show) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white">
      <div className="flex w-full max-w-sm flex-col items-center gap-4 px-6">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-zinc-200 border-t-sky-500" />
        <div className="text-sm text-zinc-500">Analyzing your food image...</div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100">
          <div className="h-full w-1/2 animate-[progress_1.1s_ease-in-out_infinite] rounded-full bg-sky-500" />
        </div>
      </div>
      <style jsx global>{`
        @keyframes progress {
          0% {
            transform: translateX(-120%);
          }
          50% {
            transform: translateX(40%);
          }
          100% {
            transform: translateX(220%);
          }
        }
      `}</style>
    </div>
  );
}

function AnalyzerPage() {
  const [mode, setMode] = useState<"upload" | "url">("upload");
  const [imageUrl, setImageUrl] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploadKey, setUploadKey] = useState<string | null>(null);
  const [uploadSource, setUploadSource] = useState<"s3" | "local" | "url" | null>(null);

  const [job, setJob] = useState<JobResponse | null>(null);
  const [busy, setBusy] = useState<"idle" | "uploading" | "analyzing">("idle");
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);
  const sseRef = useRef<EventSource | null>(null);

  const canAnalyze = useMemo(() => Boolean(uploadKey && uploadSource && busy === "idle"), [uploadKey, uploadSource, busy]);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      if (sseRef.current) sseRef.current.close();
    };
  }, []);

  function clearAll() {
    setImageUrl("");
    setPreviewUrl(null);
    setUploadKey(null);
    setUploadSource(null);
    setJob(null);
    setBusy("idle");
    setError(null);
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = null;
    if (sseRef.current) sseRef.current.close();
    sseRef.current = null;
  }

  async function onPickFile(f: File | null) {
    clearAll();
    if (!f) return;
    setPreviewUrl(URL.createObjectURL(f));
    setBusy("uploading");
    try {
      const up = await presignOrLocalUpload(f);
      setUploadKey(up.key);
      setUploadSource(up.source);
      setBusy("idle");
    } catch (e: unknown) {
      setError(errMessage(e) ?? "Upload failed");
      setBusy("idle");
    }
  }

  async function onLoadUrl() {
    clearAll();
    if (!imageUrl.trim()) return;
    setPreviewUrl(imageUrl.trim());
    setBusy("uploading");
    try {
      const up = await uploadFromUrl(imageUrl.trim());
      setUploadKey(up.key);
      setUploadSource(up.source);
      setBusy("idle");
    } catch (e: unknown) {
      setError(errMessage(e) ?? "URL load failed");
      setBusy("idle");
    }
  }

  async function onAnalyze() {
    if (!uploadKey || !uploadSource) return;
    setError(null);
    setBusy("analyzing");
    try {
      const created = await createAnalyzeJob(uploadKey, uploadSource);
      setJob({ jobId: created.jobId, status: created.status });

      // Prefer SSE to avoid repeated API calls.
      try {
        if (sseRef.current) sseRef.current.close();
        const es = new EventSource(`${apiBase()}/v1/jobs/${created.jobId}/events`);
        sseRef.current = es;

        es.onmessage = (evt) => {
          try {
            const data = JSON.parse(evt.data) as JobResponse;
            setJob(data);
            if (data.status === "done" || data.status === "failed") {
              setBusy("idle");
              es.close();
              if (sseRef.current === es) sseRef.current = null;
            }
          } catch {
            // Ignore parse errors; server will send next event.
          }
        };

        es.onerror = async () => {
          // Fallback to polling if SSE isn't supported (proxy, CORS, etc).
          es.close();
          if (sseRef.current === es) sseRef.current = null;

          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = window.setInterval(async () => {
            try {
              const j = await fetchJob(created.jobId);
              setJob(j);
              if (j.status === "done" || j.status === "failed") {
                setBusy("idle");
                if (pollRef.current) window.clearInterval(pollRef.current);
                pollRef.current = null;
              }
            } catch (e: unknown) {
              setError(errMessage(e) ?? "Polling failed");
              setBusy("idle");
              if (pollRef.current) window.clearInterval(pollRef.current);
              pollRef.current = null;
            }
          }, 800);
        };
      } catch {
        // If EventSource fails immediately, fallback to polling.
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = window.setInterval(async () => {
          try {
            const j = await fetchJob(created.jobId);
            setJob(j);
            if (j.status === "done" || j.status === "failed") {
              setBusy("idle");
              if (pollRef.current) window.clearInterval(pollRef.current);
              pollRef.current = null;
            }
          } catch (e: unknown) {
            setError(errMessage(e) ?? "Polling failed");
            setBusy("idle");
            if (pollRef.current) window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }, 800);
      }
    } catch (e: unknown) {
      setError(errMessage(e) ?? "Analyze failed");
      setBusy("idle");
    }
  }

  const result = job?.result;
  const isFood = result?.is_food === true;
  const notFood = result?.is_food === false;
  const showLoading = busy === "analyzing" || job?.status === "queued" || job?.status === "in_progress";

  return (
    <div className="min-h-screen bg-white">
      <LoadingOverlay show={showLoading} />
      <main className="mx-auto w-full max-w-3xl px-4 py-14">
        <div className="text-center">
          <div className="text-3xl font-semibold tracking-tight text-sky-500">analyze.food</div>
          <div className="mt-2 text-sm text-zinc-500">Upload a food image to get nutritional analysis estimate</div>
        </div>

        <div className="mt-10 flex justify-center gap-3">
          <button
            className={classNames(
              "h-10 rounded-xl px-5 text-sm font-medium border",
              mode === "upload" ? "bg-sky-500 text-white border-sky-500" : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-50"
            )}
            onClick={() => {
              clearAll();
              setMode("upload");
            }}
          >
            Upload File
          </button>
          <button
            className={classNames(
              "h-10 rounded-xl px-5 text-sm font-medium border",
              mode === "url" ? "bg-sky-500 text-white border-sky-500" : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-50"
            )}
            onClick={() => {
              clearAll();
              setMode("url");
            }}
          >
            Enter URL
          </button>
        </div>

        <div className="mt-8 rounded-2xl border border-dashed border-zinc-200 p-10">
          {mode === "upload" ? (
            <div className="text-center">
              <div className="text-base font-medium text-zinc-900">Upload food image</div>
              <div className="mt-4 inline-flex items-center justify-center">
                <label className={classNames("inline-flex cursor-pointer items-center justify-center rounded-xl bg-sky-500 px-6 py-3 text-white text-sm font-medium", busy === "uploading" && "opacity-60 cursor-not-allowed")}>
                  Choose File
                  <input
                    className="hidden"
                    type="file"
                    accept="image/*"
                    disabled={busy === "uploading"}
                    onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
                  />
                </label>
              </div>
            </div>
          ) : (
            <div className="text-center">
              <div className="text-base font-medium text-zinc-900">Enter image URL</div>
              <div className="mt-4 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
                <input
                  className="h-10 w-full max-w-md rounded-xl border border-zinc-200 px-3 text-sm outline-none focus:ring-2 focus:ring-sky-200"
                  placeholder="https://example.com/image.jpg"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                />
                <button
                  className={classNames("h-10 rounded-xl bg-sky-500 px-5 text-sm font-medium text-white", busy === "uploading" && "opacity-60")}
                  onClick={onLoadUrl}
                  disabled={busy === "uploading"}
                >
                  Load Image
                </button>
              </div>
            </div>
          )}
        </div>

        {previewUrl && (
          <div className="mt-8 flex flex-col items-center gap-4">
            <img src={previewUrl} alt="Preview" className="h-48 w-auto rounded-xl border border-zinc-200 object-cover" />
            <div className="flex gap-3">
              <button
                className={classNames("h-11 rounded-xl bg-sky-500 px-6 text-sm font-medium text-white", !canAnalyze && "opacity-60")}
                disabled={!canAnalyze}
                onClick={onAnalyze}
              >
                {busy === "analyzing" ? "Analyzing..." : "Analyze Nutrition"}
              </button>
              <button className="h-11 rounded-xl border border-zinc-200 bg-white px-6 text-sm font-medium text-zinc-700 hover:bg-zinc-50" onClick={clearAll}>
                Clear
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {job && (job.status === "queued" || job.status === "in_progress") && (
          <div className="mt-6 text-center text-sm text-zinc-500">Analyzing your food image...</div>
        )}

        {job?.status === "failed" && (
          <div className="mt-6 rounded-xl border border-zinc-200 bg-white px-4 py-4">
            <div className="text-lg font-semibold text-zinc-900">Analysis Failed</div>
            <div className="mt-2 text-sm text-zinc-600">{job.error ?? "Unknown error"}</div>
            <div className="mt-4">
              <button className="h-10 rounded-xl bg-sky-500 px-5 text-sm font-medium text-white" onClick={onAnalyze} disabled={busy !== "idle" || !uploadKey}>
                Try Again
              </button>
            </div>
          </div>
        )}

        {result && (
          <div className="mt-10">
            <div className="mb-4 text-left text-lg font-semibold text-zinc-900">Nutritional Information</div>

            {notFood && (
              <div className="rounded-xl border border-zinc-200 bg-white px-4 py-4">
                <div className="text-sm text-zinc-700">
                  <span className="font-semibold">Result:</span> {result.message ?? "Image is not food"}
                </div>
                <div className="mt-1 text-xs text-zinc-500">Confidence: {pct(result.confidence)}</div>
              </div>
            )}

            {isFood && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-5">
                {(result.description || result.health_note) && (
                  <div className="mb-5 rounded-xl border border-zinc-100 bg-zinc-50 px-4 py-3 text-sm text-zinc-700">
                    {result.description && <div>{result.description}</div>}
                    {result.health_note && <div className="mt-2 text-xs text-zinc-500">{result.health_note}</div>}
                    <div className="mt-2 text-xs text-zinc-500">
                      <span className="font-semibold text-zinc-600">Serving Size:</span>{" "}
                      {result.portion?.label ?? "-"}
                    </div>
                  </div>
                )}
                <div className="text-sm text-zinc-700">
                  <span className="font-semibold">Dish:</span> {result.dish ?? "-"}
                </div>
                <div className="mt-1 text-xs text-zinc-500">
                  Portion: {result.portion?.label ?? "-"} ({result.portion?.grams_estimate ?? "-"}g) · Model confidence: {pct(result.confidence)}
                </div>
                {(result.notes ?? []).length > 0 && (
                  <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    {(result.notes ?? []).join(" ")}
                  </div>
                )}

                <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
                  <StatCard label="Calories" value={numberOrDash(result.nutrition?.calories_kcal, "kcal")} highlight />
                  <StatCard label="Protein" value={numberOrDash(result.nutrition?.protein_g, "g")} />
                  <StatCard label="Fat" value={numberOrDash(result.nutrition?.fat_g, "g")} />
                  <StatCard label="Sat. Fat" value={numberOrDash(result.nutrition?.sat_fat_g, "g")} />
                  <StatCard label="Carbs" value={numberOrDash(result.nutrition?.carbs_g, "g")} />
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatCard label="Fiber" value={numberOrDash(result.nutrition?.fiber_g, "g")} />
                  <StatCard label="Sugar" value={numberOrDash(result.nutrition?.sugar_g, "g")} />
                  <StatCard label="Sodium" value={numberOrDash(result.nutrition?.sodium_mg, "mg")} />
                  <StatCard label="Cholesterol" value={numberOrDash(result.nutrition?.cholesterol_mg, "mg")} />
                </div>

                <div className="mt-6 grid gap-6 sm:grid-cols-2">
                  <div>
                    <div className="text-[10px] font-semibold tracking-wide uppercase text-zinc-500">Macro % of calories</div>
                    <div className="mt-2 text-sm text-zinc-700">
                      Carbs: <span className="font-semibold">{pct(result.macro_percent_of_calories?.carbs_pct)}</span> · Protein:{" "}
                      <span className="font-semibold">{pct(result.macro_percent_of_calories?.protein_pct)}</span> · Fat:{" "}
                      <span className="font-semibold">{pct(result.macro_percent_of_calories?.fat_pct)}</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-semibold tracking-wide uppercase text-zinc-500">% Daily value (rough)</div>
                    <div className="mt-2 text-sm text-zinc-700">
                      Sodium: <span className="font-semibold">{pct(result.daily_value_percent?.sodiummgPct)}</span> · Fiber:{" "}
                      <span className="font-semibold">{pct(result.daily_value_percent?.fibergPct)}</span> · Protein:{" "}
                      <span className="font-semibold">{pct(result.daily_value_percent?.proteingPct)}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-6 border-t border-zinc-100 pt-5">
                  <div className="text-[10px] font-semibold tracking-wide uppercase text-zinc-500">Ingredients</div>
                  <ul className="mt-2 list-disc pl-5 text-sm text-zinc-700">
                    {(result.ingredients ?? []).length ? (result.ingredients ?? []).map((x: string) => <li key={x}>{x}</li>) : <li>-</li>}
                  </ul>

                  <div className="mt-4 text-[10px] font-semibold tracking-wide uppercase text-zinc-500">Potential Allergens</div>
                  <ul className="mt-2 list-disc pl-5 text-sm text-zinc-700">
                    {(result.potential_allergens ?? []).length ? (result.potential_allergens ?? []).map((x: string) => <li key={x}>{x}</li>) : <li>-</li>}
                  </ul>

                  {result.warning && <div className="mt-4 text-xs text-zinc-500">{result.warning}</div>}
                </div>
              </div>
            )}

            <div className="mt-6">
              <button className="w-full rounded-xl border border-zinc-200 bg-white py-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50" onClick={clearAll}>
                Analyze Another Image
              </button>
            </div>
          </div>
        )}

        <div className="mt-14 text-center text-xs text-zinc-400">No external API calls • Local inference worker • Privacy-friendly</div>
      </main>
    </div>
  );
}

export default function Home() {
  return <AnalyzerPage />;
}

