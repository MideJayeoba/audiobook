import { Fragment, useEffect, useMemo, useState } from "react";
import Header from "./components/Header";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const statusStyles = {
  uploaded: "bg-slate-700 text-slate-100",
  extracting: "bg-amber-600 text-amber-50",
  extracted: "bg-cyan-700 text-cyan-50",
  tts_processing: "bg-indigo-700 text-indigo-50",
  completed: "bg-emerald-700 text-emerald-50",
  failed: "bg-rose-700 text-rose-50"
};

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function canStartTts(document) {
  const hasText = Boolean(document.has_extracted_text);
  return hasText && (document.status === "extracted" || document.status === "failed");
}

function getMostRecentTime(value) {
  const time = new Date(value || 0).getTime();
  return Number.isFinite(time) ? time : 0;
}

function getDocumentTime(document) {
  return getMostRecentTime(document.updated_at || document.created_at);
}

function getJobTime(job) {
  return getMostRecentTime(job.started_at || job.created_at || job.updated_at);
}

async function fetchJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  const raw = await response.text();
  let data;
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { detail: raw || "Unexpected non-JSON response from server." };
  }
  if (!response.ok) {
    const message = data?.detail || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

async function parseJsonResponse(response) {
  const raw = await response.text();
  try {
    return raw ? JSON.parse(raw) : {};
  } catch {
    return { detail: raw || `Unexpected response (${response.status}).` };
  }
}

function waitMs(duration) {
  return new Promise((resolve) => setTimeout(resolve, duration));
}

async function uploadDocument(payload) {
  let lastError;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetch(`${API_BASE_URL}/documents/`, {
        method: "POST",
        body: payload
      });

      const raw = await response.text();
      let data;
      try {
        data = raw ? JSON.parse(raw) : {};
      } catch {
        data = { detail: raw || "Server returned an unexpected response." };
      }

      return { response, data };
    } catch (error) {
      lastError = error;
      if (attempt === 0) {
        await waitMs(1200);
      }
    }
  }

  throw lastError || new Error("Upload request failed.");
}

export default function App() {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [extractionJobs, setExtractionJobs] = useState([]);
  const [audioJobs, setAudioJobs] = useState([]);
  const [navigationEvents, setNavigationEvents] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [startingTtsId, setStartingTtsId] = useState(null);
  const [detectingChaptersId, setDetectingChaptersId] = useState(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [semanticQuery, setSemanticQuery] = useState("");
  const [isSemanticSeeking, setIsSemanticSeeking] = useState(false);
  const [semanticResult, setSemanticResult] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [expandedDocumentId, setExpandedDocumentId] = useState(null);
  const [showPastAudiobooks, setShowPastAudiobooks] = useState(false);
  const [showJobHistory, setShowJobHistory] = useState(false);
  const [message, setMessage] = useState("Ready.");

  const filteredDocuments = useMemo(() => {
    const sortedDocuments = [...documents].sort((left, right) => getDocumentTime(right) - getDocumentTime(left));
    if (statusFilter === "all") {
      return sortedDocuments;
    }
    return sortedDocuments.filter((document) => document.status === statusFilter);
  }, [documents, statusFilter]);
  const seekableDocuments = useMemo(
    () => documents.filter((document) => Boolean(document.has_extracted_text)),
    [documents]
  );
  const latestExtractionJobByDocument = useMemo(() => {
    const byDoc = {};
    const sortedJobs = [...extractionJobs].sort((left, right) => getJobTime(right) - getJobTime(left));
    for (const job of sortedJobs) {
      if (!byDoc[job.document]) {
        byDoc[job.document] = job;
      }
    }
    return byDoc;
  }, [extractionJobs]);
  const latestAudioJobByDocument = useMemo(() => {
    const byDoc = {};
    const sortedJobs = [...audioJobs].sort((left, right) => getJobTime(right) - getJobTime(left));
    for (const job of sortedJobs) {
      if (!byDoc[job.document]) {
        byDoc[job.document] = job;
      }
    }
    return byDoc;
  }, [audioJobs]);
  const sortedExtractionJobs = useMemo(
    () => [...extractionJobs].sort((left, right) => getJobTime(right) - getJobTime(left)),
    [extractionJobs]
  );
  const sortedAudioJobs = useMemo(
    () => [...audioJobs].sort((left, right) => getJobTime(right) - getJobTime(left)),
    [audioJobs]
  );
  const sortedNavigationEvents = useMemo(
    () => [...navigationEvents].sort((left, right) => getJobTime(right) - getJobTime(left)),
    [navigationEvents]
  );
  const visibleDocuments = showPastAudiobooks ? filteredDocuments : filteredDocuments.slice(0, 1);
  const visibleExtractionJobs = showJobHistory ? sortedExtractionJobs : sortedExtractionJobs.slice(0, 1);
  const visibleAudioJobs = showJobHistory ? sortedAudioJobs : sortedAudioJobs.slice(0, 1);
  const visibleNavigationEvents = showJobHistory ? sortedNavigationEvents : sortedNavigationEvents.slice(0, 1);

  useEffect(() => {
    if (filteredDocuments.length) {
      setExpandedDocumentId(filteredDocuments[0].id);
    }
  }, [filteredDocuments]);

  async function loadDashboardData() {
    setIsLoading(true);
    try {
      const [docs, extracted, audio, navigation] = await Promise.all([
        fetchJson("/documents/"),
        fetchJson("/extraction-jobs/"),
        fetchJson("/audio-jobs/"),
        fetchJson("/navigation-events/")
      ]);

      setDocuments(Array.isArray(docs) ? docs : []);
      setExtractionJobs(Array.isArray(extracted) ? extracted : []);
      setAudioJobs(Array.isArray(audio) ? audio : []);
      setNavigationEvents(Array.isArray(navigation) ? navigation : []);
      setMessage("Documents loaded.");
    } catch (_error) {
      setMessage(_error instanceof Error ? _error.message : "Could not reach API. Check backend server and API base URL.");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadDocuments() {
    try {
      const data = await fetchJson("/documents/");
      setDocuments(Array.isArray(data) ? data : []);
      return data;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load documents.");
      return [];
    }
  }

  async function handleUpload(event) {
    event.preventDefault();

    if (!file) {
      setMessage("Select a PDF file to upload.");
      return;
    }

    const resolvedTitle = title.trim() || file.name.replace(/\.pdf$/i, "").trim() || "Untitled PDF";

    const payload = new FormData();
    payload.append("title", resolvedTitle);
    payload.append("source_file", file);

    setIsUploading(true);

    try {
      const { response, data } = await uploadDocument(payload);

      if (!response.ok) {
        const detail = data?.detail || JSON.stringify(data);
        setMessage(`Upload failed: ${detail}`);
        return;
      }

      const uploadState = data?.status || "uploaded";
      if (uploadState === "failed") {
        setMessage("Upload accepted, but extraction failed. Check Job History for the exact error.");
      } else {
        setMessage(`Upload successful. Current status: ${uploadState}.`);
      }
      setTitle("");
      setFile(null);
      await loadDashboardData();
    } catch (_error) {
      const likelyProtocolMismatch = window?.location?.protocol === "https:";
      setMessage(
        likelyProtocolMismatch
          ? "Upload failed: protocol mismatch detected. Use same-origin /api setup or open the app over HTTP."
          : "Upload failed due to network error. Backend may still be starting; retry in a few seconds."
      );
    } finally {
      setIsUploading(false);
    }
  }

  async function startTts(documentId) {
    setStartingTtsId(documentId);
    setDocuments((prev) =>
      prev.map((document) =>
        document.id === documentId ? { ...document, status: "tts_processing" } : document
      )
    );

    try {
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}/start-tts/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ voice: "en-US-Neural2-J" })
      });

      const data = await parseJsonResponse(response);
      if (!response.ok) {
        const detail = data?.detail || `Request failed (${response.status})`;
        setMessage(`TTS failed: ${detail}`);
        await loadDocuments();
        return;
      }

      setDocuments((prev) => prev.map((document) => (document.id === documentId ? data : document)));
      setMessage("TTS completed for selected document.");
      await loadDashboardData();
    } catch (_error) {
      setMessage("TTS request failed due to network error.");
      await loadDashboardData();
    } finally {
      setStartingTtsId(null);
    }
  }

  async function detectChapters(documentId) {
    setDetectingChaptersId(documentId);
    try {
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}/detect-chapters/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        }
      });
      const data = await parseJsonResponse(response);

      if (!response.ok) {
        const detail = data?.detail || `Request failed (${response.status})`;
        setMessage(`Chapter detection failed: ${detail}`);
        return;
      }

      setDocuments((prev) => prev.map((document) => (document.id === documentId ? data : document)));
      setMessage(`Detected ${data.chapter_map?.length || 0} chapters.`);
      await loadDashboardData();
    } catch (_error) {
      setMessage("Chapter detection failed due to network error.");
    } finally {
      setDetectingChaptersId(null);
    }
  }

  async function runSemanticSeek(event) {
    event.preventDefault();

    if (!selectedDocumentId || !semanticQuery.trim()) {
      setMessage("Select a document and enter a navigation query.");
      return;
    }

    setIsSemanticSeeking(true);
    try {
      const response = await fetch(`${API_BASE_URL}/documents/${selectedDocumentId}/semantic-seek/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ query: semanticQuery.trim() })
      });
      const data = await parseJsonResponse(response);

      if (!response.ok) {
        const detail = data?.detail || `Request failed (${response.status})`;
        setMessage(`Semantic seek failed: ${detail}`);
        return;
      }

      setSemanticResult(data);
      setMessage("Semantic seek completed.");
      await loadDashboardData();
    } catch (_error) {
      setMessage("Semantic seek failed due to network error.");
    } finally {
      setIsSemanticSeeking(false);
    }
  }

  useEffect(() => {
    loadDashboardData();
    const id = setInterval(loadDashboardData, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-10 md:px-8">
        <Header />

        <div className="flex flex-col gap-8 lg:flex-row">
          <section className="flex-1 rounded-xl border border-slate-800 bg-slate-900/80 p-6">
          <h2 className="text-xl font-semibold text-white">Upload PDF</h2>
          <p className="mt-2 text-sm text-slate-300">Public mode is enabled. Anyone can upload and process PDFs right now.</p>
          <form onSubmit={handleUpload} className="mt-4 grid gap-3">
            <input
              type="text"
              placeholder="Document title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
            />
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => {
                const selected = event.target.files?.[0] || null;
                setFile(selected);
                if (selected && !title.trim()) {
                  setTitle(selected.name.replace(/\.pdf$/i, ""));
                }
              }}
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none file:mr-3 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-1 file:text-slate-100"
            />
            <button
              type="submit"
              disabled={isUploading}
              className="w-fit rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
            >
              {isUploading ? "Uploading..." : "Upload and Process"}
            </button>
          </form>
          <button
            type="button"
            onClick={loadDocuments}
            disabled={isLoading}
            className="mt-4 rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-60"
          >
            {isLoading ? "Refreshing..." : "Refresh Documents"}
          </button>
          <p className="mt-3 text-sm text-slate-300">Status: {message}</p>
          </section>

          <section className="flex-1 rounded-xl border border-slate-800 bg-slate-900/80 p-6">
            <h2 className="text-xl font-semibold text-white">AI Semantic Navigation</h2>
            <p className="mt-2 text-sm text-slate-300">
              Ask naturally, for example: <span className="text-slate-100">"Take me to the investigation part"</span>.
            </p>

            <form onSubmit={runSemanticSeek} className="mt-4 grid gap-3">
              <select
                value={selectedDocumentId}
                onChange={(event) => setSelectedDocumentId(event.target.value)}
                className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
              >
                <option value="">Select a document</option>
                {seekableDocuments.map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.title}
                  </option>
                ))}
              </select>

              <input
                type="text"
                placeholder="Ask where you want to jump in the book"
                value={semanticQuery}
                onChange={(event) => setSemanticQuery(event.target.value)}
                className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
              />

              <button
                type="submit"
                disabled={isSemanticSeeking}
                className="w-fit rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-violet-700 disabled:opacity-60"
              >
                {isSemanticSeeking ? "Finding best match..." : "Semantic Seek"}
              </button>
            </form>

            {semanticResult && (
              <div className="mt-4 rounded-md border border-violet-700/40 bg-violet-500/10 p-4 text-sm text-violet-100">
                <p>
                  Jump to <strong>{semanticResult.chapter_title || "matched section"}</strong> at{" "}
                  <strong>{Math.round(semanticResult.position_seconds)}s</strong>
                </p>
                <p className="mt-1">
                  Provider: {semanticResult.provider} | Confidence: {semanticResult.confidence}
                </p>
                {semanticResult.match_excerpt && (
                  <p className="mt-2 text-violet-50/90">{semanticResult.match_excerpt}</p>
                )}
              </div>
            )}
          </section>
        </div>

        <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-6">
          <h2 className="text-xl font-semibold text-white">Track Progress</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setShowPastAudiobooks((current) => !current)}
              className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
            >
              {showPastAudiobooks ? "Show latest only" : "Show all past audiobooks"}
            </button>

            <button
              type="button"
              onClick={loadDashboardData}
              disabled={isLoading}
              className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-slate-100 transition hover:bg-slate-700 disabled:opacity-60"
            >
              {isLoading ? "Refreshing..." : "Refresh status"}
            </button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {[
              { value: "all", label: "All" },
              { value: "uploaded", label: "Uploaded" },
              { value: "extracting", label: "Extracting" },
              { value: "extracted", label: "Extracted" },
              { value: "tts_processing", label: "TTS Processing" },
              { value: "completed", label: "Completed" },
              { value: "failed", label: "Failed" }
            ].map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setStatusFilter(filter.value)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  statusFilter === filter.value
                    ? "bg-brand-500 text-white"
                    : "bg-slate-800 text-slate-200 hover:bg-slate-700"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-300">
                  <th className="px-2 py-2">Title</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Created</th>
                  <th className="px-2 py-2">Audio</th>
                  <th className="px-2 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleDocuments.map((document) => (
                  <Fragment key={document.id}>
                    <tr className="border-b border-slate-800/70">
                      <td className="px-2 py-2 text-slate-100">{document.title}</td>
                      <td className="px-2 py-2">
                        <span
                          className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusStyles[document.status] || "bg-slate-700 text-slate-100"}`}
                        >
                          {document.status}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-slate-300">{formatDate(document.created_at)}</td>
                      <td className="px-2 py-2 text-slate-300">{document.audio_url ? "Available" : "-"}</td>
                      <td className="px-2 py-2 text-slate-300">
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedDocumentId((current) => (current === document.id ? null : document.id))
                          }
                          className="rounded-md bg-slate-700 px-3 py-1 text-xs font-medium text-white transition hover:bg-slate-600"
                        >
                          {expandedDocumentId === document.id ? "Hide details" : "Show details"}
                        </button>
                      </td>
                    </tr>
                    {expandedDocumentId === document.id && (
                      <tr className="border-b border-slate-800/70 bg-slate-900/50">
                        <td className="px-2 py-3 text-slate-300" colSpan={5}>
                          <div className="grid gap-3 md:grid-cols-[1.3fr_1fr_auto] md:items-start">
                            <div className="space-y-2">
                              <p className="text-xs uppercase tracking-wide text-slate-400">Audio</p>
                              {document.audio_url ? (
                                <audio controls preload="none" className="h-8 w-full max-w-96" src={document.audio_url}>
                                  Your browser does not support audio playback.
                                </audio>
                              ) : (
                                <p className="text-sm text-slate-400">No audio available yet.</p>
                              )}
                            </div>

                            <div className="space-y-2">
                              <p className="text-xs uppercase tracking-wide text-slate-400">TTS</p>
                              <button
                                type="button"
                                onClick={() => startTts(document.id)}
                                disabled={startingTtsId === document.id || !canStartTts(document)}
                                className="rounded-md bg-indigo-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                <span className="inline-flex items-center gap-2">
                                  {startingTtsId === document.id && (
                                    <span className="h-3 w-3 animate-spin rounded-full border border-white/40 border-t-white" />
                                  )}
                                  {startingTtsId === document.id
                                    ? "Starting..."
                                    : document.status === "failed"
                                      ? "Retry TTS"
                                      : "Start TTS"}
                                </span>
                              </button>
                              {document.status === "failed" && (
                                <p className="text-xs text-rose-300">
                                  {latestAudioJobByDocument[document.id]?.error_message ||
                                    latestExtractionJobByDocument[document.id]?.error_message ||
                                    "Last run failed. Check job history for details."}
                                </p>
                              )}
                            </div>

                            <div className="space-y-2">
                              <p className="text-xs uppercase tracking-wide text-slate-400">Chapters</p>
                              <button
                                type="button"
                                onClick={() => detectChapters(document.id)}
                                disabled={detectingChaptersId === document.id || !document.has_extracted_text}
                                className="rounded-md bg-cyan-700 px-3 py-1 text-xs font-medium text-white transition hover:bg-cyan-800 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {detectingChaptersId === document.id ? "Detecting..." : "Detect Chapters"}
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {!visibleDocuments.length && (
                  <tr>
                    <td className="px-2 py-4 text-slate-400" colSpan={5}>
                      No matching documents. Try another filter or upload a new PDF.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {filteredDocuments.length > 1 && !showPastAudiobooks && (
            <p className="mt-3 text-sm text-slate-400">Showing the latest document only. Use the button to reveal the rest.</p>
          )}
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-6">
          <h2 className="text-xl font-semibold text-white">Job History</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setShowJobHistory((current) => !current)}
              className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
            >
              {showJobHistory ? "Show latest only" : "Show full job history"}
            </button>
          </div>

          <div className="mt-4 space-y-4">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Extraction Jobs</h3>
              <div className="mt-2 overflow-x-auto">
                <table className="min-w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400">
                      <th className="px-2 py-2">Document</th>
                      <th className="px-2 py-2">Status</th>
                      <th className="px-2 py-2">Provider</th>
                      <th className="px-2 py-2">Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleExtractionJobs.map((job) => (
                      <tr key={job.id} className="border-b border-slate-800/70">
                        <td className="px-2 py-2 text-slate-100">{job.document_title || job.document}</td>
                        <td className="px-2 py-2 text-slate-300">{job.status}</td>
                        <td className="px-2 py-2 text-slate-300">{job.provider || "-"}</td>
                        <td className="px-2 py-2 text-slate-300">{formatDate(job.started_at || job.created_at)}</td>
                      </tr>
                    ))}
                    {!visibleExtractionJobs.length && (
                      <tr>
                        <td className="px-2 py-3 text-slate-500" colSpan={4}>
                          No extraction jobs yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Audio Jobs</h3>
              <div className="mt-2 overflow-x-auto">
                <table className="min-w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400">
                      <th className="px-2 py-2">Document</th>
                      <th className="px-2 py-2">Status</th>
                      <th className="px-2 py-2">Voice</th>
                      <th className="px-2 py-2">Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleAudioJobs.map((job) => (
                      <tr key={job.id} className="border-b border-slate-800/70">
                        <td className="px-2 py-2 text-slate-100">{job.document_title || job.document}</td>
                        <td className="px-2 py-2 text-slate-300">{job.status}</td>
                        <td className="px-2 py-2 text-slate-300">{job.voice || "-"}</td>
                        <td className="px-2 py-2 text-slate-300">{formatDate(job.started_at || job.created_at)}</td>
                      </tr>
                    ))}
                    {!visibleAudioJobs.length && (
                      <tr>
                        <td className="px-2 py-3 text-slate-500" colSpan={4}>
                          No audio jobs yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="mt-6">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Navigation History</h3>
            <div className="mt-2 overflow-x-auto">
              <table className="min-w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="px-2 py-2">Document</th>
                    <th className="px-2 py-2">Event</th>
                    <th className="px-2 py-2">Chapter</th>
                    <th className="px-2 py-2">Position</th>
                    <th className="px-2 py-2">Query</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleNavigationEvents.map((event) => (
                    <tr key={event.id} className="border-b border-slate-800/70">
                      <td className="px-2 py-2 text-slate-100">{event.document_title || event.document}</td>
                      <td className="px-2 py-2 text-slate-300">{event.event_type}</td>
                      <td className="px-2 py-2 text-slate-300">{event.chapter_title || "-"}</td>
                      <td className="px-2 py-2 text-slate-300">{Math.round(event.position_seconds || 0)}s</td>
                      <td className="px-2 py-2 text-slate-300">{event.query || event.match_excerpt || "-"}</td>
                    </tr>
                  ))}
                  {!visibleNavigationEvents.length && (
                    <tr>
                      <td className="px-2 py-3 text-slate-500" colSpan={5}>
                        No navigation events yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          {sortedExtractionJobs.length > 1 && !showJobHistory && (
            <p className="mt-3 text-sm text-slate-400">Showing the latest job only. Use the button to reveal the rest.</p>
          )}
        </section>
      </div>
    </div>
  );
}
