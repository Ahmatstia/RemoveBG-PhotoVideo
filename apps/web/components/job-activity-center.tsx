"use client";

import { CheckCircle2, ChevronDown, LoaderCircle, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

type JobSummary = {
  id: string;
  kind: string;
  state: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
};

const API = process.env.NODE_ENV === "development" ? "http://127.0.0.1:7860" : "";
const LABELS: Record<string, string> = {
  video: "Hapus latar video", photo: "Hapus latar foto", transcription: "Transkripsi",
  download: "Unduh media", scraping: "Scraping ulasan Shopee",
};

export function JobActivityCenter() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(Date.now());
  const hasActiveJobs = jobs.some((job) => job.state === "queued" || job.state === "running");

  useEffect(() => {
    let mounted = true;
    let initialized = false;
    let timer: number;
    const refresh = async () => {
      try {
        const response = await fetch(API + "/api/jobs", { cache: "no-store" });
        if (response.ok) {
          const data: { jobs: JobSummary[] } = await response.json();
          if (mounted) {
            setJobs(data.jobs);
            if (!initialized && data.jobs.some((job) => job.state === "queued" || job.state === "running" || job.message.includes("Backend dimulai ulang"))) setOpen(true);
            initialized = true;
          }
        }
      } catch { }
      if (mounted) timer = window.setTimeout(refresh, 1500);
    };
    refresh();
    return () => { mounted = false; window.clearTimeout(timer); };
  }, []);

  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs]);

  async function cancel(jobId: string) {
    await fetch(API + "/api/jobs/" + jobId + "/cancel", { method: "POST" }).catch(() => {});
  }

  async function remove(jobId: string) {
    const response = await fetch(API + "/api/jobs/" + jobId, { method: "DELETE" }).catch(() => null);
    if (response?.ok) setJobs((current) => current.filter((job) => job.id !== jobId));
  }

  if (!jobs.length) return null;
  const activeJobs = jobs.filter((job) => job.state === "queued" || job.state === "running");
  const title = activeJobs.length ? `${activeJobs.length} pekerjaan berjalan/antre` : "Pekerjaan terbaru";

  return (
    <aside className="job-center" aria-label="Pekerjaan MyTools">
      <button className="job-center-toggle" type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        {activeJobs.length ? <LoaderCircle size={16} className="spin" /> : <CheckCircle2 size={16} />}
        <span>{title}</span><ChevronDown size={15} className={open ? "is-open" : ""} />
      </button>
      {open && <section className="job-center-panel">
        <header><b>{title}</b><span>{activeJobs.length ? "Status tetap tersedia saat berpindah alat atau me-refresh halaman." : "Klik pekerjaan selesai untuk membuka hasilnya."} Riwayat dan hasil lokal dibersihkan otomatis setelah 7 hari.</span></header>
        <div className="job-center-list">
          {jobs.map((job) => {
            const active = job.state === "queued" || job.state === "running";
            const start = job.started_at || job.created_at;
            const end = job.finished_at || now / 1000;
            const seconds = Math.max(0, Math.floor(end - start));
            const href = job.kind === "scraping" ? `/scraping?job=${job.id}` : `/?tool=${job.kind}&job=${job.id}`;
            const stateLabel = job.state === "queued" ? "Menunggu proses lain" : job.state === "running" ? "Sedang berjalan" : job.state === "completed" ? "Selesai" : job.state === "failed" ? "Gagal" : "Dibatalkan";
            return <article className="job-center-item" key={job.id}>
              <a href={href} className="job-center-link">
                <span className={`job-center-dot ${job.state}`} />
                <span className="job-center-copy"><b>{LABELS[job.kind] || "Pekerjaan MyTools"}</b><small>{stateLabel} · {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}</small><small className="job-center-message">{job.message}</small></span>
              </a>
              {active && <button type="button" className="job-center-cancel" onClick={() => cancel(job.id)} aria-label={`Batalkan ${LABELS[job.kind] || "pekerjaan"}`}><X size={14} /></button>}
              {!active && <button type="button" className="job-center-cancel job-center-delete" onClick={() => remove(job.id)} aria-label={`Hapus riwayat ${LABELS[job.kind] || "pekerjaan"}`} title="Hapus riwayat dan file hasil"><Trash2 size={14} /></button>}
            </article>;
          })}
        </div>
      </section>}
    </aside>
  );
}
