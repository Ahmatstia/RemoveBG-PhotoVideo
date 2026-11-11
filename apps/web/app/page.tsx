"use client";

import {
  ArrowDownToLine, AudioLines, Check, ChevronRight, Clapperboard, ExternalLink, FileText,
  LoaderCircle, LockKeyhole, Monitor, MousePointer2, Scissors,
  ShieldCheck, Sparkles, Upload, WandSparkles, X,
} from "lucide-react";
import { ChangeEvent, FormEvent, MouseEvent, useEffect, useState } from "react";
import { ToolNavigation, type MediaTool } from "@/components/tool-navigation";

type Feature = MediaTool;
type Point = { x: number; y: number; keep: boolean };
type Uploaded = {
  id: string;
  kind: string;
  preview_url: string;
  details: { width: number; height: number; duration?: number; fps?: number; has_audio?: boolean };
};
type FileResult = { url: string; filename: string };
type Job = {
  id: string;
  kind: Feature;
  state: "queued" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string;
  error?: string | null;
  result?: {
    title?: string; text?: string; words?: number; sentences?: number; size?: number; images?: number; notice?: string;
    report?: { frames: number; processed_seconds: number };
    files: Record<string, FileResult>;
  } | null;
};
type MediaCapture = { id: string; state: string; message: string; candidates: { url: string; type: string; status: number }[] };
const API = process.env.NODE_ENV === "development" ? "http://127.0.0.1:7860" : "";
const FEATURES: { id: Feature; label: string }[] = [
  { id: "video", label: "Hapus latar video" },
  { id: "photo", label: "Hapus latar foto" },
  { id: "transcription", label: "Transkripsi YouTube" },
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

export default function Home() {
  const [feature, setFeature] = useState<Feature>("video");
  const [gpu, setGpu] = useState<string | null>(null);
  const [languages, setLanguages] = useState<string[]>(["Auto"]);
  const [uploaded, setUploaded] = useState<Uploaded | null>(null);
  const [uploading, setUploading] = useState(false);
  const [mode, setMode] = useState("Manusia");
  const [quality, setQuality] = useState("Detail");
  const [exportKind, setExportKind] = useState("transparent");
  const [pointKind, setPointKind] = useState(true);
  const [points, setPoints] = useState<Point[]>([]);
  const [name, setName] = useState("");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [language, setLanguage] = useState("Auto");
  const [platform, setPlatform] = useState("YouTube");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [downloadQuality, setDownloadQuality] = useState("Terbaik");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [backendReady, setBackendReady] = useState(false);
  const [mediaCapture, setMediaCapture] = useState<MediaCapture | null>(null);

  useEffect(() => {
    const requestedTool = new URLSearchParams(window.location.search).get("tool") as Feature | null;
    if (FEATURES.some((item) => item.id === requestedTool)) setFeature(requestedTool!);
    fetch(API + "/api/health").then(responseJson).then((data) => { setGpu(data.gpu); setBackendReady(true); }).catch(() => setBackendReady(false));
    fetch(API + "/api/languages").then(responseJson).then((data) => setLanguages(data.languages)).catch(() => {});
  }, []);

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

  async function uploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const kind = feature === "photo" ? "photo" : "video";
    setError(""); setJob(null); setPoints([]); setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file); form.append("kind", kind);
      const response = await fetch(API + "/api/uploads", { method: "POST", body: form });
      const data: Uploaded = await responseJson(response);
      setUploaded(data);
      setName(file.name.replace(/\.[^.]+$/, "-hasil"));
    } catch (reason) {
      setUploaded(null);
      setError(reason instanceof Error ? reason.message : "Gagal mengunggah file.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  function discardUpload(id: string) {
    fetch(API + "/api/uploads/" + id, { method: "DELETE" }).catch(() => {});
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
    event.preventDefault(); setError(""); setJob(null);
    let payload: Record<string, unknown>;
    if (feature === "video" || feature === "photo") {
      if (!uploaded) { setError("Pilih file terlebih dahulu."); return; }
      payload = {
        kind: feature, upload_id: uploaded.id, mode,
        ...(feature === "video" ? { quality: quality, export: exportKind } : {}),
        points: points.map((point) => [point.x, point.y, point.keep ? 1 : 0]), name,
      };
    } else if (feature === "transcription") {
      payload = { kind: feature, url: youtubeUrl, language, name };
    } else {
      payload = { kind: "download", url: downloadUrl, platform, quality: downloadQuality, name };
    }
    setBusy(true);
    try {
      const form = new FormData(); form.append("payload", JSON.stringify(payload));
      const created: Job = await responseJson(await fetch(API + "/api/jobs", { method: "POST", body: form }));
      setJob(created);
      for (;;) {
        const snapshot: Job = await responseJson(await fetch(API + "/api/jobs/" + created.id, { cache: "no-store" }));
        setJob(snapshot);
        if (snapshot.state === "completed") break;
        if (snapshot.state === "failed") { setError(snapshot.error || "Proses gagal."); break; }
        if (snapshot.state === "cancelled") break;
        await new Promise((resolve) => window.setTimeout(resolve, 700));
      }
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
    if (mediaCapture) fetch(API + "/api/media-captures/" + mediaCapture.id, { method: "DELETE" }).catch(() => {});
    setMediaCapture(null);
    if (uploaded) discardUpload(uploaded.id);
    setFeature(next); setError(""); setJob(null); setUploaded(null); setPoints([]); setName("");
  }

  const currentFeature = FEATURES.find((item) => item.id === feature)!;
  const jobResult = job?.kind === feature && job.state === "completed" ? job.result : null;
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
        <ToolNavigation activeTool={feature} onSelectTool={chooseFeature} />
      </div>

      <div className="workspace">
        <aside className="sidebar">
          <ToolNavigation activeTool={feature} onSelectTool={chooseFeature} />
          <div className="sidebar-tip"><strong><LockKeyhole size={13} style={{ verticalAlign: "-2px", marginRight: 5 }} />Dijalankan lokal</strong>Hasil tersimpan sementara. Unduh file hanya saat kamu memilihnya.</div>
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
                  {uploaded ? <div>
                    <div className={"source-preview " + (mode === "Objek umum" ? "interactive" : "")} style={{ width: "min(100%, " + (420 * uploaded.details.width / uploaded.details.height) + "px)", aspectRatio: uploaded.details.width + " / " + uploaded.details.height }} onClick={addPoint}>
                      <img src={API + uploaded.preview_url} alt="Pratinjau sumber" />
                      {points.map((point, index) => <span key={index} className={"point-marker " + (point.keep ? "keep" : "remove")} style={{ left: (point.x / uploaded.details.width * 100) + "%", top: (point.y / uploaded.details.height * 100) + "%" }} />)}
                    </div>
                    <div className="preview-caption">
                      <span>{uploaded.details.width} × {uploaded.details.height}{uploaded.details.duration ? " · " + formatTime(uploaded.details.duration) : " · Foto"}</span>
                      <button type="button" className="text-button" onClick={() => { discardUpload(uploaded.id); setUploaded(null); }}>Ganti file</button>
                    </div>
                  </div> : <label className="upload-box">
                    <input type="file" accept={feature === "photo" ? ".png,.jpg,.jpeg,.webp" : ".mp4,.mov,.mkv,.avi,.webm"} onChange={uploadFile} />
                    {uploading ? <LoaderCircle className="spin" size={22} color="#0d9488" /> : <Upload size={22} color="#0d9488" />}
                    <span className="upload-title">{uploading ? "Menyiapkan pratinjau…" : "Pilih file dari komputer"}</span>
                    <span className="upload-subtitle">{feature === "photo" ? "PNG, JPG, WEBP · Maks. 40 MP" : "MP4, MOV, MKV, AVI, WEBM · Maks. 15 menit"}</span>
                  </label>}
                </div>
                <div className="field">
                  <label className="field-label">Mode subjek</label>
                  <div className="choice-row">{["Manusia", "Objek umum"].map((value) => <label className="choice" key={value}><input type="radio" checked={mode === value} onChange={() => setMode(value)} />{value === "Manusia" ? "Manusia otomatis" : "Objek dengan titik"}</label>)}</div>
                  {mode === "Objek umum" && <p className="field-hint"><MousePointer2 size={12} style={{ verticalAlign: "-2px" }} /> {feature === "photo" ? "Klik objek yang ingin dipertahankan pada foto sumber." : "Klik objek pada frame pertama. Titik hijau menyimpan, titik merah menghapus."}</p>}
                </div>
                {mode === "Objek umum" && uploaded && <div className="field"><div className="choice-row">
                  <button type="button" className={"choice-button " + (pointKind ? "selected" : "")} onClick={() => setPointKind(true)}>● Titik simpan</button>
                  <button type="button" className={"choice-button " + (!pointKind ? "selected remove" : "")} onClick={() => setPointKind(false)}>● Titik hapus</button>
                  <button type="button" className="text-button" onClick={() => setPoints([])}>Bersihkan titik{points.length ? " (" + points.length + ")" : ""}</button>
                </div></div>}
                <div className="field"><label className="field-label" htmlFor="output-name">Nama hasil</label><input id="output-name" className="control" value={name} onChange={(event) => setName(event.target.value)} placeholder="otomatis dari nama file" /></div>
                {feature === "video" && <>
                  <div className="field"><label className="field-label">Kualitas pemrosesan</label><div className="choice-row">{["Detail", "Cepat"].map((value) => <label className="choice" key={value}><input type="radio" checked={quality === value} onChange={() => setQuality(value)} />{value}</label>)}</div></div>
                  <div className="field"><label className="field-label" htmlFor="export-kind">Format hasil</label><select id="export-kind" className="control select-control" value={exportKind} onChange={(event) => setExportKind(event.target.value)}>{EXPORTS.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></div>
                </>}
              </>}

              {feature === "transcription" && <>
                <div className="field"><label className="field-label" htmlFor="youtube-url">Tautan video YouTube</label><input id="youtube-url" className="control" type="url" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=…" /><p className="field-hint">Audio diproses dengan Whisper multilingual. Video tidak disimpan oleh fitur ini.</p></div>
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
                <button className="primary-button" type="submit" disabled={busy || uploading || ((feature === "video" || feature === "photo") && !uploaded)}>
                  {busy ? <><LoaderCircle size={16} className="spin" /> Sedang diproses</> : <><WandSparkles size={16} />{featureAction(feature)}</>}
                </button>
                {busy && <button className="danger-button" type="button" onClick={cancelJob} aria-label="Batalkan proses"><X size={16} /></button>}
              </div>
              {job && job.kind === feature && <div className="progress-card" aria-live="polite"><div className="progress-top"><span>{job.message}</span><strong>{Math.round(job.progress * 100)}%</strong></div><div className="progress-track"><div className="progress-fill" style={{ width: Math.max(2, job.progress * 100) + "%" }} /></div></div>}
              {error && <div className="error-box" role="alert">{error}</div>}
              {job?.kind === feature && job.state === "cancelled" && <div className="error-box">Proses dibatalkan.</div>}
              {jobResult && <div className="success-box"><Check size={14} style={{ verticalAlign: "-3px", marginRight: 5 }} />Selesai{jobResult.title ? " · " + jobResult.title : ""}{jobResult.words ? " · " + jobResult.words + " kata" : ""}{jobResult.images ? " · " + jobResult.images + " foto" : ""}</div>}
              {jobResult?.notice && <p className="field-hint">{jobResult.notice}</p>}
              <div className="privacy-note"><ShieldCheck size={15} />Hasil ditampilkan di sini dan disimpan sementara. Simpan salinan hanya dengan menekan tombol unduh.</div>
            </div>

            <div className="result-column">
              <div className="result-heading"><h3>Pratinjau & hasil</h3><span className="result-meta">{jobResult ? "Siap disimpan" : "Hasil akan muncul di sini"}</span></div>
              {feature === "video" && files?.preview ? <><video className="preview-video" src={fileUrl(files.preview)} controls playsInline preload="metadata" /><FileDownload file={files.result} /><p className="field-hint">Pratinjau hanya menampilkan 5 detik pertama. File lengkap dapat disimpan lewat tombol di atas.</p></>
                : feature === "photo" && files?.result ? <><img className="preview-image" src={fileUrl(files.result)} alt="Hasil foto tanpa latar" /><FileDownload file={files.result} /></>
                : feature === "download" && files?.result ? <><video className="preview-video" src={fileUrl(files.result)} controls playsInline preload="metadata" /><div className="result-meta result-size">{jobResult?.size ? (jobResult.size / 1048576).toFixed(1) + " MB" : ""}</div><FileDownload file={files.result} /></>
                  : feature === "download" && files && jobResult?.images ? <div className="photo-gallery">{Object.entries(files).map(([key, file], index) => <article className="photo-card" key={key}><img className="preview-image" src={fileUrl(file)} alt={`Foto ${index + 1}`} /><div className="photo-card-footer"><span>Foto {index + 1}</span><a className="secondary-button" href={fileUrl(file, true)}><ArrowDownToLine size={15} />Unduh</a></div></article>)}</div>
                    : feature === "transcription" && jobResult?.text ? <><div className="transcript-output">{jobResult.text}</div><div className="file-links">{["txt", "srt", "vtt", "json"].map((key) => <a className="file-link" href={fileUrl(files?.[key], true)} key={key}><FileText size={14} />{key.toUpperCase()}</a>)}</div></>
                      : <div className="empty-preview"><div><Monitor size={25} /><div>Pilih alat dan mulai pekerjaan.<br />Pratinjau akan tampil di area ini.</div></div></div>}
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
    transcription: "Ubah ucapan YouTube menjadi teks multilingual dengan timestamp per kata.",
    download: "Unduh video dari YouTube, Instagram, TikTok, Twitter/X, atau tautan umum. Foto dan carousel TikTok serta Instagram ditampilkan sebagai galeri.",
  }[feature];
}
function featureAction(feature: Feature) {
  return { video: "Proses video", photo: "Hapus latar", transcription: "Buat transkrip", download: "Unduh media" }[feature];
}
