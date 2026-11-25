"use client";

import {
  ArrowDownToLine, Check, ChevronRight, Database, ExternalLink,
  FileSpreadsheet, FileText, Info, LoaderCircle, LockKeyhole, Monitor,
  Scissors, ShieldCheck, Sparkles, Star, Terminal, WandSparkles, X
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { ToolNavigation } from "@/components/tool-navigation";
import { TerminalProcessingView } from "@/components/terminal-processing-view";

type FileResult = { url: string; filename: string };
type PreviewReview = {
  review_id: number;
  username: string;
  rating_bintang: number;
  tanggal: string;
  varian: string;
  ulasan: string;
  jumlah_foto: number;
  link_foto: string;
  jumlah_video: number;
  respon_penjual: string;
  like_count: number;
};
type ScrapingJob = {
  id: string;
  kind: "scraping";
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
    title?: string;
    total?: number;
    preview_rows?: PreviewReview[];
    files: Record<string, FileResult>;
  } | null;
};

const API = process.env.NODE_ENV === "development" ? "http://127.0.0.1:7860" : "";

async function responseJson(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Permintaan gagal. Coba lagi.");
  return body;
}

function fileUrl(file?: FileResult, download = false) {
  return file ? API + file.url + (download ? "?download=1" : "") : "";
}

export default function ScrapingPage() {
  const [gpu, setGpu] = useState<string | null>(null);
  const [backendReady, setBackendReady] = useState(false);

  // Form states
  const [url, setUrl] = useState("");
  const [limit, setLimit] = useState(50);
  const [star, setStar] = useState(0);
  const [mediaOnly, setMediaOnly] = useState(false);
  const [commentOnly, setCommentOnly] = useState(false);
  const [useBrowser, setUseBrowser] = useState(false);
  const [cookie, setCookie] = useState("");
  const [name, setName] = useState("");
  const [showCookieGuide, setShowCookieGuide] = useState(false);

  // Job states
  const [job, setJob] = useState<ScrapingJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showResult, setShowResult] = useState(false);

  useEffect(() => {
    fetch(API + "/api/health")
      .then(responseJson)
      .then((data) => {
        setGpu(data.gpu);
        setBackendReady(true);
      })
      .catch(() => setBackendReady(false));

    // Load saved cookie from localStorage
    const savedCookie = localStorage.getItem("shopee_cookie");
    if (savedCookie) setCookie(savedCookie);

    const requestedJob = new URLSearchParams(window.location.search).get("job");
    if (requestedJob) {
      fetch(API + "/api/jobs/" + requestedJob, { cache: "no-store" }).then(responseJson).then((restored: ScrapingJob) => {
        if (restored.kind === "scraping") {
          setJob(restored);
          setShowResult(false);
        }
      }).catch(() => setError("Pekerjaan ini sudah tidak tersedia. Mungkin server lokal telah dimulai ulang."));
    }
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
        const snapshot: ScrapingJob = await responseJson(response);
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

  function handleCookieChange(val: string) {
    setCookie(val);
    localStorage.setItem("shopee_cookie", val);
  }

  async function startScraping(event: FormEvent) {
    event.preventDefault();
    if (!url.trim()) {
      setError("Masukkan tautan produk Shopee terlebih dahulu.");
      return;
    }

    setError("");
    setJob(null);
    setShowResult(false);
    setBusy(true);

    const payload = {
      kind: "scraping",
      url: url.trim(),
      limit,
      star,
      media_only: mediaOnly,
      comment_only: commentOnly,
      use_browser: useBrowser,
      cookie: cookie.trim(),
      name: name.trim(),
    };

    try {
      const form = new FormData();
      form.append("payload", JSON.stringify(payload));
      const created: ScrapingJob = await responseJson(
        await fetch(API + "/api/jobs", { method: "POST", body: form })
      );
      setJob(created);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Proses scraping gagal.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelJob() {
    if (job) {
      await fetch(API + "/api/jobs/" + job.id + "/cancel", { method: "POST" }).catch(() => {});
    }
  }

  const jobResult = job?.state === "completed" ? job.result : null;
  const currentJobActive = job?.state === "queued" || job?.state === "running";
  const files = jobResult?.files;
  const previewRows = jobResult?.preview_rows || [];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <Scissors size={21} strokeWidth={2.3} />
          </div>
          <div>
            <p className="brand-name">MyTools</p>
            <p className="brand-caption">Studio lokal untuk pekerjaan media &amp; data</p>
          </div>
        </div>
        <div className="local-status">
          <span className={"status-dot " + (backendReady ? "" : "offline")} />
          {gpu || (backendReady ? "Backend lokal aktif" : "Menghubungkan…")}
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <ToolNavigation activeTool="scraping" />
          <div className="sidebar-tip">
            <strong>
              <LockKeyhole size={13} style={{ verticalAlign: "-2px", marginRight: 5 }} />
              Scraping Lokal &amp; Aman
            </strong>
            Data ulasan diproses dan disimpan langsung di PC Anda tanpa melalui server perantara.
          </div>
        </aside>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">Scraping Ulasan Produk Shopee</h2>
              <p className="panel-description">
                Ekstrak ulasan pembeli secara akurat, lengkap dengan rating bintang, varian produk, foto pembeli, dan respon penjual ke format CSV &amp; JSON.
              </p>
            </div>
            <ChevronRight size={18} color="#a0aaa5" />
          </div>

          <form onSubmit={startScraping} className="panel-body">
            <div className="form-column">
              <div className="field">
                <label className="field-label" htmlFor="shopee-url">
                  URL Produk Shopee
                </label>
                <input
                  id="shopee-url"
                  className="control"
                  type="url"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://shopee.co.id/product/42702581/23081198424 atau link produk Shopee..."
                />
                <p className="field-hint">
                  Mendukung format link standar Shopee, shortlink (s.shopee.co.id / shope.ee), dan format i.shopid.itemid.
                </p>
              </div>

              <div className="field">
                <label className="field-label" htmlFor="review-limit">
                  Jumlah Ulasan Target
                </label>
                <select
                  id="review-limit"
                  className="control select-control"
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value))}
                >
                  <option value={20}>20 ulasan (Cepat)</option>
                  <option value={50}>50 ulasan (Rekomendasi)</option>
                  <option value={100}>100 ulasan</option>
                  <option value={200}>200 ulasan</option>
                  <option value={500}>500 ulasan (Maksimal batch)</option>
                </select>
              </div>

              <div className="field">
                <label className="field-label" htmlFor="star-filter">
                  Filter Rating Bintang
                </label>
                <select
                  id="star-filter"
                  className="control select-control"
                  value={star}
                  onChange={(e) => setStar(Number(e.target.value))}
                >
                  <option value={0}>Semua Rating (Bintang 1 - 5)</option>
                  <option value={5}>⭐⭐⭐⭐⭐ Hanya Bintang 5</option>
                  <option value={4}>⭐⭐⭐⭐ Hanya Bintang 4</option>
                  <option value={3}>⭐⭐⭐ Hanya Bintang 3</option>
                  <option value={2}>⭐⭐ Hanya Bintang 2</option>
                  <option value={1}>⭐ Hanya Bintang 1 (Ulasan Negatif)</option>
                </select>
              </div>

              <div className="field">
                <label className="field-label">Filter Tambahan</label>
                <div className="choice-row">
                  <label className="choice">
                    <input
                      type="checkbox"
                      checked={commentOnly}
                      onChange={(e) => setCommentOnly(e.target.checked)}
                    />
                    Hanya yang ada teks komentar
                  </label>
                  <label className="choice">
                    <input
                      type="checkbox"
                      checked={mediaOnly}
                      onChange={(e) => setMediaOnly(e.target.checked)}
                    />
                    Hanya yang ada foto / video
                  </label>
                </div>
              </div>

              <div className="field">
                <label className="field-label">Metode Ekstraksi</label>
                <div className="choice-row">
                  <label className="choice">
                    <input
                      type="radio"
                      checked={!useBrowser}
                      onChange={() => setUseBrowser(false)}
                    />
                    API Cepat (Direkomendasikan)
                  </label>
                  <label className="choice">
                    <input
                      type="radio"
                      checked={useBrowser}
                      onChange={() => setUseBrowser(true)}
                    />
                    Browser Otomatis (Playwright)
                  </label>
                </div>
                <p className="field-hint">
                  {!useBrowser
                    ? "Mode API sangat cepat (ratusan ulasan per detik). Butuh Cookie Shopee jika terkena blokir 403."
                    : "Mode browser menjalankan Chrome terisolasi untuk melewati bot-detection secara alami."}
                </p>
              </div>

              <div className="field">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <label className="field-label" htmlFor="shopee-cookie">
                    Cookie Sesi Shopee (Wajib untuk Akun / Anti-Bot)
                  </label>
                  <button
                    type="button"
                    className="text-button"
                    style={{ fontSize: 11, marginBottom: 7, color: "var(--accent-dark)", background: "transparent", border: 0, cursor: "pointer" }}
                    onClick={() => setShowCookieGuide(!showCookieGuide)}
                  >
                    <Info size={12} style={{ verticalAlign: "-2px", marginRight: 3 }} />
                    {showCookieGuide ? "Tutup panduan" : "Cara dapatkan cookie"}
                  </button>
                </div>
                {showCookieGuide && (
                  <div style={{ padding: 12, marginBottom: 10, borderRadius: 10, background: "#f0fdf9", border: "1px solid #ccfbf1", fontSize: 11.5, lineHeight: 1.6, color: "#134e4a" }}>
                    <strong>Panduan Cepat Salin Cookie Shopee:</strong><br />
                    1. Buka <code>shopee.co.id</code> di Chrome / Edge Anda tempat Anda sudah login akun Shopee.<br />
                    2. Buka link produk ini, tekan <b>F12</b> ➔ Masuk tab <b>Network</b> ➔ Refresh halaman.<br />
                    3. Klik salah satu request (misal ke <code>shopee.co.id</code>) ➔ Di panel kanan cari <b>Request Headers</b> ➔ Salin nilai <b>Cookie</b> dan tempel ke bawah ini.<br />
                    <span style={{ color: "#0d9488" }}><i>* Cookie akan tersimpan otomatis di browser ini sehingga Anda cukup menempelkannya sekali saja.</i></span>
                  </div>
                )}
                <input
                  id="shopee-cookie"
                  className="control"
                  type="password"
                  value={cookie}
                  onChange={(e) => handleCookieChange(e.target.value)}
                  placeholder="Tempel string Cookie di sini (SPC_EC=...; SPC_F=...; _sapid=...)"
                />
                <p className="field-hint">
                  {cookie ? (
                    <span style={{ color: "var(--accent-dark)", fontWeight: 500 }}>
                      ✓ Cookie sesi Shopee tersimpan secara lokal.
                    </span>
                  ) : (
                    "Shopee memblokir akses tamu tanpa login (Error 90309999). Tempel cookie akun Shopee Anda untuk hasil 100% akurat."
                  )}
                </p>
              </div>

              <div className="field">
                <label className="field-label" htmlFor="output-name">
                  Nama File Hasil (Opsional)
                </label>
                <input
                  id="output-name"
                  className="control"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="otomatis dari ID produk"
                />
              </div>

              <div className="button-row" style={{ marginTop: 20 }}>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={busy || currentJobActive || !url.trim()}
                >
                  {busy || currentJobActive ? (
                    <>
                      <LoaderCircle size={16} className="spin" /> Sedang mengambil ulasan…
                    </>
                  ) : (
                    <>
                      <WandSparkles size={16} /> Mulai Scraping Ulasan
                    </>
                  )}
                </button>
                {currentJobActive && (
                  <button
                    className="danger-button"
                    type="button"
                    onClick={cancelJob}
                    aria-label="Batalkan proses"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              {error && job?.state !== "failed" && (
                <div className="error-box" role="alert" style={{ marginTop: 14 }}>
                  {error}
                </div>
              )}

              {showResult && jobResult && (
                <div className="success-box" style={{ marginTop: 14 }}>
                  <Check size={14} style={{ verticalAlign: "-3px", marginRight: 5 }} />
                  Berhasil mengekstrak <strong>{jobResult.total} ulasan</strong>!
                </div>
              )}

              <div className="privacy-note" style={{ marginTop: 20 }}>
                <ShieldCheck size={15} />
                Data diekstrak langsung ke folder output lokal komputer Anda (<code>data/outputs/</code>).
              </div>
            </div>

            <div className="result-column">
              <div className="result-heading">
                <h3>Hasil &amp; Unduhan</h3>
                <span className="result-meta">
                  {jobResult && showResult
                    ? `${jobResult.total} ulasan siap diunduh`
                    : busy || (job && !showResult)
                    ? "Konsol scraping aktif"
                    : "Hasil akan muncul di sini"}
                </span>
              </div>

              {busy || (job && !showResult) ? (
                <TerminalProcessingView
                  job={job}
                  busy={busy}
                  featureTitle="Scraping Ulasan Shopee"
                  onViewResult={() => setShowResult(true)}
                  onCancel={cancelJob}
                />
              ) : showResult && jobResult && files ? (
                <div style={{ display: "grid", gap: 16 }}>
                  <div className="result-nav-bar">
                    <div className="result-status-pill">
                      <Check size={14} strokeWidth={3} />
                      <span>{jobResult.total} ulasan berhasil diekstrak</span>
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

                  {/* Download Cards */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    {files.csv && (
                      <a
                        href={fileUrl(files.csv, true)}
                        className="secondary-button"
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 6,
                          padding: "16px 14px",
                          borderRadius: 12,
                          background: "#f0fdf9",
                          border: "1.5px solid #0d9488",
                          color: "#0f766e",
                          textDecoration: "none",
                          fontWeight: 700,
                        }}
                      >
                        <FileSpreadsheet size={24} color="#0d9488" />
                        <span>Unduh CSV (Excel)</span>
                        <small style={{ fontSize: 10.5, fontWeight: 500, color: "#697772" }}>
                          Format tabel rapi UTF-8
                        </small>
                      </a>
                    )}
                    {files.json && (
                      <a
                        href={fileUrl(files.json, true)}
                        className="secondary-button"
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 6,
                          padding: "16px 14px",
                          borderRadius: 12,
                          background: "#ffffff",
                          border: "1.5px solid var(--border)",
                          color: "var(--text)",
                          textDecoration: "none",
                          fontWeight: 700,
                        }}
                      >
                        <FileText size={24} color="#697772" />
                        <span>Unduh JSON</span>
                        <small style={{ fontSize: 10.5, fontWeight: 500, color: "#697772" }}>
                          Format data terstruktur
                        </small>
                      </a>
                    )}
                  </div>

                  {/* Integration button with Decision Support */}
                  <div style={{ padding: 14, borderRadius: 12, background: "#fdf8ee", border: "1px solid #fed7aa", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                    <div>
                      <strong style={{ display: "block", fontSize: 12.5, color: "#9a3412" }}>
                        Ingin menganalisis ulasan ini?
                      </strong>
                      <span style={{ fontSize: 11.5, color: "#c2410c" }}>
                        Unggah file CSV ini ke modul Analisis &amp; Perbandingan untuk melihat aspek kepuasan pembeli (IndoBERT).
                      </span>
                    </div>
                    <a
                      href="/decision-support"
                      className="secondary-button"
                      style={{ fontSize: 12, padding: "7px 12px", whiteSpace: "nowrap", border: "1px solid #ea580c", color: "#c2410c", textDecoration: "none", fontWeight: 700 }}
                    >
                      Buka Analisis <ExternalLink size={12} style={{ marginLeft: 4 }} />
                    </a>
                  </div>

                  {/* Preview Table */}
                  {previewRows.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <h4 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 750, color: "var(--text)" }}>
                        Pratinjau Ulasan ({Math.min(previewRows.length, 10)} pertama):
                      </h4>
                      <div
                        style={{
                          maxHeight: 460,
                          overflowY: "auto",
                          border: "1px solid var(--border)",
                          borderRadius: 12,
                          background: "#fff",
                        }}
                      >
                        {previewRows.map((r, i) => (
                          <div
                            key={r.review_id || i}
                            style={{
                              padding: "12px 14px",
                              borderBottom: i < previewRows.length - 1 ? "1px solid #edf0ee" : "none",
                              fontSize: 12.5,
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span style={{ fontWeight: 700, color: "#17211e" }}>{r.username}</span>
                                {r.varian && (
                                  <span style={{ fontSize: 10.5, padding: "2px 6px", borderRadius: 4, background: "#f1f5f3", color: "#53615c" }}>
                                    {r.varian}
                                  </span>
                                )}
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: 2, color: "#eab308" }}>
                                {Array.from({ length: 5 }).map((_, idx) => (
                                  <Star
                                    key={idx}
                                    size={13}
                                    fill={idx < r.rating_bintang ? "#eab308" : "none"}
                                    color={idx < r.rating_bintang ? "#eab308" : "#cbd5e1"}
                                  />
                                ))}
                                <span style={{ fontSize: 11, marginLeft: 4, color: "#8a9691" }}>
                                  {r.tanggal ? r.tanggal.split(" ")[0] : ""}
                                </span>
                              </div>
                            </div>
                            <p style={{ margin: "4px 0", color: "#374151", lineHeight: 1.5 }}>
                              {r.ulasan || <em style={{ color: "#9ca3af" }}>(Pembeli tidak menyertakan komentar teks)</em>}
                            </p>
                            {r.jumlah_foto > 0 && (
                              <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                                {r.link_foto.split(" | ").slice(0, 4).map((imgUrl, imgIdx) => (
                                  <a key={imgIdx} href={imgUrl} target="_blank" rel="noopener noreferrer">
                                    <img
                                      src={imgUrl}
                                      alt="Foto ulasan"
                                      style={{ width: 44, height: 44, objectFit: "cover", borderRadius: 6, border: "1px solid #e5eae7" }}
                                    />
                                  </a>
                                ))}
                              </div>
                            )}
                            {r.respon_penjual && (
                              <div style={{ marginTop: 6, padding: "6px 10px", borderRadius: 6, background: "#f8faf9", borderLeft: "3px solid #0d9488", fontSize: 11.5, color: "#475569" }}>
                                <strong>Respon Penjual:</strong> {r.respon_penjual}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="empty-preview">
                  <div>
                    <Database size={26} color="#8a9691" />
                    <div>
                      Masukkan URL produk Shopee dan tekan mulai.<br />
                      Ulasan yang diekstrak akan ditampilkan dan dapat diunduh di sini.
                    </div>
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

