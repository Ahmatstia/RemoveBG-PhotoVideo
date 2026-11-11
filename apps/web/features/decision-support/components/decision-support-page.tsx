"use client";

import { ArrowLeft, BarChart3, Check, ChevronDown, Database, FileUp, LoaderCircle, Sparkles } from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { analyzeReviews as requestReviewAnalysis, commitImport, getModelStatus, getProduct, listCategories, listProducts, previewImport } from "../api/client";
import type { Category, ImportPreview, Product, ProductDetail } from "../types";
import { ToolNavigation } from "@/components/tool-navigation";
import "./decision-support.css";

const ASPECTS = [
  ["sound_quality", "Kualitas suara"], ["battery", "Baterai"], ["comfort", "Kenyamanan"],
  ["connectivity", "Konektivitas"], ["microphone", "Mikrofon"], ["anc_transparency", "ANC / transparansi"],
  ["build_quality", "Kualitas material"], ["controls_app", "Kontrol / aplikasi"],
  ["price_value", "Harga / value"], ["warranty_support", "Garansi / dukungan"],
] as const;
const money = (value: number | null, currency = "IDR") => {
  if (value == null) return "Belum ada data harga";
  try { return new Intl.NumberFormat("id-ID", { style: "currency", currency, maximumFractionDigits: 0 }).format(value); }
  catch { return `${currency} ${Math.round(value).toLocaleString("id-ID")}`; }
};
const date = (value: string | null) => value ? new Date(value).toLocaleDateString("id-ID") : "—";

export default function DecisionSupportPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState("");
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

  const loadCategories = useCallback(async () => {
    const result = await listCategories();
    setCategories(result.categories);
    setCategory((current) => current || result.categories.find((item) => item.product_count > 0)?.key || "");
    return result.categories;
  }, []);

  const loadProducts = useCallback(async () => {
    if (!category) { setProducts([]); return; }
    const result = await listProducts(category, search);
    setProducts(result.products);
  }, [category, search]);

  useEffect(() => {
    loadCategories().catch((reason) => setError(reason instanceof Error ? reason.message : "Gagal memuat kategori."));
    loadProducts().catch((reason) => setError(reason instanceof Error ? reason.message : "Gagal memuat data."));
    getModelStatus().then((result) => {
      setModelReady(result.ready);
      setModelMacroF1(result.evaluation?.macro_f1 ?? null);
    }).catch(() => {});
  }, [loadCategories, loadProducts]);

  async function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0] || null;
    event.target.value = "";
    setFile(picked); setPreview(null); setError(""); setMessage("");
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
      await loadCategories();
      await loadProducts();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Import gagal."); }
    finally { setBusy(false); }
  }

  async function openDetail(id: number) {
    setError("");
    try { setDetail(await getProduct(id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Gagal membuka detail produk."); }
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
    const csv = "category,brand,model,variant,price,currency,source_name,source_url,observed_at,rating,review_date,review_text,spec_example\n";
    const href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = href; anchor.download = "template-data-produk.csv"; anchor.click(); URL.revokeObjectURL(href);
  }

  const compared = products.filter((product) => selected.includes(product.id));
  const activeCategory = categories.find((item) => item.key === category);
  const detailRecord = detail;

  return <div className="pd-workspace">
    <aside className="sidebar pd-sidebar"><ToolNavigation activeTool="decision-support" /><div className="sidebar-tip"><strong><Database size={13} style={{ verticalAlign: "-2px", marginRight: 5 }} />Riset &amp; Data</strong>Impor data yang boleh kamu gunakan, lalu bandingkan hasilnya.</div></aside>
    <div className="pd-mobile-nav"><ToolNavigation activeTool="decision-support" /></div>
    <main className="pd-page">
    <header className="pd-topbar"><a href="/" className="pd-back"><ArrowLeft size={16} /> Kembali ke MyTools</a><span className="pd-local"><i /> Data tersimpan di komputer ini</span></header>
    <section className="pd-hero">
      <div><div className="pd-kicker"><Sparkles size={15} /> ANALISIS DATA</div><h1>Bandingkan pilihan berdasarkan data.</h1><p>Impor data dari berbagai kategori, lihat harga, rating, spesifikasi, dan ulasan, lalu bandingkan beberapa pilihan.</p></div>
      <div className="pd-hero-mark"><BarChart3 size={28} /><span>Kategori aktif<br /><b>{activeCategory?.name || "Pilih kategori"}</b></span></div>
    </section>

    <div className="pd-grid">
      <section className="pd-panel pd-import">
        <div className="pd-section-title"><div><span className="pd-step">01</span><h2>Masukkan data produk</h2></div><button className="pd-text-button" type="button" onClick={downloadTemplate}>Unduh template CSV</button></div>
        <p className="pd-muted">Tambahkan data dari kategori apa pun. Satu baris berisi satu produk dan observasi harga, spesifikasi, atau ulasan; data tersimpan lokal.</p>
        <label className="pd-upload"><FileUp size={19} /><span>{file ? file.name : "Pilih CSV dari komputer"}</span><input type="file" accept=".csv,text/csv" onChange={selectFile} /></label>
        {preview && <div className="pd-import-report"><b>Pratinjau · {preview.source_name}</b><div className="pd-stats"><span>{preview.rows_seen}<small>baris</small></span><span>{preview.distinct_products}<small>produk</small></span><span>{preview.accepted}<small>bisa diimpor</small></span><span>{preview.duplicates + preview.rejected}<small>duplikat / ditolak</small></span></div>
          {preview.rows.some((row) => row.reason) && <details><summary>Lihat baris bermasalah</summary><ul>{preview.rows.filter((row) => row.reason).slice(0, 12).map((row) => <li key={row.line}>Baris {row.line}: {row.reason}</li>)}</ul></details>}
          <button className="pd-primary" type="button" onClick={importFile} disabled={busy || preview.accepted === 0}>{busy ? "Memproses…" : "Simpan data valid"}</button></div>}
        <div className="pd-csv-hint"><b>Kolom wajib:</b> <code>category, brand, model</code>. Kolom data lain opsional: <code>variant, price, currency, rating, review_text, review_date, source_name, source_url, observed_at</code>. Untuk spesifikasi, tambahkan kolom dengan nama <code>spec_[nama]</code>, misalnya <code>spec_memory_gb</code> atau <code>spec_sensor</code>. Hanya impor data yang memang boleh kamu gunakan.</div>
      </section>

      <section className="pd-panel pd-category-panel">
        <div className="pd-section-title"><div><span className="pd-step">02</span><h2>Pilih kategori data</h2></div></div>
        <label className="pd-field">Kategori<select value={category} onChange={(event) => { setCategory(event.target.value); setSelected([]); setDetail(null); }}>
          {!category && <option value="">Pilih kategori data</option>}
          {categories.map((item) => <option key={item.key} value={item.key}>{item.name} · {item.product_count} data</option>)}
        </select></label>
        <p className="pd-muted">Kategori dibuat dari nilai kolom <code>category</code> pada CSV (huruf kecil, angka, _ atau -). Data laptop, kamera, audio, dan kategori lain tersimpan dan ditampilkan terpisah.</p>
        {category === "tws" ? (
          <div className="pd-model-status">
            <span className={modelReady ? "pd-model-dot ready" : "pd-model-dot"} />
            <div><b>{modelReady ? "Model ulasan TWS siap" : "Model ulasan TWS belum dilatih"}</b><p>{modelReady ? `Macro-F1 evaluasi ${modelMacroF1 == null ? "tidak tersedia" : (modelMacroF1 * 100).toFixed(1) + "%"}. Model ini hanya digunakan untuk ulasan TWS.` : "Analisis aspek AI TWS tersedia setelah ada dataset berlabel dan model terlatih."}</p></div>
            {modelReady && <button type="button" className="pd-text-button" disabled={busy} onClick={analyzeReviews}>Analisis ulasan</button>}
          </div>
        ) : category ? (
          <div className="pd-model-status"><span className="pd-model-dot" /><div><b>Analisis AI belum tersedia untuk kategori ini</b><p>Perlu data berlabel dan model yang sesuai dengan kategori sebelum analisis aspek diaktifkan.</p></div></div>
        ) : (
          <div className="pd-model-status"><span className="pd-model-dot" /><div><b>Belum ada kategori berisi data</b><p>Impor CSV untuk menambahkan kategori dan mulai melihat katalog.</p></div></div>
        )}
      </section>
    </div>

    {message && <div className="pd-notice"><Check size={16} />{message}</div>}{error && <div className="pd-error" role="alert">{error}</div>}

    <section className="pd-panel pd-catalog">
      <div className="pd-section-title"><div><span className="pd-step">03</span><h2>{activeCategory?.name || "Katalog data"}</h2></div><span className="pd-product-count">{products.length} produk</span></div>
      <div className="pd-catalog-tools"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari brand atau model…" /><span>Pilih hingga 3 produk untuk dibandingkan</span></div>
      {products.length ? <div className="pd-product-list">{products.map((product) => <article className="pd-product" key={product.id}>
        <label className="pd-compare-check" title="Pilih untuk perbandingan"><input type="checkbox" checked={selected.includes(product.id)} onChange={() => toggleCompare(product.id)} disabled={!selected.includes(product.id) && selected.length >= 3} /><span /></label>
        <div className="pd-product-name"><b>{product.brand} {product.model}</b><small>{product.variant || "Model standar"}</small></div>
        <div className="pd-product-price">{money(product.latest_price, product.currency || "IDR")}<small>{product.review_count} ulasan · rating {product.average_rating ?? "—"}</small></div>
        <button className="pd-icon-button" onClick={() => openDetail(product.id)} aria-label={`Detail ${product.brand} ${product.model}`}><ChevronDown size={17} /></button>
      </article>)}</div> : <div className="pd-empty"><Database size={22} /><b>Belum ada data di kategori ini</b><span>Impor CSV dengan kolom kategori, brand, dan model untuk mulai membandingkan.</span></div>}
    </section>

    {compared.length > 1 && <section className="pd-panel pd-compare"><div className="pd-section-title"><div><span className="pd-step">04</span><h2>Perbandingan</h2></div><button className="pd-text-button" onClick={() => setSelected([])}>Hapus pilihan</button></div><div className="pd-compare-grid">{compared.map((product) => <article key={product.id}><b>{product.brand} {product.model}</b><span>Harga: {money(product.latest_price, product.currency || "IDR")}</span><span>Rating: {product.average_rating ?? "Data belum tersedia"}</span><span>Jumlah ulasan: {product.review_count}</span><span>Waktu harga: {date(product.price_observed_at)}</span>{Object.entries(product.specs).map(([key, value]) => <span key={key}>{key}: {value}</span>)}</article>)}</div></section>}

    {detailRecord && <div className="pd-modal-backdrop" onClick={() => setDetail(null)}><section className="pd-modal" onClick={(event) => event.stopPropagation()}><button className="pd-modal-close" onClick={() => setDetail(null)}>Tutup</button><h2>{detailRecord.brand} {detailRecord.model}</h2><p className="pd-muted">{detailRecord.variant || "Model standar"}</p><h3>Spesifikasi</h3>{Object.keys(detailRecord.specs || {}).length ? <ul>{Object.entries(detailRecord.specs || {}).map(([key, value]) => { const source = detailRecord.specification_sources?.find((item) => item.attribute_key === key); return <li key={key}>{key}: {value}{source ? ` · ${source.source_name} · ${date(source.observed_at)}` : ""}</li>; })}</ul> : <p>Belum ada spesifikasi yang diimpor.</p>}<h3>Harga yang tercatat</h3>{detailRecord.prices?.length ? detailRecord.prices.map((item, index) => <p key={index}>{money(item.price, item.currency)} · {item.source_name} · {date(item.observed_at)}</p>) : <p>Belum ada observasi harga.</p>}{detailRecord.category_key === "tws" && <><h3>Insight aspek TWS</h3>{detailRecord.aspect_insights?.length ? detailRecord.aspect_insights.map((item, index) => <p key={index}>{ASPECTS.find(([key]) => key === item.aspect_key)?.[1] || item.aspect_key}: {item.sentiment} ({item.evidence_count} ulasan; confidence {Math.round(item.confidence * 100)}%)</p>) : <p>Belum ada hasil model ABSA.</p>}</>}<h3>Bukti ulasan</h3>{detailRecord.reviews?.length ? detailRecord.reviews.map((review, index) => <blockquote key={index}>“{review.text}”<small>{review.source_name} · rating {review.rating ?? "—"} · {date(review.review_date)}</small></blockquote>) : <p>Belum ada ulasan.</p>}</section></div>}

    <footer className="pd-footer">Perbandingan merangkum data yang tersedia; kategori berbeda dapat memakai spesifikasi yang berbeda. Data impor, sumber, dan tanggalnya menjadi dasar analisis.</footer>
    </main>
  </div>;
}
