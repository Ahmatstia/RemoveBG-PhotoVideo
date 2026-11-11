# MyTools — Product Decision Assistant

> **Dokumen spesifikasi fitur untuk AI coding agent**  
> Versi: 1.0-draft  
> Status: Ready for repository discovery; implementation details pending MyTools audit  
> Parent project: **MyTools**  
> Nama fitur sementara: **Product Decision Assistant** (nama tampilan dapat ditetapkan kemudian, misalnya “PilihCerdas”)  
> Kategori pilot: **TWS / True Wireless Stereo**  
> Target arsitektur: **Multi-category from the beginning**

---

## 0. Instruksi paling penting untuk AI agent

Dokumen ini menjelaskan **fitur baru di dalam aplikasi MyTools yang sudah ada**. Dokumen ini BUKAN instruksi untuk membuat aplikasi baru, repository baru, backend baru, frontend baru, autentikasi baru, atau infrastruktur terpisah.

### 0.1 Aturan wajib

1. **Audit repository MyTools terlebih dahulu sebelum mengubah kode.** Baca dokumentasi proyek, instruksi agent, manifest/package files, struktur folder, route/navigation, design system, database schema, ORM, service layer, API conventions, authentication/authorization, testing, serta deployment setup.
2. **Reuse, extend, do not rebuild.** Gunakan pola, komponen, service, database, autentikasi, layout, navigation, design tokens, logging, dan mekanisme deployment yang sudah tersedia.
3. Jangan mengasumsikan stack teknologi. Stack aktual harus ditemukan dari repository, bukan dipilih berdasarkan dokumen ini.
4. Jangan membuat service terpisah, microservice, database baru, queue baru, atau infrastruktur baru kecuali audit membuktikan hal tersebut benar-benar diperlukan dan keputusan itu disetujui pemilik proyek.
5. Jangan mengganti atau merombak modul existing yang tidak terkait fitur ini.
6. Jangan melakukan scraping pada platform tanpa memeriksa Terms of Service, izin, lisensi, robots policy yang relevan, dan batas penggunaan. Jangan melewati login, CAPTCHA, paywall, rate limit, atau mekanisme keamanan.
7. Jangan membuat data sintetis atau prediksi model seolah-olah merupakan data nyata. Data demo harus diberi label **simulasi**.
8. Jangan menganggap rating, jumlah ulasan, atau sentimen positif sebagai bukti objektif bahwa produk memiliki kualitas terbaik.
9. Setiap hasil rekomendasi harus dapat ditelusuri ke data, kriteria, bobot, versi algoritma, dan bukti ulasan yang digunakan.
10. Jika ada detail yang tidak diketahui, catat sebagai **Open Question / Pending Repository Audit**. Jangan mengarang keputusan teknis.
11. Implementasikan secara bertahap dengan perubahan kecil, migration yang aman, tests, dan dokumentasi sesuai konvensi repository.
12. Jangan menampilkan credential, token, informasi pribadi reviewer, atau rahasia konfigurasi ke log, UI, repository, maupun output agent.

### 0.2 Perintah awal agent

Tugas pertama agent setelah menerima dokumen ini adalah:

- Memeriksa seluruh repository MyTools dan dokumentasi yang relevan.
- Menemukan instruksi khusus agent seperti `AGENTS.md`, `CLAUDE.md`, `README.md`, atau aturan sejenis.
- Menyusun `PRODUCT_DECISION_ASSISTANT_REPOSITORY_AUDIT.md` yang menjelaskan arsitektur existing dan titik integrasi yang tepat.
- Membuat mapping kebutuhan dokumen ini ke modul, tabel, komponen, service, dan pola yang sudah ada.
- Mengidentifikasi konflik, risiko, dependency, serta keputusan yang perlu dikonfirmasi.
- **Tidak mengimplementasikan fitur sebelum audit dan rencana integrasi disampaikan.**

---

# 1. Ringkasan produk

## 1.1 Konteks

MyTools merupakan aplikasi induk yang berisi berbagai tools untuk membantu menyelesaikan masalah nyata yang dihadapi pemilik/pengguna. Product Decision Assistant akan ditambahkan sebagai salah satu tool di dalam MyTools, bukan sebagai produk atau aplikasi standalone.

Pengguna menghadapi kesulitan ketika ingin membeli suatu barang karena terdapat banyak merek dan model dengan harga, spesifikasi, rating, serta ulasan yang berbeda. Membaca semua ulasan secara manual membutuhkan waktu dan sulit menghasilkan perbandingan yang konsisten.

Product Decision Assistant membantu pengguna membandingkan produk berdasarkan:

- Identitas dan spesifikasi produk.
- Harga dan informasi listing yang tersedia.
- Rating dan ulasan pelanggan.
- Sentimen terhadap aspek tertentu dari produk.
- Preferensi dan batas anggaran pengguna.

Sistem mengolah data tersebut menjadi insight, perbandingan, dan rekomendasi yang transparan. Rekomendasi bukan klaim bahwa suatu produk secara objektif paling baik untuk semua orang.

## 1.2 Pernyataan solusi

Product Decision Assistant adalah fitur analisis dan pendukung keputusan pembelian yang menggabungkan **data analytics, NLP/Aspect-Based Sentiment Analysis (ABSA), dan Multi-Criteria Decision Making (MCDM)** untuk membantu pengguna memilih produk yang paling sesuai dengan kebutuhan dan bukti data yang tersedia.

## 1.3 Prinsip produk

- **Evidence over hype:** rekomendasi didukung data dan bukti ulasan.
- **Preference-aware:** pilihan terbaik bergantung pada kebutuhan pengguna.
- **Explainable:** sistem menjelaskan mengapa produk berada pada peringkat tertentu.
- **Data quality first:** kualitas identitas produk, ulasan, sumber, dan waktu data harus dijaga.
- **Multi-category by design:** domain dapat diperluas tanpa mengunci struktur aplikasi pada TWS.
- **Incremental integration:** fitur mengikuti arsitektur dan design system MyTools.
- **Honest uncertainty:** jika data kurang, sistem menyatakan keterbatasan dan tidak memaksakan rekomendasi.

## 1.4 Tujuan

1. Mengurangi waktu dan kebingungan saat membandingkan produk.
2. Mengubah ulasan teks menjadi insight aspek produk yang terstruktur.
3. Menampilkan kelebihan, kekurangan, dan coverage bukti untuk setiap produk.
4. Menghasilkan ranking berdasarkan kriteria dan bobot kebutuhan pengguna.
5. Menyediakan fondasi teknis untuk kategori produk lain.
6. Menjadi implementasi nyata Data Analytics dan AI/ML di dalam MyTools.

## 1.5 Bukan tujuan fitur ini

- Tidak menjamin kualitas produk secara objektif atau laboratoris.
- Tidak menjamin keaslian setiap review kecuali tersedia mekanisme verifikasi yang sah.
- Tidak melakukan transaksi, checkout, pembayaran, atau pembelian otomatis.
- Tidak menjadi marketplace atau sistem katalog seluruh produk di internet.
- Tidak mengambil data dari platform dengan cara melanggar persyaratan akses.
- Tidak membangun chatbot generatif sebagai satu-satunya mesin rekomendasi.
- Tidak melatih model untuk semua kategori sekaligus pada fase pertama.
- Tidak membuat aplikasi baru yang terpisah dari MyTools.

---

# 2. Ruang lingkup dan strategi kategori

## 2.1 Strategi multi-category

Fondasi data dan domain dirancang untuk mendukung banyak kategori sejak awal. Namun, data pipeline, taxonomy, anotasi, model, dan evaluasi pertama difokuskan pada kategori **TWS**.

Perbedaan penting:

- **Multi-category architecture:** wajib menjadi pertimbangan desain awal.
- **Multi-category model training:** bukan kewajiban MVP.
- **TWS pilot:** kategori pertama yang harus dibuktikan dengan dataset dan evaluasi nyata.

Kategori ekspansi yang mungkin: laptop, smartphone, smartwatch, power bank, dan perangkat elektronik lain. Kategori tersebut bukan komitmen implementasi MVP.

## 2.2 Category-specific configuration

Setiap kategori harus dapat memiliki konfigurasi sendiri, minimal:

- Category identifier dan nama.
- Attribute/specification definitions.
- Unit, tipe data, dan validasi atribut.
- Aspect taxonomy untuk analisis ulasan.
- Sinonim/alias aspek.
- Kriteria rekomendasi.
- Tipe kriteria: benefit, cost, atau utility function khusus.
- Default preference weights bila memang disediakan.
- Aturan normalisasi dan kelengkapan data.

Jangan mengasumsikan semua kategori mempunyai aspek atau spesifikasi yang sama.

## 2.3 TWS pilot taxonomy — baseline awal

Taxonomy berikut merupakan rancangan awal dan wajib divalidasi melalui audit dataset serta anotasi.

| Aspect key | Nama aspek | Contoh istilah/opini | Catatan |
|---|---|---|---|
| `sound_quality` | Kualitas suara | bass, treble, jernih, detail, cempreng | Pisahkan opini kualitas suara dari volume jika dibutuhkan |
| `battery` | Baterai | awet, boros, cepat habis, charging case | Bedakan earbud dan case jika data memungkinkan |
| `comfort` | Kenyamanan | nyaman, sakit, longgar, pas di telinga | Pengalaman pengguna |
| `connectivity` | Konektivitas | pairing, putus-putus, Bluetooth, delay | Bedakan koneksi dari latency jika taxonomy diperinci |
| `microphone` | Mikrofon | mic jernih, suara kecil, noise | Utamanya pengalaman call/meeting |
| `anc_transparency` | ANC/transparency | noise cancellation, mode transparansi | Aspek opsional jika relevan pada produk |
| `build_quality` | Kualitas material | casing, engsel, mudah rusak, kokoh | Dapat mencakup durability dengan aturan jelas |
| `controls_app` | Kontrol dan aplikasi | touch control, aplikasi, gesture, EQ | Aspek gabungan dapat dipecah setelah audit |
| `price_value` | Harga/value | mahal, murah, worth it, sepadan | Bedakan harga nominal dengan persepsi value |
| `warranty_support` | Garansi/dukungan | garansi, service center, klaim garansi | Jangan dicampur dengan kualitas hardware |
| `seller_shipping` | Penjual/pengiriman | packing, kurir, seller, pengiriman | **Bukan kualitas produk**; simpan sebagai aspek eksternal dan kecualikan dari skor kualitas produk secara default |

Taxonomy dapat diperbarui dengan versioning. Perubahan taxonomy tidak boleh diam-diam mengubah hasil analisis terdahulu tanpa menyimpan versi yang digunakan.

---

# 3. Aktor dan hak akses

Hak akses harus mengikuti sistem role/permission yang sudah ada di MyTools. Jangan membuat sistem autentikasi atau role baru jika sudah tersedia.

| Aktor | Kemampuan konseptual |
|---|---|
| Pengguna MyTools | Menjelajahi produk, membandingkan, menyimpan preferensi, meminta rekomendasi |
| Pengelola data/admin | Mengelola kategori, produk, sumber data, import, dan validasi data sesuai permission existing |
| Researcher/operator (opsional) | Melihat hasil evaluasi model, dataset, job analisis, dan metadata model |

Jika MyTools hanya memiliki satu jenis pengguna saat ini, implementasi harus mengikuti model tersebut dan tidak menciptakan role kompleks tanpa kebutuhan.

---

# 4. User stories dan alur utama

## 4.1 User stories

### Product discovery

- Sebagai pengguna, saya ingin memilih kategori produk agar hanya melihat produk yang relevan.
- Sebagai pengguna, saya ingin mencari produk berdasarkan merek dan nama model.
- Sebagai pengguna, saya ingin melihat harga, atribut, sumber, dan tanggal data.

### Product comparison

- Sebagai pengguna, saya ingin memilih beberapa produk dari kategori yang sama untuk dibandingkan.
- Sebagai pengguna, saya ingin melihat perbandingan spesifikasi secara berdampingan.
- Sebagai pengguna, saya ingin mengetahui data mana yang tidak tersedia atau tidak sebanding.

### Review intelligence

- Sebagai pengguna, saya ingin melihat ringkasan pengalaman konsumen berdasarkan aspek produk.
- Sebagai pengguna, saya ingin melihat aspek yang sering dipuji dan dikeluhkan.
- Sebagai pengguna, saya ingin membuka bukti ulasan yang mendukung insight.
- Sebagai pengguna, saya ingin mengetahui berapa banyak ulasan yang menjadi dasar analisis.

### Recommendation

- Sebagai pengguna, saya ingin menentukan batas anggaran.
- Sebagai pengguna, saya ingin mengatur aspek yang paling penting bagi saya.
- Sebagai pengguna, saya ingin memperoleh ranking produk yang disertai alasan dan keterbatasan data.

### Data management

- Sebagai pengelola, saya ingin mengimpor data dari file yang didukung.
- Sebagai pengelola, saya ingin melihat ringkasan validasi import sebelum menyimpan data.
- Sebagai pengelola, saya ingin mengetahui sumber, lisensi, waktu pengambilan, dan versi dataset.
- Sebagai pengelola, saya ingin menjalankan atau menjadwalkan analisis ulang sesuai fasilitas MyTools yang tersedia.

## 4.2 Alur pengguna utama

1. Pengguna membuka tool Product Decision Assistant dari navigation MyTools.
2. Pengguna memilih kategori TWS.
3. Pengguna mencari atau memilih produk.
4. Pengguna melihat detail produk, harga, atribut, review count, dan tanggal update.
5. Pengguna dapat memilih produk untuk dibandingkan.
6. Pengguna dapat membuka Review Insights untuk melihat sentimen per aspek dan contoh bukti review.
7. Pengguna membuka Recommendation.
8. Pengguna mengatur anggaran dan bobot preferensi.
9. Sistem memvalidasi preferensi, ketersediaan data, dan eligibility produk.
10. Sistem menghitung ranking menggunakan versi algoritma yang tercatat.
11. Pengguna melihat hasil ranking, alasan, kekuatan, kelemahan, coverage, dan bukti review.
12. Pengguna dapat mengubah bobot dan menghitung ulang.

## 4.3 Alur pengelolaan data

1. Admin memilih sumber data atau jenis import.
2. Sistem memeriksa tipe file, ukuran, kolom, dan format.
3. Sistem menampilkan preview dan hasil validasi.
4. Admin memetakan kolom sumber ke field internal bila diperlukan.
5. Sistem melakukan deduplication dan entity validation.
6. Sistem menyimpan record yang lolos validasi dan melaporkan record yang ditolak/ditahan.
7. Data baru masuk antrean analisis bila analisis otomatis memang didukung oleh arsitektur existing.
8. Status job dan hasilnya dapat dilihat oleh pengguna yang berwenang.

---

# 5. Functional requirements

Prioritas:

- **P0:** wajib untuk MVP.
- **P1:** tahap berikutnya setelah MVP stabil.
- **P2:** pengembangan lanjutan.

| ID | Fitur | Prioritas | Requirement |
|---|---|---:|---|
| FR-001 | Integrasi navigation | P0 | Tool dapat dibuka melalui pola navigation MyTools yang sudah ada |
| FR-002 | Category catalog | P0 | Sistem menampilkan kategori aktif yang memiliki data |
| FR-003 | Product catalog | P0 | Pengguna dapat mencari dan melihat produk per kategori |
| FR-004 | Product detail | P0 | Detail menampilkan identitas, atribut, sumber, dan freshness data |
| FR-005 | Product comparison | P0 | Pengguna dapat membandingkan produk dalam kategori yang sama |
| FR-006 | Review display | P0 | Review dapat ditelusuri ke produk dan sumbernya sesuai izin |
| FR-007 | Dataset import | P0 | Pengelola dapat mengimpor format yang didukung melalui proses validasi |
| FR-008 | Data quality report | P0 | Sistem melaporkan invalid rows, duplicate candidates, missing mappings, dan coverage |
| FR-009 | Review preprocessing | P0 | Teks dapat dinormalisasi tanpa menghapus raw text yang diperlukan untuk audit |
| FR-010 | Sentiment baseline | P0 | Pipeline baseline dapat diuji dengan data berlabel dan menghasilkan metrik |
| FR-011 | Aspect taxonomy | P0 | TWS memiliki taxonomy yang terversi dan configurable |
| FR-012 | ABSA inference | P0 | Sistem dapat menghasilkan prediksi aspek/sentimen untuk data yang didukung model |
| FR-013 | Evidence traceability | P0 | Insight aspek dapat ditelusuri ke review evidence yang diizinkan |
| FR-014 | Review analytics | P0 | Dashboard menampilkan volume review, distribusi sentimen, aspek, dan keterbatasan data |
| FR-015 | Recommendation preferences | P0 | Pengguna dapat mengatur budget dan bobot kriteria |
| FR-016 | SAW ranking | P0 | Sistem menghitung ranking berdasarkan kriteria valid dan bobot |
| FR-017 | Explainable result | P0 | Hasil menampilkan skor, kontribusi kriteria, evidence, coverage, dan versi metode |
| FR-018 | Recommendation history | P1 | Pengguna dapat melihat hasil rekomendasi sebelumnya jika sesuai pola MyTools |
| FR-019 | Conversational input | P1 | Chat membantu mengubah kebutuhan bahasa natural menjadi parameter terstruktur |
| FR-020 | Semantic review search | P2 | Pengguna dapat mencari review berdasarkan makna jika infrastruktur mendukung |
| FR-021 | Price history/tracking | P2 | Sistem menyimpan dan menampilkan riwayat harga bila data temporal mencukupi |
| FR-022 | Additional categories | P1/P2 | Kategori baru dapat ditambahkan melalui konfigurasi dan data tanpa mengubah core engine secara besar |

## 5.1 P0 product comparison rules

- Produk yang dibandingkan harus berasal dari kategori sama, kecuali fitur lintas kategori secara eksplisit dirancang kemudian.
- Varian harus dibedakan bila perbedaan varian berdampak pada spesifikasi atau harga.
- Satuan spesifikasi harus distandardisasi sebelum ditampilkan sebagai perbandingan.
- Nilai kosong ditampilkan sebagai “Data tidak tersedia”, bukan nol.
- Sumber dan waktu pembaruan data harus terlihat.
- Harga dari listing berbeda tidak boleh disajikan seolah-olah merupakan harga tetap produk.

## 5.2 P0 review analytics rules

- Review harus memiliki product mapping yang dapat dipertanggungjawabkan.
- Review seller/shipping tidak boleh menurunkan skor kualitas produk secara default.
- Review duplikat harus dideteksi dan ditangani.
- Rating mentah harus tetap disimpan terpisah dari prediksi sentimen.
- Prediksi model harus menyimpan versi model, waktu analisis, dan confidence/probability yang relevan.
- Sistem tidak boleh mengarang ringkasan atau kutipan review yang tidak ada.

---

# 6. Dataset, ingestion, dan data governance

## 6.1 Jenis data

### A. Product master data

Informasi identitas produk/model dan kategori.

Contoh field konseptual:

- product identifier internal.
- category identifier.
- brand.
- model name.
- model/series code jika tersedia.
- description.
- variant relationship.
- lifecycle/status.

### B. Product attributes/specifications

Atribut harus category-specific. Contoh TWS:

- battery life claim.
- battery capacity jika tersedia dan satuannya jelas.
- Bluetooth version.
- codec.
- ANC/transparency availability.
- water resistance rating.
- microphone count (bila terverifikasi).
- warranty duration.

Simpan value, unit, sumber, dan waktu verifikasi. Jangan mengisi atribut berdasarkan tebakan dari nama produk.

### C. Product listing/price observations

Harga melekat pada listing/observasi, bukan semata-mata identitas produk.

Field konseptual:

- product/variant reference.
- source/platform.
- seller reference jika penggunaannya diperbolehkan.
- observed price.
- currency.
- observed timestamp.
- listing URL/reference bila boleh disimpan.
- availability/condition bila tersedia.

### D. Reviews

Field konseptual:

- internal review ID.
- product/variant mapping.
- source ID.
- source review ID jika sah disimpan.
- raw review text.
- normalized review text.
- star rating (nullable).
- review date (nullable).
- collected/ingested timestamp.
- language.
- mapping confidence/status.
- deduplication fingerprint.
- permitted source reference.

Jangan mengumpulkan nama lengkap, nomor telepon, email, alamat, foto profil, atau data pribadi reviewer jika tidak benar-benar diperlukan dan tidak memiliki dasar izin yang memadai. Gunakan data seminimal mungkin.

### E. Annotation data

Label untuk training dan evaluation tidak boleh dicampur dengan pseudo-label tanpa penanda.

Field konseptual:

- review/span reference.
- aspect taxonomy version.
- aspect label.
- opinion span bila digunakan.
- polarity: positive, neutral, negative, mixed/uncertain bila skema mengizinkan.
- annotator/reference provenance.
- adjudication status.
- annotation guideline version.

### F. Model predictions

Field konseptual:

- review ID.
- model version.
- taxonomy version.
- aspect identifier.
- opinion/extracted span bila tersedia.
- sentiment label.
- class probabilities/confidence.
- inference timestamp.
- processing status.

### G. Source and dataset provenance

Setiap dataset/sumber harus mencatat:

- source name and type.
- source URL/reference bila boleh disimpan.
- owner/provider.
- license/permission/terms reference.
- permitted use and restrictions.
- collection method.
- collection time/window.
- dataset version/hash bila sesuai.
- field mapping.
- known limitations.

## 6.2 Dataset audit gate

Tidak ada dataset yang boleh menjadi sumber utama training/recommendation sebelum audit berikut diselesaikan:

1. Lisensi, terms, dan hak penggunaan dipahami.
2. Kategori dan jumlah produk diketahui.
3. Jumlah review per produk diketahui.
4. Identitas product/model dapat dipetakan dengan benar.
5. Distribusi bahasa dan kualitas teks diperiksa.
6. Duplikasi dan review spam/noise diperiksa sejauh memungkinkan.
7. Rating, tanggal, dan metadata lain diperiksa.
8. Label yang tersedia diidentifikasi asalnya: manusia, vendor, heuristic, atau model-generated.
9. Risiko bias dan keterbatasan dataset ditulis.
10. Train/validation/test split dapat dibuat tanpa leakage.

Output audit minimal: `DATASET_AUDIT_REPORT.md` dan `DATASET_CARD.md`.

## 6.3 Dataset TWS pilot

Target awal untuk menguji pipeline, bukan jaminan kecukupan statistik:

- 5–10 model TWS.
- Sekitar 100–200 review per model sebagai target eksplorasi awal bila data tersedia secara sah.
- Produk dan model harus teridentifikasi dengan jelas.
- Variasi review harus cukup untuk mengevaluasi aspek positif, negatif, dan netral.
- Data harga/spesifikasi mempunyai sumber dan timestamp.

Target anotasi pilot ABSA dapat dimulai dari 500–1.000 unit teks/kalimat yang dipilih secara terstratifikasi, kemudian disesuaikan berdasarkan distribusi aspek, learning curve, dan hasil evaluasi. Angka tersebut **bukan** klaim bahwa dataset sudah cukup untuk generalisasi final.

## 6.4 Sumber data dan scraping

Prioritas sumber:

1. Dataset publik dengan lisensi yang sesuai.
2. API/provider dengan izin penggunaan yang jelas.
3. Data hasil kerja sama atau izin pemilik sumber.
4. Import manual/CSV dari sumber yang penggunaannya diperbolehkan.

Scraping bukan asumsi default. Sebelum implementasi crawler, agent wajib:

- Menemukan sumber spesifik yang akan diambil.
- Memeriksa Terms of Service dan kebijakan akses.
- Memeriksa lisensi/hak penggunaan dataset.
- Mematuhi rate limits dan aturan robots yang relevan.
- Menghindari data pribadi yang tidak perlu.
- Tidak bypass authentication, CAPTCHA, paywall, anti-bot, atau pembatasan teknis.
- Menyimpan provenance setiap record.

Jika izin tidak jelas, gunakan dataset berlisensi atau mekanisme import yang sah. Jangan menulis crawler sampai sumber dan izin dinilai layak.

## 6.5 Data cleaning

Pipeline minimal:

1. Validate schema and data types.
2. Normalize whitespace and Unicode safely.
3. Preserve original raw text.
4. Normalize language/encoding where possible.
5. Detect exact duplicates.
6. Detect likely near-duplicates without deleting uncertain cases silently.
7. Validate product mapping.
8. Separate product review from seller/shipping/service review.
9. Validate rating range and timestamp.
10. Flag empty, spam-like, irrelevant, or unsupported-language records.
11. Produce import summary and rejected-row report.

Jangan menghapus negasi, emoji, slang, atau bentuk bahasa informal secara membabi buta karena dapat mengubah sentimen.

---

# 7. AI / NLP methodology

## 7.1 Peran AI

AI digunakan untuk memahami teks review dan menghasilkan struktur aspek serta sentimen. AI bukan penentu ranking akhir secara bebas.

Komponen rekomendasi harus deterministik dan dapat direproduksi berdasarkan input, bobot, konfigurasi kriteria, data snapshot, serta versi algoritma.

## 7.2 Tahapan model

### Stage 1 — Baseline sentiment

- TF-IDF + Logistic Regression.
- TF-IDF + Linear SVM.
- Gunakan data berlabel yang asal labelnya terdokumentasi.
- Bandingkan metrik per kelas, bukan accuracy saja.

### Stage 2 — Transformer baseline

- Evaluasi pretrained model Bahasa Indonesia yang relevan.
- IndoBERT merupakan kandidat, bukan keputusan mutlak sebelum dataset dan compute diaudit.
- Fine-tune hanya dengan dataset yang hak penggunaan dan labelnya jelas.
- Catat model card, hyperparameters, seed, split, dan dependencies.

### Stage 3 — Aspect-Based Sentiment Analysis

Pendekatan awal yang realistis:

- Aspect taxonomy/alias untuk kandidat aspek.
- Aspect-conditioned sentiment classification: pasangan `(review, aspect)` dikirim ke model untuk menentukan polaritas aspek tersebut.
- Setelah baseline berjalan, evaluasi apakah aspect extraction perlu ditingkatkan ke sequence labeling atau triplet extraction (aspect-opinion-sentiment).

Jangan mengklaim bahwa model sentiment biasa otomatis merupakan ABSA.

## 7.3 Contoh input dan output

Input review:

> “Bass-nya enak dan baterainya awet, tetapi koneksi sering putus saat HP agak jauh.”

Output terstruktur ilustratif:

```json
{
  "review_id": "review-example-001",
  "taxonomy_version": "tws-v1",
  "predictions": [
    {
      "aspect_key": "sound_quality",
      "opinion_span": "Bass-nya enak",
      "sentiment": "positive"
    },
    {
      "aspect_key": "battery",
      "opinion_span": "baterainya awet",
      "sentiment": "positive"
    },
    {
      "aspect_key": "connectivity",
      "opinion_span": "koneksi sering putus",
      "sentiment": "negative"
    }
  ]
}
```

Ini hanya contoh skema, bukan output model aktual. Output produksi harus menyertakan versi model, probabilities/confidence, dan status inference.

## 7.4 Annotation guidelines

Sebelum training ABSA:

- Definisikan unit anotasi (review, sentence, atau span).
- Definisikan aspect taxonomy dan contoh positif/negatif/netral.
- Definisikan penanganan mixed sentiment, implicit aspect, ironi, negasi, dan review di luar domain.
- Pisahkan aspek produk dari seller/shipping/service.
- Berikan panduan anotasi tertulis dan contoh edge cases.
- Anotasikan sebagian data secara independen oleh minimal dua annotator bila memungkinkan.
- Hitung inter-annotator agreement (misalnya Cohen’s Kappa untuk label kategorikal yang sesuai).
- Selesaikan disagreement melalui adjudication.
- Simpan annotation guideline version.

Label otomatis dari model lain adalah pseudo-label, bukan ground truth manusia. Pseudo-label harus diberi penanda dan tidak digunakan sebagai test ground truth.

## 7.5 Dataset split dan leakage prevention

- Deduplicate sebelum splitting.
- Kelompokkan salinan/near-duplicate agar tidak tersebar ke train dan test.
- Untuk klaim generalisasi ke produk baru, gunakan product-group split sehingga produk pada test tidak muncul di train.
- Jika split acak per review digunakan sebagai eksperimen tambahan, jelaskan keterbatasannya.
- Jangan tuning model berdasarkan test set.
- Simpan seed dan manifest split.

## 7.6 Evaluasi model

Metrik minimum:

- Precision, recall, F1 per kelas.
- Macro F1 sebagai metrik penting untuk kelas tidak seimbang.
- Confusion matrix.
- Aspect extraction F1 bila tugas extraction dilakukan.
- Aspect sentiment classification Macro F1.
- Evaluasi per aspek dan per produk bila jumlah data memungkinkan.
- Calibration/reliability bila confidence digunakan untuk keputusan downstream.

Model hanya boleh dipromosikan ke production inference setelah memenuhi threshold yang disepakati berdasarkan baseline dan kualitas data. Threshold belum ditentukan dan harus ditetapkan setelah pilot dataset/evaluation.

## 7.7 Model lifecycle

Setiap hasil prediksi harus bisa ditelusuri ke:

- model identifier/version.
- model artifact checksum/reference.
- preprocessing version.
- taxonomy version.
- inference timestamp.
- dataset/review version.

Perubahan model atau taxonomy tidak boleh menimpa histori secara diam-diam. Reprocessing harus menciptakan versi hasil baru atau mengikuti pola versioning yang sudah ada di MyTools.

---

# 8. Product analytics and aspect aggregation

## 8.1 Analytics minimum

Per kategori dan produk, tampilkan bila data tersedia:

- total review yang dianalisis.
- distribusi rating mentah.
- distribusi sentimen keseluruhan.
- distribusi sentimen per aspek.
- aspek yang paling sering dibahas.
- aspek positif yang paling sering muncul.
- keluhan negatif yang paling sering muncul.
- perubahan dari waktu ke waktu bila tanggal cukup lengkap.
- coverage aspek dan jumlah evidence.
- tanggal data terakhir diperbarui.

Hindari menyajikan persentase tanpa denominator. Contoh: “70% positif” harus disertai “7 dari 10 review teranalisis”.

## 8.2 Sentiment scoring

Pemetaan sederhana untuk analisis awal:

- positive = +1.
- neutral = 0.
- negative = -1.

Jika probabilitas kelas tersedia, kandidat nilai review-aspect:

`sentiment_value = P(positive) - P(negative)`

Kemudian dapat dipetakan ke skala 0–100:

`aspect_value_0_100 = 50 * (sentiment_value + 1)`

Gunakan probabilitas yang telah dievaluasi kalibrasinya bila confidence weighting diperlukan. Jangan menafsirkan probabilitas model sebagai kepastian kebenaran.

## 8.3 Aggregation and smoothing

Untuk mengurangi ketidakstabilan produk dengan sedikit review, gunakan pendekatan smoothing terhadap prior kategori.

Salah satu bentuk konseptual:

`smoothed_score = (effective_n * observed_mean + m * category_prior) / (effective_n + m)`

Keterangan:

- `observed_mean`: rata-rata nilai sentimen aspek untuk produk.
- `effective_n`: jumlah bukti efektif; definisinya harus konsisten dan tidak boleh menyamarkan jumlah review asli.
- `category_prior`: baseline kategori/aspek dari dataset yang valid.
- `m`: kekuatan prior yang ditentukan melalui analisis/sensitivity testing.

Simpan juga nilai mentah, jumlah review asli, jumlah review valid, dan nilai smoothed. Jangan hanya menyimpan satu angka akhir.

**No evidence is not zero quality.** Jika aspek tidak memiliki bukti, nilainya harus `unknown/null`, bukan otomatis 0 atau 100.

## 8.4 Confidence and coverage

Pisahkan tiga hal:

1. **Aspect score:** ringkasan polaritas pengalaman pada aspek.
2. **Evidence volume:** berapa review yang mendukung skor.
3. **Confidence/coverage:** kualitas prediksi dan kecukupan data.

Jumlah review tidak sama dengan kualitas produk. Jumlah review juga tidak boleh langsung dijadikan bonus kualitas.

UI harus menjelaskan apabila hasil berasal dari sampel kecil, prediksi confidence rendah, atau data yang tidak representatif.

---

# 9. Recommendation engine — MCDM / SAW

## 9.1 Tujuan

Recommendation Engine memilih dan mengurutkan produk yang paling sesuai dengan preferensi pengguna, bukan menentukan “produk terbaik universal”.

Metode baseline: **Simple Additive Weighting (SAW)**. Metode ini dipilih karena transparan dan mudah direproduksi. Metode lain seperti TOPSIS/PROMETHEE dapat diuji kemudian sebagai pembanding, bukan ditambahkan tanpa kebutuhan.

## 9.2 Input rekomendasi

- Category ID.
- Budget maximum/minimum (optional sesuai UI).
- Candidate products atau filter pencarian.
- Preference weights.
- Criteria configuration version.
- Data snapshot/version.
- Minimum evidence/coverage rules.

Semua bobot harus tervalidasi. Jika total bobot tidak sama dengan 1, sistem dapat menormalisasi secara deterministik atau meminta pengguna memperbaiki input. Perilaku harus konsisten dan dijelaskan.

## 9.3 Tipe kriteria

- **Benefit:** nilai lebih tinggi lebih diinginkan, contoh aspect satisfaction score.
- **Cost:** nilai lebih rendah lebih diinginkan, contoh harga.
- **Utility function:** nilai mentah dipetakan ke desirability sesuai aturan kategori, contoh rentang baterai atau garansi.

Jangan menyamakan skala spesifikasi yang berbeda tanpa fungsi normalisasi yang masuk akal.

## 9.4 Normalization

Bentuk dasar SAW untuk data positif:

Benefit:

`r_ij = x_ij / max(x_j)`

Cost:

`r_ij = min(x_j) / x_ij`

Rumus di atas hanya digunakan ketika asumsi data terpenuhi. Untuk harga nol/invalid, data ekstrem, atau spesifikasi dengan utility nonlinear, gunakan validasi dan utility mapping yang terdokumentasi.

Pertimbangkan fungsi normalisasi yang stabil dan tidak berubah secara tidak terduga ketika produk baru ditambahkan. Jika skor bergantung pada min/max kandidat saat itu, hasil ranking dapat berubah hanya karena kandidat lain masuk/keluar. Konfigurasi skala tetap atau utility function per kategori lebih mudah diaudit.

## 9.5 Final scoring

Bentuk dasar:

`V_i = sum(w_j * r_ij)`

Setiap recommendation run harus menyimpan:

- input preferences.
- normalized weights.
- criteria configuration version.
- candidate set dan data snapshot.
- nilai kriteria sebelum/sesudah normalisasi.
- kontribusi setiap kriteria.
- final score dan rank.
- eligibility/exclusion reason.
- recommendation algorithm version.

## 9.6 Missing data policy

- Nilai kosong tidak boleh dianggap nol secara otomatis.
- Nilai kosong tidak boleh dianggap nilai terbaik.
- Opsi yang mungkin: exclude candidate bila critical criteria kosong; atau renormalize bobot hanya jika coverage minimum terpenuhi dan hal itu ditampilkan dengan jelas.
- Produk dengan coverage rendah tidak boleh dibandingkan seolah-olah memiliki evidence lengkap.
- Jika criteria coverage tidak cukup, sistem harus menampilkan “data belum cukup untuk rekomendasi yang andal”.

Jangan menggunakan renormalization tanpa batas karena produk yang hanya memiliki satu aspek terukur bisa mendapat skor tinggi secara tidak adil.

## 9.7 Budget policy

- Jika pengguna menentukan batas maksimum, default adalah mengecualikan listing di atas batas tersebut.
- Jika tidak ada produk yang memenuhi anggaran, jangan diam-diam melonggarkan batas. Tampilkan tidak ada hasil dan sediakan opsi bagi pengguna untuk mengubah anggaran.
- Harga harus menunjukkan sumber, waktu observasi, dan mata uang.
- Jangan menyebut harga sebagai harga terkini jika timestamp sudah tidak memenuhi freshness policy.

## 9.8 Recommendation explanation

Hasil ranking minimum menampilkan:

- rank dan final score.
- budget eligibility.
- strengths dan weaknesses berdasarkan aspect score.
- kontribusi kriteria terhadap final score.
- jumlah review/evidence per aspek.
- coverage atau missing criteria.
- tanggal data.
- algoritma/configuration version.
- bukti review yang mendukung insight, dengan kutipan singkat dan sumber bila diizinkan.

Jangan menghasilkan alasan yang tidak dapat ditelusuri ke data.

## 9.9 Baseline comparison eksperimen

Untuk validasi akademik/teknis, bandingkan:

- E1: rating-only.
- E2: specification-only.
- E3: ABSA-only.
- E4: hybrid ABSA + specification + price + preference.

Klaim peningkatan hanya boleh dibuat bila memiliki ground truth atau protokol evaluasi relevansi yang sah.

---

# 10. UI/UX requirements

## 10.1 Integrasi visual

- Ikuti design system, typography, spacing, colors, component library, responsive rules, dan interaction patterns MyTools.
- Jangan membuat design system kedua.
- Jangan mengubah global navigation/layout kecuali diperlukan dan disetujui.
- Gunakan komponen existing yang sesuai.
- Sediakan loading, empty, error, partial-data, and permission-denied states.
- Pastikan layout dapat digunakan di viewport desktop dan mobile sesuai dukungan MyTools.

## 10.2 Halaman/area konseptual

Nama route dan struktur aktual ditentukan setelah audit routing MyTools.

### A. Tool overview / landing

- Deskripsi singkat tool.
- Kategori yang tersedia.
- Pencarian produk.
- Shortcut untuk perbandingan/rekomendasi bila ada.
- Status ketersediaan data jika relevan.

### B. Product explorer

- Filter kategori.
- Search brand/model.
- Filter harga/specification jika datanya ada.
- Indikator review count dan data freshness.
- Jangan menampilkan produk tanpa identitas yang cukup sebagai item seolah valid.

### C. Product detail

- Nama brand/model dan variant.
- Spesifikasi.
- Harga/listings dengan timestamp.
- Rating mentah dan volume review.
- Ringkasan aspek.
- Evidence review.
- Coverage dan keterbatasan analisis.

### D. Product comparison

- Perbandingan spesifikasi berdampingan.
- Harga dan tanggal observasi.
- Aspek yang paling kuat/lemah.
- Perbedaan review volume dan coverage.
- Missing values.

### E. Review intelligence dashboard

- Sentiment distribution.
- Aspect-level sentiment.
- Most-discussed aspects.
- Positive/negative insight.
- Evidence snippets.
- Filter waktu/sumber bila data mendukung.

### F. Recommendation flow/result

- Input budget.
- Preference weights.
- Validasi total bobot.
- Hasil ranking.
- Explanation and evidence.
- Coverage warnings.
- Option to adjust weights and recalculate.

### G. Data management (permission-gated)

- Import/preview.
- Column mapping.
- Validation summary.
- Import history/status.
- Dataset/source metadata.
- Analysis job status.

## 10.3 Copywriting and claims

Gunakan istilah yang jujur:

- “Paling sesuai dengan preferensi Anda” lebih tepat daripada “produk terbaik”.
- “Berdasarkan 42 ulasan yang dianalisis” lebih tepat daripada “konsumen menyukai”.
- “Model memprediksi sentimen positif” lebih tepat daripada “review terbukti positif”.
- Tampilkan “data belum cukup” bila memang belum cukup.

---

# 11. Conversational AI (P1)

Chatbot bukan mesin ranking. Chatbot hanya antarmuka untuk menangkap maksud pengguna dan membantu menjelaskan hasil.

## 11.1 Fungsi yang diperbolehkan

- Memahami kategori produk.
- Mengambil budget dari bahasa natural.
- Memahami prioritas, misalnya baterai dan kualitas suara.
- Mengubah input ke structured preferences.
- Memanggil recommendation service melalui API internal yang tervalidasi.
- Merangkum hasil dari data hasil rekomendasi.
- Menjawab pertanyaan tentang bukti yang tersedia.

## 11.2 Batasan

- LLM tidak boleh mengarang produk, harga, spesifikasi, ranking, atau ulasan.
- Semua klaim produk harus diambil dari catalog/analytics/recommendation result.
- Output LLM untuk preferensi harus divalidasi schema dan business rules.
- Jika parameter ambigu, minta klarifikasi seperlunya.
- Jangan mengeksekusi pembelian atau transaksi.
- Simpan API key hanya di server-side secret management existing.
- Jika provider LLM tidak tersedia, fitur katalog, analytics, dan ranking harus tetap berjalan.

Contoh structured intent:

```json
{
  "category_key": "tws",
  "budget_max": 500000,
  "currency": "IDR",
  "weights": {
    "sound_quality": 0.40,
    "battery": 0.30,
    "comfort": 0.15,
    "connectivity": 0.10,
    "microphone": 0.05
  }
}
```

---

# 12. Conceptual data model

> **Penting:** ini model domain konseptual, bukan instruksi langsung membuat tabel dengan nama persis. Setelah repository audit, sesuaikan dengan database, ORM, naming conventions, existing entities, dan migration patterns MyTools. Hindari menduplikasi tabel yang sudah ada.

## 12.1 Entitas konseptual

| Entity | Tujuan | Relasi penting |
|---|---|---|
| Category | Kategori produk | Memiliki products, attributes, aspects, criteria |
| CategoryAttributeDefinition | Definisi spesifikasi category-specific | Dimiliki category |
| Product | Identitas model produk | Milik category; memiliki variants, reviews, attributes |
| ProductVariant | Varian model | Milik product |
| ProductAttributeValue | Nilai spesifikasi | Mengacu product/variant dan attribute definition |
| ProductListing/PriceObservation | Harga/listing dari sumber pada waktu tertentu | Mengacu product/variant dan data source |
| DataSource | Metadata asal data | Memiliki products/listings/reviews/imports |
| Review | Ulasan konsumen | Mengacu product/variant dan source |
| AspectDefinition | Taxonomy aspek | Milik category dan taxonomy version |
| ReviewAspectPrediction | Hasil ABSA per review-aspect | Mengacu review, aspect, model version |
| ProductAspectAggregate | Ringkasan aspek per product | Mengacu product, aspect, aggregation version |
| ModelVersion | Metadata model | Digunakan prediction jobs |
| DatasetVersion/ImportBatch | Versi dataset dan import | Mengacu data source dan records |
| AnalysisJob | Status pekerjaan batch analysis | Mengacu import/model/dataset bila relevan |
| RecommendationProfile | Preferensi yang disimpan (opsional) | Mengacu pengguna existing |
| RecommendationRun | Satu eksekusi rekomendasi | Menyimpan input, algorithm version, snapshot |
| RecommendationItem | Hasil rank per product | Mengacu run dan product |
| RecommendationEvidence | Evidence untuk keputusan | Mengacu item, review, aspect, atau attribute |

## 12.2 Relational rules

- Product belongs to one category in the initial model.
- Product and variant must be distinct when variant data affects comparison.
- Listing/price observation is time-bound and source-bound.
- Review maps to one product/variant only when evidence supports that mapping.
- Review may have multiple aspect predictions.
- Aspect prediction belongs to a taxonomy version and model version.
- Product aspect aggregates are derived data and must be reproducible.
- Recommendation run stores the criteria and data snapshot needed to reproduce ranking.
- Foreign keys, unique constraints, cascade behavior, and indexes must follow MyTools conventions.

## 12.3 Flexible attributes

Gunakan pola attribute-definition + value atau pendekatan setara yang sesuai dengan database existing.

JSON/JSONB dapat dipertimbangkan untuk konfigurasi kategori atau metadata yang fleksibel jika database mendukung dan queryability masih terjaga. Jangan menyimpan seluruh domain utama sebagai satu JSON besar bila membutuhkan filtering, indexing, foreign keys, dan validasi relasional.

## 12.4 Index candidates

Tentukan setelah query patterns diketahui. Kandidat:

- category + product status.
- normalized product name/model.
- product + review date.
- product + source.
- review deduplication fingerprint.
- review + aspect + model version.
- recommendation run + rank.

Jangan menambah index berlebihan tanpa query plan/justifikasi.

---

# 13. API/service boundary

Endpoint di bawah bersifat konseptual. Nama, versioning, authentication, serialization, dan error conventions harus mengikuti API patterns MyTools.

| Capability | Operasi konseptual |
|---|---|
| Categories | List/get category and its configuration |
| Products | Search/list/get product |
| Comparison | Compare selected products in one category |
| Reviews | List/filter reviews and evidence |
| Analytics | Read product/category aspect analytics |
| Recommendation | Validate preferences and calculate ranking |
| Imports | Upload/preview/validate/commit dataset |
| Jobs | Inspect ingestion/analysis job status |
| Taxonomy | Read/manage category aspects under permission |
| Model metadata | Read active model and evaluation status where allowed |

## 13.1 Service design principles

- Keep business logic outside UI components.
- Keep model inference behind a clearly defined interface.
- Recommendation calculation must be deterministic and unit-testable.
- Do not expose raw internal exceptions to users.
- Validate every request and file upload.
- Paginate potentially large review/product lists.
- Use background jobs for long-running batch tasks if MyTools already provides a suitable mechanism.
- If no job mechanism exists, first assess workload and existing infrastructure before introducing one.

---

# 14. Architecture integration requirements

## 14.1 Required repository audit

Agent must identify:

| Area | What to inspect | Output needed |
|---|---|---|
| Project instructions | AGENTS, CLAUDE, README, contributor docs | Binding rules |
| Frontend | Framework, routing, layouts, state, component patterns | Feature integration point |
| Backend | Framework, modules, API conventions, service patterns | Domain integration point |
| Database | Database, ORM, migrations, existing entities | Reuse/extension proposal |
| Auth | Existing user and permissions model | Access control reuse |
| Design system | Tokens, components, theme, typography | UI consistency plan |
| Testing | Unit/integration/e2e setup | Test plan |
| Data/ML | Existing Python packages, worker, notebooks, model runtime | ML integration proposal |
| Storage | File/object storage and import patterns | Dataset handling plan |
| Deployment | Build, environments, secrets, hosting | Release plan |

## 14.2 Architecture decision rules

1. If MyTools already has a Python backend, assess adding an ML module/package there before proposing a separate inference service.
2. If MyTools backend is not Python, assess the lowest-complexity integration consistent with existing architecture. A separate Python inference process/service is an option only if there is a concrete technical reason.
3. If MyTools already has background jobs/queues, reuse them for dataset import and batch inference.
4. If there is no background job system, do not introduce one until workload and hosting constraints are understood.
5. Reuse existing database and ORM unless there is a demonstrated incompatibility.
6. Store model artifacts using the existing storage/deployment conventions. Do not commit large weights blindly to Git.
7. Prefer modular monolith integration. Microservices are out of scope for MVP.

## 14.3 No speculative scaffolding

Do not create placeholder folders/packages for technologies not present in the repository until the integration proposal has been reviewed. Do not add dependencies without a clear need, version compatibility check, and justification.

---

# 15. Non-functional requirements

## 15.1 Security and privacy

- Reuse MyTools authentication and authorization.
- Enforce authorization on server-side operations, not only hidden UI controls.
- Validate file uploads by type, size, and content; do not trust filename or MIME type alone.
- Protect against CSV formula injection when exporting user-controlled values.
- Keep secrets in environment/secret management already used by MyTools.
- Avoid logging raw review text or user preferences unless necessary; redact where appropriate.
- Minimize personal data collection.
- Record administrative import/reprocess actions when existing audit logging supports it.

## 15.2 Reliability

- Long-running import/inference should report progress/status where supported.
- Partial import failures must be visible and recoverable.
- Failed analysis must not corrupt previously valid analysis results.
- Retried jobs should be idempotent or use deduplication/idempotency keys.
- Recommendation results should be reproducible from stored inputs and versions.

## 15.3 Performance

Performance targets must be calibrated to actual MyTools hosting/data volumes. Initial expectations:

- Catalog/search endpoints should use pagination and database filtering.
- Product comparison should not trigger full model inference synchronously.
- ABSA batch processing should be asynchronous if execution is long-running.
- Cache derived analytics only if invalidation/versioning is safe.
- Avoid loading all reviews into application memory for a single product page.

Do not claim precise latency targets until environment and dataset sizes are known.

## 15.4 Accessibility and usability

- Keyboard-accessible controls.
- Clear form labels and validation messages.
- Sufficient contrast based on MyTools design system.
- Charts must have textual summaries or accessible data alternatives.
- Explain terms like ABSA, confidence, and score in user-facing help where needed.

## 15.5 Maintainability

- Follow existing lint/format/type conventions.
- Keep taxonomy and criteria configuration versioned.
- Keep model training code separate from inference code where appropriate.
- Add tests for aggregation, normalization, weighting, missing data, and ranking.
- Document assumptions and limitations.

---

# 16. Testing and quality assurance

## 16.1 Unit tests

At minimum:

- Product/category validation.
- Attribute unit normalization.
- Review deduplication.
- Product mapping validation.
- Seller/shipping aspect exclusion from product quality score.
- ABSA output schema validation.
- Aspect aggregation.
- Smoothing behavior.
- Weight validation and normalization.
- Benefit/cost utility calculation.
- Missing criteria behavior.
- Budget exclusion behavior.
- SAW ranking reproducibility.
- Recommendation explanation/evidence linkage.

## 16.2 Integration tests

- Create/read category configuration through actual persistence layer.
- Import valid dataset and inspect saved records.
- Reject malformed/unauthorized import.
- Ensure review links to correct product.
- Persist model predictions with version metadata.
- Read product analytics from stored predictions.
- Create recommendation run and retrieve items/evidence.
- Verify permission restrictions.

## 16.3 ML evaluation tests

- Fixed evaluation manifest.
- No overlap of duplicate groups between train/test.
- Report per-class and macro metrics.
- Report per-aspect performance.
- Validate prediction schema and confidence ranges.
- Check model artifact/version consistency.

## 16.4 End-to-end scenarios

### Scenario A — Product comparison

Given at least two valid TWS products, the user can compare their attributes, price observations, reviews, and aspect insights. Missing data is shown explicitly.

### Scenario B — Personalized recommendation

Given a budget and valid preference weights, the system excludes products above budget, computes scores, and returns a deterministic ranking with explanation and evidence.

### Scenario C — Insufficient data

Given a product with too few valid reviews or missing critical criteria, the system displays insufficient evidence and does not manufacture a confident recommendation.

### Scenario D — Import validation

Given a file with invalid rows and duplicates, the system previews counts and stores only accepted records according to explicit rules. Rejected rows are reported.

### Scenario E — Category expansion

Given a new category configuration and matching data, the system can display products and criteria using the shared core without hard-coded TWS-only logic. The new category is not considered ML-supported until model evaluation validates it.

## 16.5 Definition of Done

Fitur MVP belum dianggap selesai sebelum:

- Terintegrasi ke navigation/layout MyTools.
- Tidak menduplikasi autentikasi, database, atau design system.
- TWS category configuration tersedia.
- Product/review dataset memiliki provenance yang jelas.
- Import/validation workflow diuji.
- Model ABSA memiliki evaluation report pada test data yang sah.
- Analytics menampilkan denominator, coverage, dan timestamp.
- SAW dapat direproduksi dan melewati unit tests.
- Rekomendasi menampilkan alasan/evidence dan keterbatasan.
- Permission dan upload validation diuji.
- Dokumentasi dan migration sesuai standar repository.
- Tidak ada data simulasi yang tampil sebagai data aktual.

---

# 17. Development phases and deliverables

Phases berikut adalah urutan dependensi, bukan estimasi waktu.

## Phase 0 — MyTools repository discovery (mandatory first)

Tasks:

- Audit repository and project instructions.
- Map architecture and integration points.
- Identify existing reusable components/services/entities.
- Identify constraints in hosting, storage, background jobs, and ML execution.
- Write integration proposal and open questions.

Deliverables:

- `PRODUCT_DECISION_ASSISTANT_REPOSITORY_AUDIT.md`
- `PRODUCT_DECISION_ASSISTANT_INTEGRATION_PLAN.md`
- No code changes unless explicitly requested after review.

## Phase 1 — Data feasibility and domain design

Tasks:

- Inspect candidate datasets and licenses.
- Measure product/review coverage for TWS.
- Define TWS attribute schema and aspect taxonomy.
- Define annotation guideline.
- Create data dictionary and dataset card.

Deliverables:

- `DATASET_AUDIT_REPORT.md`
- `DATA_DICTIONARY.md`
- `TWS_ASPECT_TAXONOMY.md`
- `ANNOTATION_GUIDELINES.md`

## Phase 2 — Data foundation

Tasks:

- Extend existing schema using migration conventions.
- Implement category/product/review/source import patterns.
- Implement validation and deduplication.
- Add admin/import UI using existing design system.

Deliverables:

- Database migrations.
- Import/validation functionality.
- Unit and integration tests.

## Phase 3 — Analytics baseline

Tasks:

- EDA notebooks or scripts.
- Rating/review volume summaries.
- Baseline sentiment evaluation.
- Product aspect data coverage report.

Deliverables:

- Reproducible analysis.
- Analytics views/components.
- Baseline report.

## Phase 4 — ABSA

Tasks:

- Build/validate annotated pilot dataset.
- Train and compare models.
- Evaluate on a group-aware held-out test set.
- Register model version and inference interface.
- Run batch predictions and persist results.

Deliverables:

- Model artifact/reference.
- Model card.
- Evaluation report.
- Versioned prediction records.

## Phase 5 — Recommendation engine

Tasks:

- Define category criteria and utility mappings.
- Implement SAW calculation.
- Implement evidence/coverage policy.
- Compare rating-only, specification-only, ABSA-only, and hybrid baselines.

Deliverables:

- Deterministic recommendation service.
- Ranking tests.
- Evaluation report.

## Phase 6 — User experience integration

Tasks:

- Product explorer/detail.
- Comparison UI.
- Review intelligence dashboard.
- Recommendation preferences and result.
- Empty/error/insufficient-data states.

Deliverables:

- Integrated MyTools feature.
- E2E tests.

## Phase 7 — Optional conversational interface and expansion

Tasks:

- Convert natural-language intent to validated structured preferences.
- Integrate with recommendation service.
- Add new category configuration only when data/taxonomy/model support exists.

Deliverables:

- Optional assistant UI.
- Category expansion checklist and evaluation report.

---

# 18. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Insufficient TWS reviews | ABSA/recommendation unreliable | Dataset audit gate; clearly report insufficient data |
| Product identity mismatch | Wrong reviews attached to product | Model/variant mapping, confidence, manual review for uncertain matches |
| Unlicensed source | Legal/platform risk | Verify terms and use permissioned datasets/APIs/import |
| Seller complaints mixed with product complaints | Distorted product score | Separate external service aspects |
| Pseudo-label treated as truth | Inflated evaluation | Label provenance and human-validated test set |
| Class imbalance | Misleading accuracy | Macro F1, per-class metrics, sampling strategy |
| Leakage across products/reviews | Inflated generalization | Dedup and group-aware split |
| Few reviews produce extreme score | Misleading rankings | Smoothing, minimum evidence rules, coverage indicator |
| Missing specifications | Biased SAW score | Missing-data policy and coverage thresholds |
| Price stale | Misleading affordability | Timestamp/freshness policy |
| Model drift/domain shift | Declining performance | Per-category evaluation and model versioning |
| Architecture mismatch | Rework/complexity | Mandatory MyTools audit before coding |

---

# 19. Open decisions — must be resolved after repository/data audit

Do not fabricate answers for these items.

| ID | Question | Resolution source |
|---|---|---|
| OD-01 | What frontend framework and routing patterns does MyTools use? | Repository audit |
| OD-02 | What backend framework and module conventions exist? | Repository audit |
| OD-03 | What database and ORM are used? | Repository audit |
| OD-04 | Does MyTools already support file upload/import? | Repository audit |
| OD-05 | Is there an existing background job/queue mechanism? | Repository audit |
| OD-06 | Where should Python ML code run in the existing deployment? | Repository and hosting audit |
| OD-07 | What is the exact TWS dataset and its legal use? | Dataset audit |
| OD-08 | How many TWS products and valid reviews are available? | Dataset audit |
| OD-09 | Which TWS attributes can be sourced reliably? | Dataset/source audit |
| OD-10 | Which model and annotation strategy fit the pilot data? | Experiment results |
| OD-11 | What evidence threshold makes an item recommendation-eligible? | Data analysis and user evaluation |
| OD-12 | Which criteria and utility functions should be used for TWS? | Domain review and experiment |
| OD-13 | Does the existing MyTools user model support saved preference profiles? | Repository audit |
| OD-14 | Which charts/components already exist in MyTools? | Repository audit |

---

# 20. Required agent workflow

The AI agent must work through explicit gates.

## Gate 0 — Discover

- Read repository instructions and docs.
- Inspect architecture and existing modules.
- Do not edit files.
- Produce audit report.

## Gate 1 — Propose integration

- Map each feature requirement to existing code or proposed extension.
- List new entities/migrations only where needed.
- State whether ML is integrated in-process, as an existing worker, or via another justified boundary.
- List dependencies and risks.
- Wait for project owner approval before significant implementation.

## Gate 2 — Data feasibility

- Verify dataset provenance, license, schema, product coverage, and label quality.
- Produce data dictionary, taxonomy, and annotation guideline.
- Do not train/evaluate final models on unverified or pseudo-labeled test ground truth.

## Gate 3 — Implement vertical slices

Implement in small end-to-end increments:

1. Category/product read path.
2. Product/review import and validation.
3. Analytics baseline.
4. ABSA inference/evaluation.
5. Aggregation.
6. Recommendation.
7. UI integration.

Each slice must include tests and documentation.

## Gate 4 — Verify

- Run project lint/typecheck/tests/build as supported.
- Run migrations in a safe environment.
- Verify existing features are not broken.
- Verify data provenance and ranking reproducibility.
- Report failures and known limitations honestly.

## 20.1 Agent progress report format

After each phase, report:

1. What was inspected/implemented.
2. Files created/modified.
3. Existing conventions reused.
4. Tests and commands executed, with actual results.
5. Risks or unresolved questions.
6. Next smallest actionable step.

Do not claim a test passed unless it was actually run and the output supports that claim.

---

# 21. First task prompt — copy/paste to AI agent

Use this prompt together with this specification:

> You are working inside an existing project named **MyTools**. Read `PRODUCT_DECISION_ASSISTANT_SPEC.md` completely.
>
> The Product Decision Assistant is a new feature/module inside MyTools. It is NOT a standalone application. Do not create a new frontend, backend, database, authentication system, design system, repository, or deployment stack.
>
> **Your first task is repository discovery only. Do not modify application code yet.**
>
> 1. Read all applicable agent instructions (`AGENTS.md`, `CLAUDE.md`, README, contributor instructions, and other repository-specific rules).
> 2. Inspect the repository structure, framework manifests, routes/navigation, components/design system, backend modules/services, database schema/ORM/migrations, authentication/permissions, testing, file storage/imports, background jobs, ML/Python setup, and deployment configuration.
> 3. Identify existing reusable functionality and the smallest appropriate integration point for Product Decision Assistant.
> 4. Identify any conflicts between this specification and the existing architecture. Existing repository conventions take precedence over generic technology examples in the specification.
> 5. Create `PRODUCT_DECISION_ASSISTANT_REPOSITORY_AUDIT.md` containing: current stack (with evidence from files), architecture summary, existing reusable modules, proposed integration points, conceptual schema mapping, ML execution options, testing/deployment constraints, risks, and open questions.
> 6. Create `PRODUCT_DECISION_ASSISTANT_INTEGRATION_PLAN.md` mapping P0 requirements to specific existing paths/modules and identifying only the changes that are genuinely needed.
> 7. Do not install dependencies, run destructive commands, alter existing schema, or implement features during this discovery phase.
> 8. If the repository is incomplete or an item cannot be verified, mark it unknown instead of guessing.
>
> Stop after producing the two audit/planning documents and summarize the findings for the project owner. Wait for approval before implementing.

---

# 22. Glossary

| Term | Meaning |
|---|---|
| ABSA | Aspect-Based Sentiment Analysis: identifying aspects discussed in text and sentiment toward each aspect |
| Aspect | A product dimension such as battery, sound quality, or comfort |
| Opinion span | Words/phrase expressing an opinion about an aspect |
| Polarity | Positive, neutral, negative, or an explicitly defined alternative label |
| MCDM | Multi-Criteria Decision Making: evaluating options against multiple criteria |
| SAW | Simple Additive Weighting: weighted aggregation of normalized criteria |
| Evidence volume | Number of valid review observations supporting an aspect result |
| Coverage | Degree to which product criteria/aspects have sufficient data |
| Smoothing | Stabilizing a score using a documented prior to reduce small-sample extremes |
| Pseudo-label | Label generated by a heuristic/model rather than independently verified ground truth |
| Data provenance | Information about where data came from, how it was obtained, and under what terms |
| Product variant | A specific version/size/color/configuration of a product model |
| Listing | A seller/platform offer for a product/variant at a point in time |

---

# 23. Final product principle

**Product Decision Assistant must help users identify the product that best matches their preferences and the available evidence—not merely the product with the highest rating, the most reviews, or the strongest marketing.**

Its intelligence comes from the full, traceable pipeline:

`Authorized Data → Data Quality → ABSA → Aspect Analytics → Preference-aware MCDM → Explainable Recommendation`

All implementation decisions must preserve the fact that this capability is an extension of the existing **MyTools** project.
