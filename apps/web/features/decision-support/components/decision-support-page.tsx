"use client";

import { ArrowLeft, BarChart3, Check, ChevronDown, Database, FileUp, LoaderCircle, Sparkles } from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { analyzeReviews as requestReviewAnalysis, commitImport, createRecommendations, getModelStatus, getProduct, listProducts, previewImport } from "../api/client";
import type { ImportPreview, Product, ProductDetail, RankingItem } from "../types";
import { ToolNavigation } from "@/components/tool-navigation";
import "./decision-support.css";

const ASPECTS = [
  ["sound_quality", "Kualitas suara"], ["battery", "Baterai"], ["comfort", "Kenyamanan"],
  ["connectivity", "Konektivitas"], ["microphone", "Mikrofon"], ["anc_transparency", "ANC / transparansi"],
  ["build_quality", "Kualitas material"], ["controls_app", "Kontrol / aplikasi"],
  ["price_value", "Harga / value"], ["warranty_support", "Garansi / dukungan"],
] as const;
const PREFERENCE_CRITERIA = [
  ["price", "Harga"], ["rating", "Rating pengguna"],
  ...ASPECTS.map(([key, label]) => [`aspect:${key}`, `${label} · AI`] as const),
];
const money = (value: number | null, currency = "IDR") => {
  if (value == null) return "Belum ada data harga";
  try { return new Intl.NumberFormat("id-ID", { style: "currency", currency, maximumFractionDigits: 0 }).format(value); }
  catch { return `${currency} ${Math.round(value).toLocaleString("id-ID")}`; }
};
const date = (value: string | null) => value ? new Date(value).toLocaleDateString("id-ID") : "—";

export default function DecisionSupportPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [modelReady, setModelReady] = useState(false);
  const [modelMacroF1, setModelMacroF1] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [budget, setBudget] = useState("");
  const [weights, setWeights] = useState<Record<string, number>>({ price: 35, rating: 35, "aspect:sound_quality": 15, "aspect:battery": 15 });
  const [ranking, setRanking] = useState<RankingItem[]>([]);
  const [rankingNote, setRankingNote] = useState("");

  const loadProducts = useCallback(async () => {
    const result = await listProducts(search);
    setProducts(result.products);
  }, [search]);

  useEffect(() => {
    loadProducts().catch((reason) => setError(reason instanceof Error ? reason.message : "Gagal memuat data."));
    getModelStatus().then((result) => {
      setModelReady(result.ready);
      setModelMacroF1(result.evaluation?.macro_f1 ?? null);
    }).catch(() => {});
  }, [loadProducts]);

  async function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0] || null;
    event.target.value = "";
    setFile(picked); setPreview(null); setError(""); setMessage(""); setRanking([]);
    if (!picked) return;
    setBusy(true);
    try { setPreview(await previewImport(picked)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Tidak bisa membaca CSV."); }
    finally { setBusy(false); }
  }

  async function importFile() {
    if (!file) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await commitImport(file);
      setMessage(`Import selesai: ${result.products_added} produk, ${result.reviews_added} ulasan, ${result.prices_added} observasi harga.`);
      setFile(null); setPreview(null);
      await loadProducts();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Import gagal."); }
    finally { setBusy(false); }
  }

  async function openDetail(id: number) {
    setError("");
    try { setDetail(await getProduct(id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Gagal membuka detail produk."); }
  }

  async function getRecommendations() {
    setBusy(true); setError(""); setRanking([]); setRankingNote("");
    try {
      const activeWeights = Object.fromEntries(Object.entries(weights).map(([key, value]) => [key, value / 100]).filter(([, value]) => Number(value) > 0));
      const result = await createRecommendations(budget ? Number(budget) : null, activeWeights);
      setRanking(result.items); setRankingNote(result.policy || result.message || "");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Gagal menghitung ranking."); }
    finally { setBusy(false); }
  }

  async function analyzeReviews() {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await requestReviewAnalysis();
      setMessage(`Analisis selesai: ${result.reviews_analyzed} ulasan, ${result.aspect_predictions} prediksi aspek.`);
      await loadProducts();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Analisis belum tersedia."); }
    finally { setBusy(false); }
  }

  function toggleCompare(id: number) {
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length < 3 ? [...current, id] : current);
  }

  function downloadTemplate() {
    const csv = "category,brand,model,variant,price,currency,source_name,source_url,observed_at,rating,review_date,review_text,spec_battery_hours,spec_weight_g\n";
    const href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = href; anchor.download = "template-produk-tws.csv"; anchor.click(); URL.revokeObjectURL(href);
  }

  const compared = products.filter((product) => selected.includes(product.id));
  const availableSpecKeys = [...new Set(products.flatMap((product) => Object.keys(product.specs)))].filter(
    (key) => ["battery_hours", "warranty_months", "weight_g"].includes(key),
  );
  const preferenceCriteria = [...PREFERENCE_CRITERIA, ...availableSpecKeys.map((key) => [
    `spec:${key}`, ({ battery_hours: "Daya tahan baterai (jam)", warranty_months: "Garansi (bulan)", weight_g: "Berat (gram)" } as Record<string, string>)[key],
  ] as const)];
  const detailRecord = detail;

  return <div className="pd-workspace">
    <aside className="sidebar pd-sidebar"><ToolNavigation activeTool="decision-support" /><div className="sidebar-tip"><strong><Database size={13} style={{ verticalAlign: "-2px", marginRight: 5 }} />Riset &amp; Data</strong>Impor data yang boleh kamu gunakan, lalu bandingkan hasilnya.</div></aside>
    <div className="pd-mobile-nav"><ToolNavigation activeTool="decision-support" /></div>
    <main className="pd-page">
    <header className="pd-topbar"><a href="/" className="pd-back"><ArrowLeft size={16} /> Kembali ke MyTools</a><span className="pd-local"><i /> Data tersimpan di komputer ini</span></header>
    <section className="pd-hero">
      <div><div className="pd-kicker"><Sparkles size={15} /> DECISION SUPPORT</div><h1>Pilih dengan lebih yakin.</h1><p>Bandingkan bukti harga, spesifikasi, dan ulasan. Ranking menyesuaikan budget serta prioritasmu.</p></div>
      <div className="pd-hero-mark"><BarChart3 size={28} /><span>Pilot kategori<br /><b>TWS</b></span></div>
    </section>

    <div className="pd-grid">
      <section className="pd-panel pd-import">
        <div className="pd-section-title"><div><span className="pd-step">01</span><h2>Masukkan data produk</h2></div><button className="pd-text-button" type="button" onClick={downloadTemplate}>Unduh template CSV</button></div>
        <p className="pd-muted">Satu baris untuk satu observasi produk/ulasan. Import tersimpan lokal; data contoh pada template hanya penunjuk format, bukan data produk.</p>
        <label className="pd-upload"><FileUp size={19} /><span>{file ? file.name : "Pilih CSV dari komputer"}</span><input type="file" accept=".csv,text/csv" onChange={selectFile} /></label>
        {preview && <div className="pd-import-report"><b>Pratinjau · {preview.source_name}</b><div className="pd-stats"><span>{preview.rows_seen}<small>baris</small></span><span>{preview.distinct_products}<small>produk</small></span><span>{preview.accepted}<small>bisa diimpor</small></span><span>{preview.duplicates + preview.rejected}<small>duplikat / ditolak</small></span></div>
          {preview.rows.some((row) => row.reason) && <details><summary>Lihat baris bermasalah</summary><ul>{preview.rows.filter((row) => row.reason).slice(0, 12).map((row) => <li key={row.line}>Baris {row.line}: {row.reason}</li>)}</ul></details>}
          <button className="pd-primary" type="button" onClick={importFile} disabled={busy || preview.accepted === 0}>{busy ? "Memproses…" : "Simpan data valid"}</button></div>}
        <div className="pd-csv-hint"><b>Kolom wajib:</b> <code>brand, model</code>. Opsional: <code>category, variant, price, currency, rating, review_text, review_date, source_name, source_url, observed_at</code>. Kolom <code>spec_*</code> disimpan sebagai spesifikasi. Hanya impor data yang memang boleh kamu gunakan.</div>
      </section>

      <section className="pd-panel pd-recommend">
        <div className="pd-section-title"><div><span className="pd-step">02</span><h2>Preferensi rekomendasi</h2></div></div>
        <label className="pd-field">Batas budget (IDR)<input inputMode="numeric" type="number" min="1" value={budget} onChange={(event) => setBudget(event.target.value)} placeholder="Contoh: 750000" /></label>
        <p className="pd-muted">Atur tingkat kepentingan. Bobot aktif dinormalisasi otomatis saat ranking dihitung.</p>
        {preferenceCriteria.map(([key, label]) => <label className="pd-weight" key={key}><span>{label}</span><input type="range" min="0" max="100" value={weights[key] || 0} onChange={(event) => setWeights((current) => ({ ...current, [key]: Number(event.target.value) }))} /><b>{weights[key] || 0}%</b></label>)}
        <button className="pd-primary" type="button" disabled={busy || !products.length} onClick={getRecommendations}>{busy ? "Menghitung…" : "Lihat rekomendasi"}</button>
        <div className="pd-model-status"><span className={modelReady ? "pd-model-dot ready" : "pd-model-dot"} /><div><b>{modelReady ? "Model ABSA lokal siap" : "Model ABSA TWS belum dilatih"}</b><p>{modelReady ? `Evaluasi Macro-F1 ${modelMacroF1 == null ? "tidak tersedia" : (modelMacroF1 * 100).toFixed(1) + "%"}. Tinjau metrik per kelas di evaluation.json.` : "Skor aspek AI aktif setelah model dilatih dengan ulasan TWS berlabel."}</p></div>{modelReady && <button type="button" className="pd-text-button" disabled={busy} onClick={analyzeReviews}>Analisis ulasan</button>}</div>
      </section>
    </div>

    {message && <div className="pd-notice"><Check size={16} />{message}</div>}{error && <div className="pd-error" role="alert">{error}</div>}

    {(ranking.length > 0 || rankingNote) && <section className="pd-panel pd-results"><div className="pd-section-title"><div><span className="pd-step">03</span><h2>Hasil ranking</h2></div><span className="pd-algorithm">SAW-1 · transparan</span></div><p className="pd-muted">Skor menunjukkan kesesuaian dengan bobotmu, bukan kualitas universal.</p><div className="pd-rankings">{ranking.map((item) => <article className="pd-rank-card" key={item.id}><div className="pd-rank-number">#{item.rank}</div><div className="pd-rank-main"><b>{item.brand} {item.model}</b><span>{money(item.price, item.currency || "IDR")} · {item.review_count} ulasan · coverage {item.coverage}%</span><small>Harga diamati {date(item.price_observed_at)}{item.missing_criteria.length ? ` · Data kosong: ${item.missing_criteria.join(", ")}` : ""}</small></div><div className="pd-score">{item.score}<small>/ 100</small></div><details><summary>Kontribusi kriteria</summary><div>{Object.entries(item.contributions).map(([key, value]) => <span key={key}>{key}: {value}</span>)}</div></details></article>)}</div>{!ranking.length && <p className="pd-footnote">Belum ada produk dengan coverage kriteria yang cukup atau harga yang memenuhi budget.</p>}<p className="pd-footnote">{rankingNote}</p></section>}

    <section className="pd-panel pd-catalog">
      <div className="pd-section-title"><div><span className="pd-step">04</span><h2>Katalog TWS</h2></div><span className="pd-product-count">{products.length} produk</span></div>
      <div className="pd-catalog-tools"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari brand atau model…" /><span>Pilih hingga 3 produk untuk dibandingkan</span></div>
      {products.length ? <div className="pd-product-list">{products.map((product) => <article className="pd-product" key={product.id}>
        <label className="pd-compare-check" title="Pilih untuk perbandingan"><input type="checkbox" checked={selected.includes(product.id)} onChange={() => toggleCompare(product.id)} disabled={!selected.includes(product.id) && selected.length >= 3} /><span /></label>
        <div className="pd-product-name"><b>{product.brand} {product.model}</b><small>{product.variant || "Model standar"}</small></div>
        <div className="pd-product-price">{money(product.latest_price, product.currency || "IDR")}<small>{product.review_count} ulasan · rating {product.average_rating ?? "—"}</small></div>
        <button className="pd-icon-button" onClick={() => openDetail(product.id)} aria-label={`Detail ${product.brand} ${product.model}`}><ChevronDown size={17} /></button>
      </article>)}</div> : <div className="pd-empty"><Database size={22} /><b>Belum ada produk TWS</b><span>Impor CSV berisi data produk yang sah untuk memulai. Fitur tidak memakai data simulasi.</span></div>}
    </section>

    {compared.length > 1 && <section className="pd-panel pd-compare"><div className="pd-section-title"><div><span className="pd-step">05</span><h2>Perbandingan</h2></div><button className="pd-text-button" onClick={() => setSelected([])}>Hapus pilihan</button></div><div className="pd-compare-grid">{compared.map((product) => <article key={product.id}><b>{product.brand} {product.model}</b><span>Harga: {money(product.latest_price, product.currency || "IDR")}</span><span>Rating: {product.average_rating ?? "Data belum tersedia"}</span><span>Jumlah ulasan: {product.review_count}</span><span>Waktu harga: {date(product.price_observed_at)}</span>{Object.entries(product.specs).map(([key, value]) => <span key={key}>{key}: {value}</span>)}</article>)}</div></section>}

    {detailRecord && <div className="pd-modal-backdrop" onClick={() => setDetail(null)}><section className="pd-modal" onClick={(event) => event.stopPropagation()}><button className="pd-modal-close" onClick={() => setDetail(null)}>Tutup</button><h2>{detailRecord.brand} {detailRecord.model}</h2><p className="pd-muted">{detailRecord.variant || "Model standar"}</p><h3>Spesifikasi</h3>{Object.keys(detailRecord.specs || {}).length ? <ul>{Object.entries(detailRecord.specs || {}).map(([key, value]) => { const source = detailRecord.specification_sources?.find((item) => item.attribute_key === key); return <li key={key}>{key}: {value}{source ? ` · ${source.source_name} · ${date(source.observed_at)}` : ""}</li>; })}</ul> : <p>Belum ada spesifikasi yang diimpor.</p>}<h3>Harga yang tercatat</h3>{detailRecord.prices?.length ? detailRecord.prices.map((item, index) => <p key={index}>{money(item.price, item.currency)} · {item.source_name} · {date(item.observed_at)}</p>) : <p>Belum ada observasi harga.</p>}<h3>Insight aspek</h3>{detailRecord.aspect_insights?.length ? detailRecord.aspect_insights.map((item, index) => <p key={index}>{ASPECTS.find(([key]) => key === item.aspect_key)?.[1] || item.aspect_key}: {item.sentiment} ({item.evidence_count} ulasan; confidence {Math.round(item.confidence * 100)}%)</p>) : <p>Belum ada hasil model ABSA.</p>}<h3>Bukti ulasan</h3>{detailRecord.reviews?.length ? detailRecord.reviews.map((review, index) => <blockquote key={index}>“{review.text}”<small>{review.source_name} · rating {review.rating ?? "—"} · {date(review.review_date)}</small></blockquote>) : <p>Belum ada ulasan.</p>}</section></div>}

    <footer className="pd-footer">Insight AI hanya muncul setelah model TWS tervalidasi. Data impor, sumber, dan tanggalnya menjadi dasar setiap perbandingan.</footer>
    </main>
  </div>;
}

