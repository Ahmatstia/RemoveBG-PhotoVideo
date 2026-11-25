"use client";

import { CheckCircle2, ChevronRight, Eye, LoaderCircle, Terminal, X } from "lucide-react";
import { useEffect, useState } from "react";

type ProcessingJob = {
  kind: string;
  state: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string;
  error?: string | null;
  logs?: { time: string; progress: number; message: string }[];
  created_at?: number;
  started_at?: number | null;
  finished_at?: number | null;
  progress_updated_at?: number;
};

type Props = {
  job: ProcessingJob | null;
  busy: boolean;
  featureTitle: string;
  hasPartialResult?: boolean;
  onViewResult?: () => void;
  onCancel?: () => void;
};

const SLUGS: Record<string, string> = {
  transcription: "transkripsi", video: "hapus-latar-video", photo: "hapus-latar-foto",
  download: "unduh-media", scraping: "scraping-ulasan",
};

function elapsedSeconds(job: ProcessingJob | null, now: number) {
  const start = job?.started_at || job?.created_at;
  const end = job?.finished_at || now / 1000;
  return start ? Math.max(0, Math.floor(end - start)) : 0;
}

export function TerminalProcessingView({ job, busy, featureTitle, hasPartialResult = false, onViewResult, onCancel }: Props) {
  const [now, setNow] = useState(Date.now());
  const active = busy || job?.state === "queued" || job?.state === "running";
  const completed = job?.state === "completed";
  const failed = job?.state === "failed";
  const cancelled = job?.state === "cancelled";
  const queued = job?.state === "queued";
  const seconds = elapsedSeconds(job, now);
  const quietFor = job?.progress_updated_at ? now / 1000 - job.progress_updated_at : seconds;
  const indeterminate = active && (!job || queued || quietFor >= 5);
  const percent = Math.round(Math.max(0, Math.min(1, job?.progress || 0)) * 100);

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  const elapsed = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const stateLabel = failed ? "Gagal" : cancelled ? "Dibatalkan" : completed ? "Selesai" : job?.state === "queued" ? "Dalam antrean" : "Berjalan";

  return (
    <section className="processing-console" aria-label={`Proses ${featureTitle}`}>
      <header className="processing-console-head">
        <div className="processing-console-title"><Terminal size={15} /><span>mytools@{SLUGS[job?.kind || ""] || "worker"}:~$</span></div>
        <div className="processing-console-meta">
          <span>{elapsed}</span>
          <span className={`processing-state ${active ? "is-active" : failed ? "is-failed" : cancelled ? "is-cancelled" : "is-done"}`}>
            {active && <i />}{stateLabel}
          </span>
        </div>
      </header>

      <div className="processing-status">
        <div className="processing-status-top"><span>{job?.message || "Mengirim pekerjaan ke backend lokal…"}</span><b>{!job ? "Menghubungkan" : queued ? "Menunggu" : indeterminate ? "Berjalan" : `${percent}%`}</b></div>
        <div className={`processing-track ${indeterminate ? "is-indeterminate" : ""}`}>
          <span style={indeterminate ? undefined : { width: `${percent}%` }} />
        </div>
        {queued ? <small>Pekerjaan belum dimulai karena pekerjaan lain sedang memakai worker lokal.</small> : indeterminate && <small>Proses masih aktif; tahap ini belum mengirim angka progres baru.</small>}
      </div>

      <div className="processing-log" role="log" aria-live="polite" aria-relevant="additions text">
        {(job?.logs || []).length ? job!.logs!.map((entry, index) => (
          <div className="processing-log-line" key={`${entry.time}-${index}`}>
            <time>[{entry.time}]</time><span>{entry.message.startsWith("Gagal:") ? "ERR" : entry.progress === 100 ? "OK" : "INFO"}</span><p>{entry.message}</p>
          </div>
        )) : <p className="processing-log-empty">Menunggu pembaruan proses dari backend…</p>}
        {active && <div className="processing-live"><LoaderCircle size={13} className="spin" />Masih berjalan · {elapsed}</div>}
        {failed && <div className="processing-error"><X size={14} />{job?.error || "Proses gagal."}</div>}
        {cancelled && <div className="processing-error">Proses dibatalkan.</div>}
        {completed && <div className="processing-done"><CheckCircle2 size={14} />Selesai dalam {elapsed}</div>}
      </div>

      {(completed || (cancelled && hasPartialResult)) && onViewResult && (
        <footer className="processing-result-gate">
          <div><b>{completed ? "Hasil siap dilihat" : "Hasil sebagian tersedia"}</b><span>Pratinjau dan tombol simpan tersedia setelah dibuka.</span></div>
          <button type="button" onClick={onViewResult}><Eye size={16} />Lihat hasil<ChevronRight size={16} /></button>
        </footer>
      )}
      {active && onCancel && (
        <footer className="processing-console-foot"><span>{job?.state === "queued" ? "Pekerjaan akan dimulai setelah proses lain selesai." : "Log menampilkan pembaruan yang diterima dari backend."}</span><button type="button" onClick={onCancel}><X size={13} />Batalkan</button></footer>
      )}
    </section>
  );
}
