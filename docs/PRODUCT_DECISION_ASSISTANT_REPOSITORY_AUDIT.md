# Product Decision Assistant — Repository Audit

Tanggal audit: 11 November 2026  
Ruang lingkup: discovery repository saja. Tidak ada kode aplikasi yang diubah.

## Ringkasan

MyTools saat ini adalah aplikasi desktop-web lokal untuk pengolahan media, bukan aplikasi katalog atau analisis produk. Stack yang tersedia memberi tempat integrasi yang masuk akal: frontend Next.js statis dan backend FastAPI/Python dalam satu aplikasi lokal. Belum ditemukan database, ORM, migration system, autentikasi, job queue, atau dataset produk/review.

Product Decision Assistant dapat ditambahkan sebagai modul baru dalam aplikasi yang sama. Katalog, analytics, ABSA, dan ranking memerlukan data persisten; keputusan penyimpanan dan sumber dataset menjadi prasyarat desain. Tahap ini tidak membenarkan scraping dari marketplace tertentu. Sumber dan hak penggunaannya perlu diperiksa sebelum data dikumpulkan.

## Bukti dan arsitektur saat ini

| Area | Temuan | Bukti |
|---|---|---|
| Bahasa/backend | Python 3.11+, FastAPI, Uvicorn, PyTorch, Transformers | `pyproject.toml`, `src/removebg/api.py` |
| Frontend | Next.js 16.4, React 19, TypeScript; static export | `web/package.json`, `web/next.config.ts`, `web/app/` |
| Cara menjalankan | Windows lokal; API di `127.0.0.1:7860`; dev frontend di `127.0.0.1:3000` | `run.ps1`, `scripts/dev.mjs`, `src/removebg/api.py` |
| API | Route FastAPI langsung didefinisikan dalam satu modul utama | `src/removebg/api.py` |
| UI/styling | Satu halaman utama dengan feature state; CSS global dan token warna lokal; tidak tampak component library terpisah | `web/app/page.tsx`, `web/app/globals.css`, `web/app/layout.tsx` |
| Database/ORM/migrasi | Tidak ditemukan | Tidak ada dependensi DB di `pyproject.toml`/`requirements-lock.txt`; tidak ada folder schema/migration pada file terlacak |
| Auth/permissions | Tidak ditemukan; aplikasi bind ke loopback dan berjalan lokal | `src/removebg/api.py`, `run.ps1` |
| File/storage | Upload di `%TEMP%`; hasil dibersihkan saat mulai/keluar normal; `data/` dan `models/` di-ignore Git | `src/removebg/config.py`, `src/removebg/api.py`, `.gitignore` |
| Background work | Thread per job, status di dictionary proses, satu `work_lock`; tidak ada queue persisten | `src/removebg/api.py` |
| ML | Model lokal RVM/SAM2/Whisper; cache di `models/`; CUDA sesuai fitur | `src/removebg/infrastructure/models.py`, `src/removebg/application/transcription.py`, `setup.ps1` |
| Analytics/NLP tambahan | Tidak ditemukan pandas, scikit-learn, notebook, atau training pipeline | `pyproject.toml`, `requirements-lock.txt`, struktur `src/` |
| Tes | Pytest; tes pipeline media dan unduhan | `pyproject.toml`, `tests/test_pipeline.py`, `tests/test_download.py` |
| Deployment | Setup Windows lokal, build Next static dan jalankan FastAPI; tidak ditemukan Docker/CI/deployment cloud | `setup.ps1`, `run.ps1`, `run.bat`, `scripts/dev.mjs` |

## Struktur relevan

- `src/removebg/api.py`: API, upload, status/cancel job, dan penyajian output.
- `src/removebg/application/`: alur use case media, transkrip, dan unduhan.
- `src/removebg/infrastructure/`: adapter model, codec/media, sumber/platform eksternal.
- `src/removebg/domain.py`: tipe dan validasi domain yang sekarang sederhana.
- `web/app/page.tsx`: semua fitur UI saat ini berada dalam satu halaman Next.
- `tests/`: tes backend menggunakan pytest.
- `data/`, `models/`: data kerja dan model lokal; keduanya tidak dikomit.

Belum ada data produk/review yang tampak dalam daftar file. Isi `data/` yang terlihat berupa sampel media dan laporan uji GPU; tidak tampak CSV/dataset produk TWS. Karena `data/` di-ignore Git, isi lokal yang tidak terdaftar tidak dapat dianggap sebagai dataset tersedia.

## Titik integrasi yang disarankan

1. **Backend modular monolith:** tambahkan use case dan domain Product Decision Assistant ke package Python yang sama. Route baru sebaiknya tipis dan memanggil service aplikasi; jangan menambah logika bisnis ke `api.py`.
2. **Frontend route terpisah di aplikasi yang sama:** static export Next mendukung halaman tambahan. Buat area/route baru dan tambahkan satu titik navigasi menuju route tersebut. Pertahankan halaman dan alur fitur media saat ini.
3. **Persistensi:** data produk, review, provenance, hasil prediksi, agregat, dan recommendation run tidak cocok disimpan hanya di dictionary proses. Karena DB belum ada, pilih mekanisme paling sederhana setelah pemilik menyetujui. SQLite layak dievaluasi untuk aplikasi lokal satu pengguna; ini usulan, bukan teknologi yang sudah tersedia/diputuskan. Jangan menambahkan ORM atau migration framework sebelum kebutuhan jelas.
4. **Analisis model:** pisahkan kontrak inferensi ABSA dari UI dan perhitungan ranking. Evaluasi baseline TF-IDF + Logistic Regression/Linear SVM dan transformer Bahasa Indonesia hanya setelah dataset berlabel yang sah tersedia. Dependensi training/evaluasi belum ada.
5. **Batch jobs:** tidak ada queue persisten. Import kecil/validasi dapat synchronous dengan batas ukuran. Batch ABSA perlu status/progress; ukur beban dahulu. Job media yang ada memakai satu `work_lock`, jadi jangan memasukkan proses baru ke jalur itu tanpa analisis dampak.
6. **Data import:** mulai dari dataset berlisensi atau impor yang penggunaannya diperbolehkan. Simpan provenance, versi dataset, waktu, mapping status, dan dedup fingerprint. Jangan mulai crawler sebelum sumber, terms, lisensi, dan akses dinilai.

## Pemetaan model konseptual ke persistensi

Spesifikasi mengusulkan kategori dan konfigurasi atribut/aspek/kriteria; produk dan varian; nilai spesifikasi; observasi harga; sumber; review; anotasi; prediksi review-aspek; versi model/taxonomy/dataset; pekerjaan analisis; agregat aspek; serta run dan item rekomendasi beserta evidence.

Ini **belum** skema siap-migrasi. Pemisahan tabel, constraint, indeks, dan migrasi baru dapat ditentukan setelah sumber data, pola query, skala pilot, dan pilihan database dikonfirmasi. Prediksi/agregat harus bisa ditelusuri ke review, model, taxonomy, dan versi data. Harga perlu menjadi observasi bertanggal, bukan satu field harga tetap pada produk.

## Penilaian solusi produk dan metode

Sentimen umum relevan, tetapi tidak cukup untuk memilih produk: satu review dapat memuji baterai sekaligus mengeluhkan koneksi. Arah yang lebih kuat adalah membangun bertahap:

1. katalog dan perbandingan identitas, spesifikasi, dan harga dengan sumber serta freshness;
2. review insight per aspek (misalnya suara, baterai, kenyamanan, konektivitas), dengan jumlah evidence dan contoh review yang dapat ditelusuri;
3. ranking SAW deterministik berdasarkan budget dan bobot preferensi, dengan kebijakan missing data, coverage, kontribusi kriteria, dan versi algoritma.

AI menstrukturkan bukti review; AI/LLM tidak menentukan ranking secara bebas. Rating, jumlah review, sentimen positif, atau score model bukan bukti objektif kualitas universal. Produk paling sesuai bergantung pada prioritas pengguna dan kualitas/kelengkapan data.

## Risiko dan batasan

- Belum ada dataset TWS terverifikasi, sumber harga/spesifikasi, izin review, atau data berlabel.
- Identitas model/varian dan pemetaan review dapat salah; mapping berkeyakinan rendah perlu ditandai atau ditinjau.
- Review seller/pengiriman harus dipisah dari kualitas produk.
- Label otomatis adalah pseudo-label, bukan ground truth evaluasi.
- Sampel kecil, bahasa campuran, duplikasi, ketidakseimbangan kelas, dan data usang bisa menghasilkan kesimpulan menyesatkan.
- SQLite masuk akal untuk dipertimbangkan bagi mode lokal satu pengguna, tetapi belum disetujui; backup/retensi juga belum ditentukan.
- Aplikasi tidak memiliki auth/admin role. Jangan menambah sistem akun tanpa kebutuhan nyata.
- Review, kutipan, harga, dan prediksi memerlukan aturan privasi, provenance, lisensi, freshness, dan retensi.

## Pertanyaan terbuka

1. Dataset TWS apa yang akan menjadi pilot, dari mana, serta apa lisensi/izin penggunaannya?
2. Apakah ada file produk/review lokal yang belum terlacak Git? Format dan jumlah record-nya apa?
3. Apakah target awal hanya penggunaan lokal pribadi atau perlu diakses pengguna lain?
4. Field spesifikasi/harga apa yang bisa diperoleh konsisten dan kapan data dianggap kedaluwarsa?
5. Apakah SQLite disetujui untuk persistensi lokal, dan apakah data harus bertahan saat aplikasi ditutup?
6. Siapa anotator pilot ABSA dan bagaimana test set independen disiapkan?
7. Kriteria, utility mapping, minimum evidence, dan evaluasi ranking apa yang akan dipakai setelah data diaudit?

## Status discovery

Audit ini tidak memasang dependency, melakukan scraping, mengubah schema, menyentuh fitur aplikasi existing, atau mengimplementasikan fitur baru. Lihat `PRODUCT_DECISION_ASSISTANT_INTEGRATION_PLAN.md` untuk mapping P0.
