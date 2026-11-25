"use client";

import {
  ArrowDownToLine, AudioLines, Check, ChevronRight, Clapperboard, ExternalLink, FileText,
  LoaderCircle, LockKeyhole, Monitor, MousePointer2, Scissors,
  ShieldCheck, Sparkles, Terminal, Upload, WandSparkles, X,
} from "lucide-react";
import { ChangeEvent, FormEvent, MouseEvent, useCallback, useEffect, useState } from "react";
import { ToolNavigation, type MediaTool } from "@/components/tool-navigation";
import { TerminalProcessingView } from "@/components/terminal-processing-view";
import { TranscriptWorkspace } from "@/components/transcript-workspace";

type Feature = MediaTool;
type Point = { x: number; y: number; keep: boolean };
type Uploaded = {
  id: string;
  kind: string;
  filename: string;
  preview_url: string;
  details: { width: number; height: number; duration?: number; fps?: number; has_audio?: boolean };
};
type VideoBatchUpload = Uploaded & { outputName: string };
type TranscriptionUpload = { id?: string; filename: string; size: number; previewUrl: string; mediaType: "audio" | "video" };
type FileResult = { url: string; filename: string };
type VideoBatchResult = { filename: string; status: "completed" | "failed"; result_key?: string; preview_key?: string; error?: string; report?: { frames: number; processed_seconds: number } };
type Job = {
  id: string;
  kind: Feature;
  state: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string;
  error?: string | null;
  logs?: Array<{ time: string; progress: number; message: string }>;
  created_at?: number;
  started_at?: number | null;
  finished_at?: number | null;
  progress_updated_at?: number;
  result?: {
    title?: string; text?: string; words?: number; sentences?: number; size?: number; images?: number; notice?: string; source_type?: "file" | "youtube";
    report?: { frames: number; processed_seconds: number };
    items?: VideoBatchResult[];
    files: Record<string, FileResult>;
  } | null;
};
type MediaCapture = { id: string; state: string; message: string; candidates: { url: string; type: string; status: number }[] };
const API = process.env.NODE_ENV === "development" ? "http://127.0.0.1:7860" : "";
const MAX_VIDEO_BATCH = 10;
const FEATURES: { id: Feature; label: string }[] = [
  { id: "video", label: "Hapus latar video" },
  { id: "photo", label: "Hapus latar foto" },
  { id: "transcription", label: "Transkripsi" },
  { id: "download", label: "Unduh media" },
];
const EXPORTS = [
  { value: "transparent", label: "Transparan · MOV" },
  { value: "mp4_green", label: "Layar hijau · MP4" },
  { value: "mp4_black", label: "Layar hitam · MP4" },
  { value: "mask", label: "Mask · MKV" },
];

async function responseJson(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Permintaan gagal. Coba lagi.");
  return body;
}
function fileUrl(file?: FileResult, download = false) {
  return file ? API + file.url + (download ? "?download=1" : "") : "";
}
function formatTime(seconds: number) {
  return Math.floor(seconds / 60) + ":" + String(Math.floor(seconds % 60)).padStart(2, "0");
}

async function uploadMediaFile(file: File, kind: string, onProgress: (loaded: number, total: number) => void) {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  return new Promise<Uploaded>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", API + "/api/uploads");
    request.upload.onprogress = (event) => { if (event.lengthComputable) onProgress(event.loaded, event.total); };
    request.onload = () => {
      let body: { detail?: string } & Partial<Uploaded> = {};
      try { body = JSON.parse(request.responseText); } catch { }
      if (request.status < 200 || request.status >= 300) reject(new Error(body.detail || "Gagal mengunggah file."));
      else resolve(body as Uploaded);
    };
    request.onerror = () => reject(new Error("Koneksi terputus saat mengunggah file."));
    request.send(form);
  });
}

export default function Home() {
  const [feature, setFeature] = useState<Feature>("video");
  const [gpu, setGpu] = useState<string | null>(null);
  const [languages, setLanguages] = useState<string[]>(["Auto"]);
  const [uploaded, setUploaded] = useState<Uploaded | null>(null);
  const [videoBatchUploads, setVideoBatchUploads] = useState<VideoBatchUpload[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadElapsed, setUploadElapsed] = useState(0);
  const [mode, setMode] = useState("Manusia");
  const [quality, setQuality] = useState("Detail");
  const [exportKind, setExportKind] = useState("transparent");
  const [pointKind, setPointKind] = useState(true);
  const [points, setPoints] = useState<Point[]>([]);
  const [name, setName] = useState("");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [transcriptionSource, setTranscriptionSource] = useState<"youtube" | "file">("youtube");
  const [transcriptionUpload, setTranscriptionUpload] = useState<TranscriptionUpload | null>(null);
  const [language, setLanguage] = useState("Auto");
  const [platform, setPlatform] = useState("YouTube");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [downloadQuality, setDownloadQuality] = useState("Terbaik");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showResult, setShowResult] = useState(false);
  const [backendReady, setBackendReady] = useState(false);
  const [mediaCapture, setMediaCapture] = useState<MediaCapture | null>(null);
  const [captureElapsed, setCaptureElapsed] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedTool = params.get("tool") as Feature | null;
    if (FEATURES.some((item) => item.id === requestedTool)) setFeature(requestedTool!);
    const requestedJob = params.get("job");
    if (requestedJob) {
      fetch(API + "/api/jobs/" + requestedJob, { cache: "no-store" }).then(responseJson).then((restored: Job) => {
        if (FEATURES.some((item) => item.id === restored.kind)) {
          setFeature(restored.kind);
          setJob(restored);
          setShowResult(false);
        }
      }).catch(() => setError("Pekerjaan ini sudah tidak tersedia. Mungkin server lokal telah dimulai ulang."));
    }
    fetch(API + "/api/health").then(responseJson).then((data) => { setGpu(data.gpu); setBackendReady(true); }).catch(() => setBackendReady(false));
    fetch(API + "/api/languages").then(responseJson).then((data) => setLanguages(data.languages)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!job || ["completed", "failed", "cancelled"].includes(job.state)) return;
    let active = true;
    let timer: number;
    const poll = async () => {
      try {
        const response = await fetch(API + "/api/jobs/" + job.id, { cache: "no-store" });
        if (response.status === 404) {
          if (active) setJob((current) => current?.id === job.id ? { ...current, state: "failed", error: "Pekerjaan tidak lagi tersedia di backend." } : current);
          return;
        }
        const snapshot: Job = await responseJson(response);
        if (!active) return;
        setJob((current) => current?.id === job.id ? snapshot : current);
        if (["queued", "running"].includes(snapshot.state)) timer = window.setTimeout(poll, 800);
      } catch {
        if (active) timer = window.setTimeout(poll, 1500);
      }
    };
    poll();
    return () => { active = false; window.clearTimeout(timer); };
  }, [job?.id, job?.state]);

  useEffect(() => {
    if (job?.kind === "transcription" && ["completed", "failed", "cancelled"].includes(job.state)) {
      setTranscriptionUpload((file) => file?.id ? { ...file, id: undefined } : file);
    }
  }, [job?.id, job?.kind, job?.state]);

  useEffect(() => {
    if (job?.kind === "transcription" && job.result?.source_type) {
      setTranscriptionSource(job.result.source_type);
    }
  }, [job?.id, job?.kind, job?.result?.source_type]);

  useEffect(() => {
    const previewUrl = transcriptionUpload?.previewUrl;
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl); };
  }, [transcriptionUpload?.previewUrl]);

  useEffect(() => {
    if (!uploading) { setUploadElapsed(0); return; }
    const startedAt = Date.now();
    const updateElapsed = () => setUploadElapsed(Math.floor((Date.now() - startedAt) / 1000));
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [uploading]);

  useEffect(() => {
    const captureId = mediaCapture?.id;
    if (!captureId) return;
    let active = true;
    const poll = async () => {
      try {
        const current: MediaCapture = await responseJson(await fetch(API + "/api/media-captures/" + captureId, { cache: "no-store" }));
        if (active) setMediaCapture(current);
      } catch { }
    };
    const timer = window.setInterval(poll, 1000);
    return () => { active = false; window.clearInterval(timer); };
  }, [mediaCapture?.id]);

  useEffect(() => {
    if (!mediaCapture) { setCaptureElapsed(0); return; }
    const startedAt = Date.now();
    const updateElapsed = () => setCaptureElapsed(Math.floor((Date.now() - startedAt) / 1000));
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [mediaCapture?.id]);

  async function uploadFile(event: ChangeEvent<HTMLInputElement>, addToVideoBatch = false) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length || busy || uploading || currentJobActive) return;
    const batchMode = feature === "video" && (addToVideoBatch || files.length > 1 || videoBatchUploads.length > 0);
    if (batchMode) {
      const existing: VideoBatchUpload[] = addToVideoBatch && uploaded
        ? [{ ...uploaded, outputName: `${uploaded.filename.replace(/\.[^.]+$/, "")}-hasil` }]
        : videoBatchUploads;
      if (existing.length + files.length > MAX_VIDEO_BATCH) {
        setError(`Satu batch maksimal ${MAX_VIDEO_BATCH} video. Proses beberapa batch jika videonya lebih banyak.`);
        event.target.value = "";
        return;
      }
      setError(""); setJob(null); setShowResult(false); setUploading(true); setUploadProgress(0);
      const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
      const added: VideoBatchUpload[] = [];
      let completedBytes = 0;
      try {
        for (const file of files) {
          const item = await uploadMediaFile(file, "video", (loaded, total) => {
            setUploadProgress(totalBytes ? (completedBytes + loaded / total * file.size) / totalBytes : 0);
          });
          added.push({ ...item, outputName: `${item.filename.replace(/\.[^.]+$/, "")}-hasil` });
          completedBytes += file.size;
        }
        setVideoBatchUploads([...existing, ...added]);
        if (addToVideoBatch && uploaded) setUploaded(null);
        setMode("Manusia"); setPoints([]); setName("");
      } catch (reason) {
        added.forEach((item) => discardUpload(item.id));
        setError(reason instanceof Error ? reason.message : "Gagal mengunggah video batch.");
      } finally {
        setUploading(false); setUploadProgress(null); event.target.value = "";
      }
      return;
    }

    const file = files[0];
    const kind = feature === "photo" ? "photo" : feature === "transcription" ? "transcription" : "video";
    if (kind === "transcription" && transcriptionUpload?.id) discardUpload(transcriptionUpload.id);
    setError(""); setJob(null); setPoints([]); setUploading(true); setUploadProgress(0);
    try {
      const data = await uploadMediaFile(file, kind, (loaded, total) => setUploadProgress(loaded / total));
      if (feature === "transcription") {
        setTranscriptionUpload({
          id: data.id,
          filename: file.name,
          size: file.size,
          previewUrl: URL.createObjectURL(file),
          mediaType: /\.(mp4|mov|mkv|avi|webm)$/i.test(file.name) ? "video" : "audio",
        });
        setName(file.name.replace(/\.[^.]+$/, ""));
      } else {
        setUploaded(data);
        setName(file.name.replace(/\.[^.]+$/, "-hasil"));
      }
    } catch (reason) {
      if (feature === "transcription") setTranscriptionUpload(null);
      else setUploaded(null);
      setError(reason instanceof Error ? reason.message : "Gagal mengunggah file.");
    } finally {
      setUploading(false);
      setUploadProgress(null);
      event.target.value = "";
    }
  }

  function discardUpload(id: string) {
    fetch(API + "/api/uploads/" + id, { method: "DELETE" }).catch(() => {});
  }

  function removeBatchVideo(id: string) {
    discardUpload(id);
    setVideoBatchUploads((items) => items.filter((item) => item.id !== id));
  }

  function addPoint(event: MouseEvent<HTMLDivElement>) {
    if (mode !== "Objek umum" || !uploaded) return;
    const rect = event.currentTarget.getBoundingClientRect();
    setPoints((old) => [...old, {
      x: Math.max(0, Math.min(uploaded.details.width - 1, Math.round((event.clientX - rect.left) / rect.width * uploaded.details.width))),
      y: Math.max(0, Math.min(uploaded.details.height - 1, Math.round((event.clientY - rect.top) / rect.height * uploaded.details.height))),
      keep: pointKind,
    }]);
  }

  async function startJob(event: FormEvent) {
    event.preventDefault(); setError(""); setJob(null); setShowResult(false);
    let payload: Record<string, unknown>;
    if (feature === "video" && videoBatchUploads.length > 0) {
      payload = { kind: "video", upload_ids: videoBatchUploads.map((item) => item.id), output_names: videoBatchUploads.map((item) => item.outputName), mode: "Manusia", quality, export: exportKind, points: [] };
    } else if (feature === "video" || feature === "photo") {
      if (!uploaded) { setError("Pilih file terlebih dahulu."); return; }
      payload = {
        kind: feature, upload_id: uploaded.id, mode,
        ...(feature === "video" ? { quality: quality, export: exportKind } : {}),
        points: points.map((point) => [point.x, point.y, point.keep ? 1 : 0]), name,
      };
    } else if (feature === "transcription") {
      if (transcriptionSource === "file") {
        if (!transcriptionUpload?.id) { setError("Pilih file audio atau video terlebih dahulu."); return; }
        payload = { kind: feature, upload_id: transcriptionUpload.id, language, name };
      } else {
        payload = { kind: feature, url: youtubeUrl, language, name };
      }
    } else {
      payload = { kind: "download", url: downloadUrl, platform, quality: downloadQuality, name };
    }
    setBusy(true);
    try {
      const form = new FormData(); form.append("payload", JSON.stringify(payload));
      const created: Job = await responseJson(await fetch(API + "/api/jobs", { method: "POST", body: form }));
      setJob(created);
      if (feature === "video" && videoBatchUploads.length > 0) setVideoBatchUploads([]);
      if (uploaded && (feature === "video" || feature === "photo")) setUploaded(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Proses gagal.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelJob() {
    if (job) await fetch(API + "/api/jobs/" + job.id + "/cancel", { method: "POST" }).catch(() => {});
  }
  async function openMediaCapture() {
    setError(""); setJob(null);
    if (mediaCapture) fetch(API + "/api/media-captures/" + mediaCapture.id, { method: "DELETE" }).catch(() => {});
    try {
      const form = new FormData(); form.append("url", downloadUrl);
      const capture: MediaCapture = await responseJson(await fetch(API + "/api/media-captures", { method: "POST", body: form }));
      setMediaCapture(capture);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Gagal membuka browser deteksi.");
    }
  }
  function useCapturedMedia(url: string) {
    if (mediaCapture) fetch(API + "/api/media-captures/" + mediaCapture.id, { method: "DELETE" }).catch(() => {});
    setDownloadUrl(url); setMediaCapture(null); setError("");
  }
  function chooseFeature(next: Feature) {
    if (busy || uploading) return;
    if (mediaCapture) fetch(API + "/api/media-captures/" + mediaCapture.id, { method: "DELETE" }).catch(() => {});
    setMediaCapture(null);
    if (uploaded) discardUpload(uploaded.id);
    videoBatchUploads.forEach((item) => discardUpload(item.id));
    if (transcriptionUpload?.id && !currentJobActive) discardUpload(transcriptionUpload.id);
    setFeature(next); setError(""); setShowResult(false); setUploaded(null); setVideoBatchUploads([]); setPoints([]); setName("");
    setTranscriptionUpload(null);
  }

  const currentFeature = FEATURES.find((item) => item.id === feature)!;
  const markTranscriptionFileSource = useCallback(() => setTranscriptionSource("file"), []);
  const jobResult = job?.kind === feature && (job.state === "completed" || (job.state === "cancelled" && Boolean(job.result?.items?.length))) ? job.result : null;
  const currentJobActive = job?.kind === feature && (job.state === "queued" || job.state === "running");
  const files = jobResult?.files;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><Scissors size={21} strokeWidth={2.3} /></div>
          <div><p className="brand-name">MyTools</p><p className="brand-caption">Studio lokal untuk pekerjaan media</p></div>
        </div>
        <div className="local-status"><span className={"status-dot " + (backendReady ? "" : "offline")} />{gpu || (backendReady ? "Backend lokal" : "Menghubungkan…")}</div>
      </header>

      <div className="mobile-nav">
        <ToolNavigation activeTool={feature} onSelectTool={chooseFeature} disabled={busy || uploading} />
      </div>

      <div className="workspace">
        <aside className="sidebar">
          <ToolNavigation activeTool={feature} onSelectTool={chooseFeature} disabled={busy || uploading} />
          <div className="sidebar-tip"><strong><LockKeyhole size={13} style={{ verticalAlign: "-2px", marginRight: 5 }} />Dijalankan lokal</strong>Hasil tersimpan di cache lokal maksimal 7 hari. Unduh file hanya saat kamu memilihnya.</div>
        </aside>

        <section className="panel">
          <div className="panel-head">
            <div><h2 className="panel-title">{currentFeature.label}</h2><p className="panel-description">{featureDescription(feature)}</p></div>
            <ChevronRight size={18} color="#a0aaa5" />
          </div>

          <form onSubmit={startJob} className="panel-body">
            <div className="form-column">
              {(feature === "video" || feature === "photo") && <>
                <div className="field">
                  <label className="field-label">File sumber</label>
                  {feature === "video" && videoBatchUploads.length > 0 ? <div>
                    <div className="video-batch-list">{videoBatchUploads.map((item) => <div className="video-batch-item" key={item.id}>
                      <img src={API + item.preview_url} alt="" />
                      <span><b>{item.filename}</b><small>{item.details.width} × {item.details.height}{item.details.duration ? ` · ${formatTime(item.details.duration)}` : ""}</small><input className="control video-batch-name" aria-label={`Nama hasil untuk ${item.filename}`} value={item.outputName} onChange={(event) => setVideoBatchUploads((items) => items.map((video) => video.id === item.id ? { ...video, outputName: event.target.value } : video))} /></span>
                      <button type="button" className="text-button" onClick={() => removeBatchVideo(item.id)} disabled={busy || currentJobActive}>Hapus</button>
                    </div>)}</div>
                    <div className="preview-caption"><span>{videoBatchUploads.length} video · akan diproses berurutan</span><button type="button" className="text-button" onClick={() => { videoBatchUploads.forEach((item) => discardUpload(item.id)); setVideoBatchUploads([]); }}>Kosongkan</button></div>
                    <label className="secondary-button video-batch-add"><Upload size={14} />Tambahkan video<input type="file" accept=".mp4,.mov,.mkv,.avi,.webm" multiple disabled={uploading || busy || currentJobActive} onChange={(event) => uploadFile(event, true)} /></label>
                  </div> : uploaded ? <div>
                    <div className={"source-preview " + (mode === "Objek umum" ? "interactive" : "")} style={{ width: "min(100%, " + (420 * uploaded.details.width / uploaded.details.height) + "px)", aspectRatio: uploaded.details.width + " / " + uploaded.details.height }} onClick={addPoint}>
                      <img src={API + uploaded.preview_url} alt="Pratinjau sumber" />
                      {points.map((point, index) => <span key={index} className={"point-marker " + (point.keep ? "keep" : "remove")} style={{ left: (point.x / uploaded.details.width * 100) + "%", top: (point.y / uploaded.details.height * 100) + "%" }} />)}
                    </div>
                    <div className="preview-caption">
                      <span>{uploaded.filename} · {uploaded.details.width} × {uploaded.details.height}{uploaded.details.duration ? " · " + formatTime(uploaded.details.duration) : " · Foto"}</span>
                      <button type="button" className="text-button" onClick={() => { discardUpload(uploaded.id); setUploaded(null); }}>Ganti file</button>
                    </div>
                    {feature === "video" && <label className="secondary-button video-batch-add"><Upload size={14} />Tambahkan video ke batch<input type="file" accept=".mp4,.mov,.mkv,.avi,.webm" multiple disabled={uploading || busy || currentJobActive} onChange={(event) => uploadFile(event, true)} /></label>}
                  </div> : <label className="upload-box">
                    <input type="file" accept={feature === "photo" ? ".png,.jpg,.jpeg,.webp" : ".mp4,.mov,.mkv,.avi,.webm"} multiple={feature === "video"} disabled={uploading || busy || currentJobActive} onChange={uploadFile} />
                    {uploading ? <LoaderCircle className="spin" size={22} color="#0d9488" /> : <Upload size={22} color="#0d9488" />}
                    <span className="upload-title">{uploading ? "Menyiapkan pratinjau…" : feature === "video" ? "Pilih satu atau beberapa video" : "Pilih file dari komputer"}</span>
                    <span className="upload-subtitle">{feature === "photo" ? "PNG, JPG, WEBP · Maks. 40 MP" : "MP4, MOV, MKV, AVI, WEBM · Maks. 15 menit per video · Maks. 10 video per batch"}</span>
                  </label>}
                </div>
                <div className="field">
                  <label className="field-label">Mode subjek</label>
                  <div className="choice-row">{["Manusia", "Objek umum"].map((value) => <label className="choice" key={value}><input type="radio" checked={mode === value} disabled={feature === "video" && videoBatchUploads.length > 0 && value === "Objek umum"} onChange={() => setMode(value)} />{value === "Manusia" ? "Manusia otomatis" : "Objek dengan titik"}</label>)}</div>
                  {feature === "video" && videoBatchUploads.length > 0 && <p className="field-hint">Batch memakai mode Manusia otomatis untuk semua klip. Mode objek manual tetap tersedia untuk video satu per satu.</p>}
                  {mode === "Objek umum" && <p className="field-hint"><MousePointer2 size={12} style={{ verticalAlign: "-2px" }} /> {feature === "photo" ? "Klik objek yang ingin dipertahankan pada foto sumber." : "Klik objek pada frame pertama. Titik hijau menyimpan, titik merah menghapus."}</p>}
                </div>
                {mode === "Objek umum" && uploaded && <div className="field"><div className="choice-row">
                  <button type="button" className={"choice-button " + (pointKind ? "selected" : "")} onClick={() => setPointKind(true)}>● Titik simpan</button>
                  <button type="button" className={"choice-button " + (!pointKind ? "selected remove" : "")} onClick={() => setPointKind(false)}>● Titik hapus</button>
                  <button type="button" className="text-button" onClick={() => setPoints([])}>Bersihkan titik{points.length ? " (" + points.length + ")" : ""}</button>
                </div></div>}
                {!(feature === "video" && videoBatchUploads.length > 0) && <div className="field"><label className="field-label" htmlFor="output-name">Nama hasil</label><input id="output-name" className="control" value={name} onChange={(event) => setName(event.target.value)} placeholder="otomatis dari nama file" /></div>}
                {feature === "video" && <>
                  <div className="field"><label className="field-label">Kualitas pemrosesan</label><div className="choice-row">{["Detail", "Cepat"].map((value) => <label className="choice" key={value}><input type="radio" checked={quality === value} onChange={() => setQuality(value)} />{value}</label>)}</div></div>
                  <div className="field"><label className="field-label" htmlFor="export-kind">Format hasil</label><select id="export-kind" className="control select-control" value={exportKind} onChange={(event) => setExportKind(event.target.value)}>{EXPORTS.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></div>
                </>}
              </>}

              {feature === "transcription" && <>
                <div className="field"><label className="field-label" htmlFor="transcription-source">Sumber transkrip</label><select id="transcription-source" className="control select-control" value={transcriptionSource} disabled={busy || currentJobActive} onChange={(event) => { const next = event.target.value as "youtube" | "file"; if (next === "youtube" && transcriptionUpload) { if (transcriptionUpload.id) discardUpload(transcriptionUpload.id); setTranscriptionUpload(null); } setTranscriptionSource(next); }}><option value="youtube">Tautan YouTube</option><option value="file">File audio atau video</option></select></div>
                {transcriptionSource === "youtube" ? <div className="field"><label className="field-label" htmlFor="youtube-url">Tautan video YouTube</label><input id="youtube-url" className="control" type="url" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=…" /><p className="field-hint">Audio diproses dengan Whisper multilingual. Video tidak disimpan oleh fitur ini.</p></div> : <div className="field"><label className="field-label">File audio atau video</label><label className="upload-box"><input type="file" accept=".mp4,.mov,.mkv,.avi,.webm,.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus,.wma" disabled={uploading || busy || currentJobActive} onChange={uploadFile} /><Upload size={22} color="#0d9488" /><span className="upload-title">{uploading ? "Mengunggah file…" : transcriptionUpload?.id ? transcriptionUpload.filename : transcriptionUpload ? `Pilih ulang: ${transcriptionUpload.filename}` : "Pilih file dari komputer"}</span><span className="upload-subtitle">MP4, MOV, MKV, AVI, WEBM · MP3, WAV, M4A, AAC, FLAC, OGG, OPUS, WMA{transcriptionUpload ? ` · ${(transcriptionUpload.size / 1048576).toFixed(1)} MB` : ""}</span></label><p className="field-hint">Untuk TikTok, Instagram, atau situs lain, unduh videonya di alat Unduh media lalu pilih file di sini. File sumber dihapus setelah proses selesai.</p></div>}
                <div className="field"><label className="field-label" htmlFor="language">Bahasa ucapan</label><input id="language" className="control" list="language-list" value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="Cari bahasa atau pilih Auto" /><datalist id="language-list">{languages.map((item) => <option value={item} key={item} />)}</datalist><p className="field-hint">Auto mendeteksi bahasa. Pilih bahasa tertentu bila sudah diketahui.</p></div>
                <div className="field"><label className="field-label" htmlFor="transcript-name">Nama file hasil (opsional)</label><input id="transcript-name" className="control" value={name} onChange={(event) => setName(event.target.value)} placeholder="otomatis dari judul video" /></div>
              </>}

              {feature === "download" && <>
                <div className="field"><label className="field-label" htmlFor="platform">Platform</label><select id="platform" className="control select-control" value={platform} onChange={(event) => { if (mediaCapture) fetch(API + "/api/media-captures/" + mediaCapture.id, { method: "DELETE" }).catch(() => {}); setMediaCapture(null); setPlatform(event.target.value); }}>{["YouTube", "Instagram", "TikTok", "Twitter/X", "Link umum"].map((item) => <option key={item}>{item}</option>)}</select></div>
                <div className="field"><label className="field-label" htmlFor="download-url">Tautan video atau posting foto</label><input id="download-url" className="control" type="url" value={downloadUrl} onChange={(event) => setDownloadUrl(event.target.value)} placeholder={platform === "Instagram" ? "Tempel tautan posting atau reel Instagram" : platform === "TikTok" ? "Tempel tautan video atau foto TikTok" : platform === "Link umum" ? "Tempel tautan halaman video atau file video langsung" : "Tempel tautan video"} /><p className="field-hint">{platform === "Instagram" ? "Posting foto dan carousel ditampilkan per foto; tautan reel/video tetap diunduh sebagai video." : platform === "TikTok" ? "Posting foto ditampilkan per foto. Video memakai TikWM tanpa login, lalu diubah ke H.264 MP4 agar kompatibel di Windows. URL publik video dikirim ke TikWM." : platform === "Link umum" ? "Mencoba halaman video dan tautan file langsung dari website publik. Website dengan DRM, login wajib, atau proteksi khusus mungkin tidak dapat diunduh." : "Tempel tautan video publik dari platform yang dipilih."}</p>
                  {platform === "Link umum" && <><button type="button" className="secondary-button" onClick={openMediaCapture} disabled={!downloadUrl.trim()}><ExternalLink size={15} />Buka halaman & deteksi video</button>{mediaCapture && <div className="capture-panel" aria-live="polite"><p className="field-hint">{mediaCapture.message}</p>{!(["failed", "cancelled"].includes(mediaCapture.state)) && <button type="button" className="text-button" onClick={() => { fetch(API + "/api/media-captures/" + mediaCapture.id, { method: "DELETE" }).catch(() => {}); setMediaCapture(null); }}>Tutup browser</button>}{mediaCapture.candidates.map((candidate, index) => <div className="capture-candidate" key={candidate.url}><span>{candidate.type || "Sumber media"} · {index + 1}</span><button type="button" className="text-button" onClick={() => useCapturedMedia(candidate.url)}>Gunakan sumber ini</button><code>{candidate.url}</code></div>)}</div>}</>}
                </div>
                {platform !== "TikTok" && <div className="field"><label className="field-label">Kualitas</label><div className="choice-row">{["Terbaik", "1080p", "720p"].map((value) => <label className="choice" key={value}><input type="radio" checked={downloadQuality === value} onChange={() => setDownloadQuality(value)} />{value}</label>)}</div></div>}
                <div className="field"><label className="field-label" htmlFor="download-name">Nama file (opsional)</label><input id="download-name" className="control" value={name} onChange={(event) => setName(event.target.value)} placeholder="otomatis dari judul video" /></div>
              </>}

              <div className="button-row">
                <button className="primary-button" type="submit" disabled={busy || currentJobActive || uploading || (feature === "video" && !uploaded && videoBatchUploads.length === 0) || (feature === "photo" && !uploaded) || (feature === "transcription" && transcriptionSource === "file" && !transcriptionUpload?.id)}>
                  {busy || currentJobActive ? <><LoaderCircle size={16} className="spin" /> Sedang diproses</> : <><WandSparkles size={16} />{featureAction(feature)}</>}
                </button>
                {currentJobActive && <button className="danger-button" type="button" onClick={cancelJob} aria-label="Batalkan proses"><X size={16} /></button>}
              </div>
              {error && job?.state !== "failed" && <div className="error-box" role="alert">{error}</div>}
              {showResult && jobResult && <div className="success-box"><Check size={14} style={{ verticalAlign: "-3px", marginRight: 5 }} />{job?.state === "cancelled" ? "Dibatalkan · hasil sebagian" : "Selesai"}{jobResult.items ? ` · ${jobResult.items.filter((item) => item.status === "completed").length}/${jobResult.items.length} video berhasil` : jobResult.title ? " · " + jobResult.title : ""}{jobResult.words ? " · " + jobResult.words + " kata" : ""}{jobResult.images ? " · " + jobResult.images + " foto" : ""}</div>}
              {showResult && jobResult?.notice && <p className="field-hint">{jobResult.notice}</p>}
              <div className="privacy-note"><ShieldCheck size={15} />Hasil dan riwayat disimpan sementara di cache lokal maksimal 7 hari. Simpan salinan file hanya dengan menekan tombol unduh.</div>
            </div>

            <div className="result-column">
              <div className="result-heading">
                <h3>Pratinjau &amp; hasil</h3>
                <span className="result-meta">
                  {jobResult && showResult
                    ? "Siap disimpan"
                    : uploading
                    ? "Menyiapkan pratinjau media"
                    : feature === "download" && mediaCapture
                    ? "Deteksi halaman aktif"
                    : busy || (job && job.kind === feature && !showResult)
                    ? "Konsol pemrosesan aktif"
                    : "Hasil akan muncul di sini"}
                </span>
              </div>

              {uploading ? (
                <div className="media-capture-status" role="status" aria-live="polite">
                  <div className="media-capture-icon"><LoaderCircle size={22} className="spin" /></div>
                  <b>{uploadProgress !== null && uploadProgress < 1 ? "Mengunggah file" : "Menyiapkan pratinjau media"}</b>
                  <p>{uploadProgress !== null && uploadProgress < 1 ? `${Math.round(uploadProgress * 100)}% file terkirim` : "File terkirim. Backend sedang membaca media dan membuat pratinjau."}</p>
                  <span>Waktu berjalan · {String(Math.floor(uploadElapsed / 60)).padStart(2, "0")}:{String(uploadElapsed % 60).padStart(2, "0")}</span>
                  <div className={`processing-track ${uploadProgress === null || uploadProgress >= 1 ? "is-indeterminate" : ""}`}><span style={uploadProgress !== null && uploadProgress < 1 ? { width: `${uploadProgress * 100}%` } : undefined} /></div>
                </div>
              ) : busy || (job && job.kind === feature && !showResult) ? (
                <TerminalProcessingView
                  job={job}
                  busy={busy}
                  featureTitle={currentFeature.label}
                  hasPartialResult={job?.state === "cancelled" && Boolean(job.result?.items?.length)}
                  onViewResult={() => setShowResult(true)}
                  onCancel={cancelJob}
                />
              ) : feature === "download" && mediaCapture ? (
                <div className="media-capture-status" role="status" aria-live="polite">
                  <div className="media-capture-icon">{["failed", "cancelled"].includes(mediaCapture.state) ? <X size={22} /> : mediaCapture.state === "waiting" ? <Monitor size={22} /> : <LoaderCircle size={22} className="spin" />}</div>
                  <b>{mediaCapture.state === "waiting" ? "Halaman siap diputar" : mediaCapture.state === "found" ? "Sumber video terdeteksi" : mediaCapture.state === "failed" ? "Halaman tidak dapat dibuka" : "Membuka halaman video"}</b>
                  <p>{mediaCapture.message}</p>
                  <span>{mediaCapture.state === "waiting" ? "Tekan Play di jendela browser yang terbuka." : mediaCapture.state === "found" ? "Pilih sumber media di panel tautan untuk melanjutkan." : "Menunggu respons website…"} · {String(Math.floor(captureElapsed / 60)).padStart(2, "0")}:{String(captureElapsed % 60).padStart(2, "0")}</span>
                  {!["waiting", "found", "failed", "cancelled"].includes(mediaCapture.state) && <div className="processing-track is-indeterminate"><span /></div>}
                </div>
              ) : showResult && jobResult ? (
                <div>
                  <div className="result-nav-bar">
                    <div className="result-status-pill">
                      <Check size={14} strokeWidth={3} />
                      <span>{job?.state === "cancelled" ? "Hasil sebagian tersedia" : "Hasil siap ditampilkan"}</span>
                    </div>
                    <button
                      type="button"
                      className="btn-show-terminal"
                      onClick={() => setShowResult(false)}
                      title="Kembali ke tampilan terminal log"
                    >
                      <Terminal size={13} />
                      <span>Lihat Log Terminal</span>
                    </button>
                  </div>

                  {feature === "video" && jobResult.items ? (
                    <div className="video-batch-results">{jobResult.items.map((item, index) => <article className="video-batch-result" key={`${item.filename}-${index}`}>
                      <b>{item.filename}</b>
                      {item.status === "completed" ? <>
                        {item.preview_key && files?.[item.preview_key] && <video className="preview-video" src={fileUrl(files[item.preview_key])} controls playsInline preload="metadata" />}
                        {item.result_key && <FileDownload file={files?.[item.result_key]} />}
                      </> : <p className="error-box">Gagal diproses: {item.error || "Kesalahan tidak diketahui."}</p>}
                    </article>)}</div>
                  ) : feature === "video" && files?.preview ? (
                    <>
                      <video className="preview-video" src={fileUrl(files.preview)} controls playsInline preload="metadata" />
                      <FileDownload file={files.result} />
                      <p className="field-hint">Pratinjau hanya menampilkan 5 detik pertama. File lengkap dapat disimpan lewat tombol di atas.</p>
                    </>
                  ) : feature === "photo" && files?.result ? (
                    <>
                      <img className="preview-image" src={fileUrl(files.result)} alt="Hasil foto tanpa latar" />
                      <FileDownload file={files.result} />
                    </>
                  ) : feature === "download" && files?.result ? (
                    <>
                      <video className="preview-video" src={fileUrl(files.result)} controls playsInline preload="metadata" />
                      <div className="result-meta result-size">{jobResult?.size ? (jobResult.size / 1048576).toFixed(1) + " MB" : ""}</div>
                      <FileDownload file={files.result} />
                    </>
                  ) : feature === "download" && files && jobResult?.images ? (
                    <div className="photo-gallery">
                      {Object.entries(files).map(([key, file], index) => (
                        <article className="photo-card" key={key}>
                          <img className="preview-image" src={fileUrl(file)} alt={`Foto ${index + 1}`} />
                          <div className="photo-card-footer">
                            <span>Foto {index + 1}</span>
                            <a className="secondary-button" href={fileUrl(file, true)}><ArrowDownToLine size={15} />Unduh</a>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : feature === "transcription" && jobResult?.text ? (
                    <>
                      <TranscriptWorkspace jobId={job?.id ?? ""} jsonUrl={files?.json?.url} initialText={jobResult.text} filename={files?.txt?.filename?.replace(/\.txt$/i, "-koreksi.txt")} mediaUrl={transcriptionSource === "file" ? transcriptionUpload?.previewUrl : undefined} mediaType={transcriptionUpload?.mediaType} onLocalSourceDetected={markTranscriptionFileSource} />
                      <p className="field-hint">File asli dari model:</p>
                      <div className="file-links">
                        {["txt", "srt", "vtt", "json"].map((key) => (
                          <a className="file-link" href={fileUrl(files?.[key], true)} key={key}>
                            <FileText size={14} />{key === "json" ? "JSON timestamp kata" : `${key.toUpperCase()} asli`}
                          </a>
                        ))}
                      </div>
                    </>
                  ) : null}
                </div>
              ) : (
                <div className="empty-preview">
                  <div>
                    <Monitor size={25} />
                    <div>Pilih alat dan mulai pekerjaan.<br />Pratinjau akan tampil di area ini.</div>
                  </div>
                </div>
              )}
            </div>
          </form>
        </section>
      </div>
      <footer className="footer">MYTOOLS · WORKSPACE LOKAL PRIBADI</footer>
    </main>
  );
}

function FileDownload({ file }: { file?: FileResult }) {
  if (!file) return null;
  return <div className="result-download"><div className="file-result"><FileText size={16} /><span>{file.filename}</span></div><a className="secondary-button" href={fileUrl(file, true)}><ArrowDownToLine size={15} />Simpan file</a></div>;
}

function featureDescription(feature: Feature) {
  return {
    video: "Hilangkan latar video dengan model lokal. Pilih manusia atau tandai objek yang ingin dipertahankan.",
    photo: "Buat foto transparan. Pilih deteksi manusia atau tandai objek secara manual.",
    transcription: "Transkripsikan audio YouTube atau file audio/video dengan teks multilingual dan timestamp per kata.",
    download: "Unduh video dari YouTube, Instagram, TikTok, Twitter/X, atau tautan umum. Foto dan carousel TikTok serta Instagram ditampilkan sebagai galeri.",
  }[feature];
}
function featureAction(feature: Feature) {
  return { video: "Proses video", photo: "Hapus latar", transcription: "Buat transkrip", download: "Unduh media" }[feature];
}
