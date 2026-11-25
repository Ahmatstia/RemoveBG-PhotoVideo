"use client";

import Script from "next/script";
import { ChangeEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronLeft, ChevronRight, Download, ExternalLink, Pencil, RotateCcw, Upload } from "lucide-react";

type Word = { text: string; start: number; end: number; start_time?: string };
type Sentence = { start: number; end: number; start_time?: string; text: string; words: Word[] };
type Transcript = { url: string; sentences: Sentence[] };
type Player = { seekTo: (seconds: number, allowSeekAhead: boolean) => void; getCurrentTime: () => number; destroy: () => void };
type PlayerEvents = { onReady: () => void; onStateChange: (event: { data: number; target: Player }) => void; onError: () => void };

declare global {
  interface Window {
    YT?: { Player: new (element: HTMLElement, options: { videoId: string; playerVars: { playsinline: number; origin: string }; events: PlayerEvents }) => Player };
  }
}

const API = process.env.NODE_ENV === "development" ? "http://127.0.0.1:7860" : "";

function videoIdFromUrl(value: string) {
  try {
    const url = new URL(value);
    const host = url.hostname.replace(/^www\./, "").replace(/^m\./, "");
    let id = "";
    if (host === "youtu.be") id = url.pathname.split("/").filter(Boolean)[0] || "";
    else if (host === "youtube.com" || host === "youtube-nocookie.com") {
      id = url.searchParams.get("v") || url.pathname.match(/^\/(?:embed|shorts|live)\/([^/?]+)/)?.[1] || "";
    }
    return /^[\w-]{11}$/.test(id) ? id : "";
  } catch {
    return "";
  }
}

function youtubeTime(url: string, seconds: number) {
  try {
    const target = new URL(url);
    target.searchParams.set("t", `${Math.max(0, Math.floor(seconds))}s`);
    return target.toString();
  } catch {
    return url;
  }
}

function clock(seconds: number) {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  return minutes >= 60
    ? `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}

function subtitleTime(seconds: number, separator: "," | ".") {
  const total = Math.max(0, Math.round(seconds * 1000));
  const hours = Math.floor(total / 3_600_000);
  const minutes = Math.floor((total % 3_600_000) / 60_000);
  const wholeSeconds = Math.floor((total % 60_000) / 1000);
  const millis = total % 1000;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(wholeSeconds).padStart(2, "0")}${separator}${String(millis).padStart(3, "0")}`;
}

function highlighted(text: string, query: string) {
  if (!query.trim()) return text;
  const escaped = query.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "ig"));
  return parts.map((part, index) => part.toLocaleLowerCase() === query.trim().toLocaleLowerCase()
    ? <mark key={index}>{part}</mark>
    : part);
}

export function TranscriptWorkspace({ jobId, jsonUrl, initialText, filename, mediaUrl, mediaType, onLocalSourceDetected }: { jobId: string; jsonUrl?: string; initialText: string; filename?: string; mediaUrl?: string; mediaType?: "audio" | "video"; onLocalSourceDetected?: () => void }) {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [originalTranscript, setOriginalTranscript] = useState<Transcript | null>(null);
  const [textOnly, setTextOnly] = useState(initialText);
  const [correctionsLoaded, setCorrectionsLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "pending" | "saving" | "saved" | "error">("idle");
  const [saveRetry, setSaveRetry] = useState(0);
  const [query, setQuery] = useState("");
  const [matchIndex, setMatchIndex] = useState(0);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [loadError, setLoadError] = useState("");
  const [origin, setOrigin] = useState("");
  const [apiReady, setApiReady] = useState(false);
  const [playerReady, setPlayerReady] = useState(false);
  const [playerError, setPlayerError] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [attachedMedia, setAttachedMedia] = useState<{ url: string; type: "audio" | "video" } | null>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<Player | null>(null);
  const localMediaRef = useRef<HTMLMediaElement>(null);
  const segmentRefs = useRef(new Map<number, HTMLElement>());
  const editVersion = useRef(0);
  const saveQueue = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => setOrigin(window.location.origin), []);

  useEffect(() => {
    const url = attachedMedia?.url;
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [attachedMedia?.url]);

  useEffect(() => {
    if (!jsonUrl) return;
    let active = true;
    setTranscript(null);
    setOriginalTranscript(null);
    setCorrectionsLoaded(false);
    setDirty(false);
    setLoadError("");
    Promise.all([
      fetch(API + jsonUrl, { cache: "no-store" }),
      fetch(API + `/api/jobs/${jobId}/transcript-corrections`, { cache: "no-store" })
        .then(async (response) => response.ok ? response.json() as Promise<{ texts?: unknown }> : null)
        .catch(() => null),
    ])
      .then(async ([response, saved]) => {
        if (!response.ok) throw new Error("Data timestamp tidak dapat dimuat.");
        const data = await response.json() as Transcript;
        if (!data || typeof data.url !== "string" || !Array.isArray(data.sentences) || !data.sentences.every((sentence) =>
          typeof sentence.text === "string" && Number.isFinite(sentence.start) && Number.isFinite(sentence.end) && Array.isArray(sentence.words),
        )) throw new Error("Format data timestamp tidak valid.");
        const texts = Array.isArray(saved?.texts) && saved.texts.length === data.sentences.length && saved.texts.every((text) => typeof text === "string")
          ? saved.texts as string[]
          : null;
        const corrected = texts ? { ...data, sentences: data.sentences.map((sentence, index) => ({ ...sentence, text: texts[index] })) } : data;
        if (active) {
          if (!data.url.trim()) onLocalSourceDetected?.();
          setTranscript(corrected);
          setOriginalTranscript(data);
          setCorrectionsLoaded(true);
          setSaveStatus(texts ? "saved" : "idle");
        }
      })
      .catch((error: unknown) => { if (active) setLoadError(error instanceof Error ? error.message : "Gagal memuat timestamp."); });
    return () => { active = false; };
  }, [jobId, jsonUrl, onLocalSourceDetected]);

  useEffect(() => {
    if (!dirty || !correctionsLoaded || !transcript) return;
    const version = editVersion.current;
    const texts = transcript.sentences.map((sentence) => sentence.text);
    let active = true;
    const timer = window.setTimeout(async () => {
      setSaveStatus("saving");
      const save = saveQueue.current.catch(() => {}).then(async () => {
        const response = await fetch(API + `/api/jobs/${jobId}/transcript-corrections`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texts }),
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || "Koreksi belum berhasil disimpan.");
        }
      });
      saveQueue.current = save;
      try {
        await save;
        if (active && version === editVersion.current) { setDirty(false); setSaveStatus("saved"); }
      } catch {
        if (active && version === editVersion.current) setSaveStatus("error");
      }
    }, 650);
    return () => { active = false; window.clearTimeout(timer); };
  }, [correctionsLoaded, dirty, jobId, saveRetry, transcript]);

  const videoId = transcript ? videoIdFromUrl(transcript.url) : "";
  const localTranscript = Boolean(transcript && !transcript.url.trim());
  const activeMediaUrl = mediaUrl || attachedMedia?.url;
  const activeMediaType = mediaType || attachedMedia?.type;

  useEffect(() => {
    if (!apiReady || !videoId || !origin || !playerContainerRef.current || !window.YT?.Player) return;
    const player = new window.YT.Player(playerContainerRef.current, {
      videoId,
      playerVars: { playsinline: 1, origin },
      events: {
        onReady: () => { setPlayerReady(true); setPlayerError(false); },
        onStateChange: (event) => { setPlaying(event.data === 1); setCurrentTime(event.target.getCurrentTime()); },
        onError: () => { setPlayerReady(false); setPlayerError(true); },
      },
    });
    playerRef.current = player;
    return () => {
      playerRef.current = null;
      player.destroy();
    };
  }, [apiReady, videoId, origin]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      const time = playerRef.current?.getCurrentTime();
      if (typeof time === "number" && Number.isFinite(time)) setCurrentTime(time);
    }, 300);
    return () => window.clearInterval(timer);
  }, [playing]);

  const sentences = transcript?.sentences ?? [];
  const matches = useMemo(() => {
    if (!query.trim()) return [];
    const needle = query.trim().toLocaleLowerCase();
    return sentences.flatMap((sentence, index) => sentence.text.toLocaleLowerCase().includes(needle) ? [index] : []);
  }, [sentences, query]);
  const matchSet = useMemo(() => new Set(matches), [matches]);
  const activeMatchIndex = matches.length ? matchIndex % matches.length : 0;
  const visibleSentences = useMemo(() => sentences
    .map((sentence, index) => ({ ...sentence, index }))
    .filter((sentence) => !query.trim() || matchSet.has(sentence.index) || editingIndex === sentence.index),
  [sentences, query, matchSet, editingIndex]);

  useEffect(() => {
    if (editingIndex !== null) return;
    const selected = matches[activeMatchIndex];
    if (selected !== undefined) segmentRefs.current.get(selected)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [activeMatchIndex, editingIndex, matches]);

  function editSentence(index: number, event: ChangeEvent<HTMLTextAreaElement>) {
    const text = event.target.value;
    editVersion.current += 1;
    setDirty(true);
    setSaveStatus("pending");
    setTranscript((current) => current ? {
      ...current,
      sentences: current.sentences.map((sentence, sentenceIndex) => sentenceIndex === index ? { ...sentence, text } : sentence),
    } : current);
  }

  function seek(event: MouseEvent<HTMLAnchorElement>, seconds: number) {
    if (!playerReady || !playerRef.current) return;
    event.preventDefault();
    jumpTo(seconds);
  }

  function jumpTo(seconds: number) {
    const target = Math.max(0, seconds);
    if (playerReady && playerRef.current) playerRef.current.seekTo(target, true);
    else if (localMediaRef.current) localMediaRef.current.currentTime = target;
    setCurrentTime(seconds);
  }

  function navigateMatch(direction: -1 | 1) {
    if (!matches.length) return;
    const next = (activeMatchIndex + direction + matches.length) % matches.length;
    setMatchIndex(next);
    const sentence = transcript?.sentences[matches[next]];
    if (sentence && (playerReady || localMediaRef.current)) jumpTo(sentence.start);
  }

  function download(name: string, content: string, mime: string) {
    const url = URL.createObjectURL(new Blob([content], { type: `${mime};charset=utf-8` }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function attachLocalMedia(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setAttachedMedia({
      url: URL.createObjectURL(file),
      type: /\.(mp4|mov|mkv|avi|webm)$/i.test(file.name) ? "video" : "audio",
    });
    event.target.value = "";
  }

  function baseName(extension: string) {
    return (filename || "transkrip-koreksi.txt").replace(/-koreksi\.txt$/i, `-koreksi.${extension}`);
  }

  function downloadFormat(format: "txt" | "srt" | "vtt") {
    if (!transcript) {
      download(baseName("txt"), textOnly.trimEnd() + "\n", "text/plain");
      return;
    }
    const body = format === "txt"
      ? transcript.sentences.map((sentence) => sentence.text).join("\n") + "\n"
      : format === "srt"
        ? transcript.sentences.map((sentence, index) => `${index + 1}\n${subtitleTime(sentence.start, ",")} --> ${subtitleTime(sentence.end, ",")}\n${sentence.text}`).join("\n\n") + "\n"
        : "WEBVTT\n\n" + transcript.sentences.map((sentence) => `${subtitleTime(sentence.start, ".")} --> ${subtitleTime(sentence.end, ".")}\n${sentence.text}`).join("\n\n") + "\n";
    download(baseName(format), body, format === "txt" ? "text/plain" : format === "srt" ? "application/x-subrip" : "text/vtt");
  }

  function resetCorrections() {
    if (!originalTranscript) return;
    const changed = transcript?.sentences.some((sentence, index) => sentence.text !== originalTranscript.sentences[index]?.text);
    if (changed && !window.confirm("Pulihkan semua kalimat ke teks hasil model? Koreksi saat ini akan dibuang.")) return;
    editVersion.current += 1;
    setDirty(true);
    setSaveStatus("pending");
    setTranscript(originalTranscript);
    setEditingIndex(null);
    setQuery("");
    setMatchIndex(0);
  }

  if (!transcript) return <section className="transcript-workspace">
    <p className="field-hint" role="status">{loadError || (jsonUrl ? "Memuat kalimat dan timestamp per kata…" : "Data timestamp tidak tersedia; teks tetap bisa dikoreksi.")}</p>
    <textarea className="transcript-editor" dir="auto" aria-label="Transkrip" value={textOnly} onChange={(event) => setTextOnly(event.target.value)} />
    <div className="transcript-toolbar"><span>TXT yang diunduh mengikuti koreksi di atas.</span><button type="button" className="secondary-button" onClick={() => downloadFormat("txt")}><Download size={14} />TXT koreksi</button></div>
  </section>;

  return <section className="transcript-workspace">
    {localTranscript && !activeMediaUrl && <>
      <label className="secondary-button transcript-attach-button"><Upload size={14} />Pilih ulang file sumber untuk memutar<input className="transcript-attach-input" type="file" accept=".mp4,.mov,.mkv,.avi,.webm,.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus,.wma" onChange={attachLocalMedia} /></label>
      <p className="field-hint">File sumber tidak disimpan setelah halaman dimuat ulang. Pilih file yang sama untuk memutar dan mengecek timestamp; transkripsi tidak akan diulang.</p>
    </>}
    {activeMediaUrl && <>
      <div className="transcript-player-wrap">
        {activeMediaType === "video"
          ? <video ref={(node) => { localMediaRef.current = node; }} className="transcript-player" src={activeMediaUrl} controls playsInline preload="metadata" onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)} />
          : <audio ref={(node) => { localMediaRef.current = node; }} className="transcript-audio" src={activeMediaUrl} controls preload="metadata" onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)} />}
      </div>
      <p className="field-hint" role="status">Putar file di sini, lalu klik timestamp untuk lompat ke bagian transkrip.</p>
    </>}
    {videoId && origin && <>
      <div className="transcript-player-wrap">
        <div ref={playerContainerRef} className="transcript-player" aria-label="Pemutar video sumber YouTube" />
        <Script src="https://www.youtube.com/iframe_api" strategy="afterInteractive" onReady={() => setApiReady(true)} onError={() => setPlayerError(true)} />
      </div>
      <p className="field-hint" role="status">{playerError ? "Video tidak dapat diputar tertanam. Gunakan timestamp untuk membukanya langsung di YouTube." : playerReady ? "Pemutar siap · klik timestamp atau hasil pencarian untuk menggeser video." : "Menghubungkan ke pemutar YouTube…"}</p>
    </>}
    <div className="transcript-search-row">
      <label className="transcript-search"><span>Cari dalam transkrip</span><input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setMatchIndex(0); }} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); navigateMatch(event.shiftKey ? -1 : 1); } }} placeholder="Ketik kata atau frasa…" /></label>
      <div className="transcript-search-nav" aria-label="Navigasi hasil pencarian">
        <span aria-live="polite">{matches.length ? `${activeMatchIndex + 1} / ${matches.length}` : query.trim() ? "0 hasil" : `${sentences.length} kalimat`}</span>
        <button type="button" className="icon-button" disabled={!matches.length} onClick={() => navigateMatch(-1)} aria-label="Hasil sebelumnya"><ChevronLeft size={16} /></button>
        <button type="button" className="icon-button" disabled={!matches.length} onClick={() => navigateMatch(1)} aria-label="Hasil berikutnya"><ChevronRight size={16} /></button>
      </div>
    </div>
    <div className="transcript-segments">
      {visibleSentences.length ? visibleSentences.map((sentence) => {
        const active = currentTime >= sentence.start && currentTime <= sentence.end;
        const selected = matches[activeMatchIndex] === sentence.index;
        return <article
          className={`transcript-segment ${active ? "is-playing" : ""} ${selected ? "is-search-match" : ""}`}
          id={`transcript-segment-${sentence.index}`}
          key={sentence.index}
          ref={(node) => { if (node) segmentRefs.current.set(sentence.index, node); else segmentRefs.current.delete(sentence.index); }}
        >
          {videoId ? <a className="transcript-time" href={youtubeTime(transcript.url, sentence.start)} target="_blank" rel="noreferrer" onClick={(event) => seek(event, sentence.start)} title="Geser pemutar ke waktu ini">{sentence.start_time || clock(sentence.start)}</a> : mediaUrl ? <button type="button" className="transcript-time" onClick={() => jumpTo(sentence.start)} title="Geser pemutar ke waktu ini">{sentence.start_time || clock(sentence.start)}</button> : <span className="transcript-time">{sentence.start_time || clock(sentence.start)}</span>}
          {editingIndex === sentence.index
            ? <textarea dir="auto" aria-label={`Koreksi kalimat ${sentence.index + 1}`} value={sentence.text} onChange={(event) => editSentence(sentence.index, event)} rows={Math.max(2, Math.min(5, Math.ceil(sentence.text.length / 72)))} />
            : <p className="transcript-sentence-text" dir="auto">{highlighted(sentence.text, query)}</p>}
          <button type="button" className="transcript-edit-button" onClick={() => setEditingIndex(editingIndex === sentence.index ? null : sentence.index)} aria-label={editingIndex === sentence.index ? "Selesai mengoreksi kalimat" : "Koreksi kalimat"}>
            {editingIndex === sentence.index ? <><Check size={13} />Selesai</> : <><Pencil size={13} />Koreksi</>}
          </button>
          <details className="transcript-word-details">
            <summary>{sentence.words.length} kata · timestamp tiap kata</summary>
            <div className="transcript-words" dir="auto">{sentence.words.map((word, index) => {
              const wordActive = currentTime >= word.start && currentTime <= word.end;
              const label = <><small>{word.start_time || clock(word.start)}</small><span>{word.text}</span></>;
              return videoId
                ? <a className={wordActive ? "is-playing" : ""} key={`${sentence.index}-${index}`} href={youtubeTime(transcript.url, word.start)} target="_blank" rel="noreferrer" onClick={(event) => seek(event, word.start)} title={`Geser ke ${word.start.toFixed(2)} detik`}>{label}</a>
                : mediaUrl
                  ? <button type="button" className={wordActive ? "is-playing" : ""} key={`${sentence.index}-${index}`} onClick={() => jumpTo(word.start)} title={`Geser ke ${word.start.toFixed(2)} detik`}>{label}</button>
                  : <div className={`transcript-word-static ${wordActive ? "is-playing" : ""}`} key={`${sentence.index}-${index}`}>{label}</div>;
            })}</div>
          </details>
        </article>;
      }) : <p className="transcript-empty">Tidak ada kalimat yang cocok dengan pencarian.</p>}
    </div>
    <div className="transcript-correction-bar">
      <span>{sentences.length} kalimat · timestamp kata tetap mengikuti hasil model. {saveStatus === "saving" ? "Menyimpan koreksi…" : saveStatus === "pending" ? "Perubahan akan segera disimpan…" : saveStatus === "saved" ? "Koreksi tersimpan untuk pekerjaan ini." : saveStatus === "error" ? "Koreksi belum tersimpan." : "Koreksi disimpan otomatis saat diedit."}</span>
      {saveStatus === "error" && <button type="button" className="text-button" onClick={() => { setSaveStatus("pending"); setSaveRetry((attempt) => attempt + 1); }}>Coba simpan lagi</button>}
      <button type="button" className="text-button" onClick={resetCorrections}><RotateCcw size={13} />Pulihkan teks awal</button>
    </div>
    <div className="transcript-toolbar transcript-exports">
      <span>Unduh transkrip yang sudah dikoreksi</span>
      {(["txt", "srt", "vtt"] as const).map((format) => <button type="button" className="secondary-button" key={format} onClick={() => downloadFormat(format)}><Download size={14} />{format.toUpperCase()} koreksi</button>)}
    </div>
    {transcript.url && <a className="transcript-source-link" href={youtubeTime(transcript.url, currentTime)} target="_blank" rel="noreferrer"><ExternalLink size={13} />Buka sumber di YouTube</a>}
  </section>;
}
