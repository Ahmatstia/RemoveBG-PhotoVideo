# RemoveBG Local

Tool Windows lokal untuk menghapus latar video/foto, membuat transkrip multilingual dari YouTube, dan mengunduh video YouTube. Pemrosesan AI berjalan di PC tanpa layanan transkripsi cloud. Fitur YouTube dan unduhan model pertama kali memerlukan internet. Penghapusan latar ditargetkan untuk RTX 3050 Laptop 6 GB; input video SDR hingga 1920×1080 / 1080×1920 dan 15 menit.

## Menjalankan

1. Instal Python 3.11, [uv](https://docs.astral.sh/uv/getting-started/installation/), [Node.js 22+](https://nodejs.org/), dan driver NVIDIA yang mendukung CUDA 12.8.
2. Buka PowerShell di folder proyek, lalu jalankan `./setup.ps1` sekali. PyTorch CUDA mengunduh beberapa GB.
3. Klik dua kali `run.bat` atau jalankan `./run.ps1`. Browser membuka alamat lokal yang ditampilkan terminal (biasanya http://127.0.0.1:7860).
4. Pilih tab **Video** atau **Foto** untuk menghapus latar. Tab **Transkrip YouTube** menghasilkan TXT, SRT, VTT, dan JSON kata beserta timestamp. Tab **Downloader** mendukung YouTube, Instagram, TikTok, dan Twitter/X.

Model diunduh dari repositori resmi pada pemakaian pertama dan disimpan di `models/`. Setelah model tersimpan, penghapusan latar dan transkripsi file lokal bisa dijalankan tanpa internet; mengambil konten dari YouTube tetap memerlukan internet. Gradio tidak menggunakan share link; analytics Gradio dan telemetry Hugging Face dinonaktifkan.

### Transkrip dan unduhan YouTube

- Tempel URL satu video YouTube pada tab **Transkrip YouTube**. Audio diambil sementara, dikonversi ke WAV 16 kHz, lalu dianalisis di PC menggunakan Whisper large-v3. Tidak ada file video yang disimpan oleh alur transkrip.
- Model Whisper large-v3 multilingual mendukung 99 bahasa, termasuk Arab, dan bahasa dapat dideteksi otomatis. Cari lalu pilih bahasa di dropdown bila sudah diketahui; decoding memakai beam search untuk membantu mengurangi kesalahan pengenalan, dengan waktu proses lebih lama.
- Transkripsi panjang diproses berurutan agar konteks antarbagiannya tetap terjaga. Ini mengutamakan ketepatan dibanding mode potongan cepat.
- TXT berisi teks, SRT/VTT berisi timestamp kalimat, dan JSON menyimpan timestamp awal/akhir setiap kata serta kelompok kalimat. Timestamp kata merupakan estimasi alignment model; audio bising, ucapan tumpang tindih, aksen, dan kata yang salah dikenali dapat memengaruhi hasil.
- Tab **Downloader** adalah fitur terpisah dari transkrip. Pilih platform, tempel tautan satu video, lalu pilih kualitas Terbaik, 1080p, atau 720p. Hasil ditampilkan di aplikasi dan tetap sementara sampai disimpan melalui tombol unduh.
- Downloader memakai yt-dlp. YouTube membutuhkan Node.js 22+ untuk menjalankan challenge solver. Tautan privat, konten yang dibatasi wilayah/umur, atau situs yang meminta login mungkin gagal; dukungan platform bergantung pada perubahan situs dan extractor yt-dlp.
- Model Whisper large-v3 berukuran beberapa GB dan diunduh saat fitur transkrip pertama kali dipakai. Model ini lebih mengutamakan akurasi daripada kecepatan; waktu proses bergantung pada panjang video dan GPU.

`requirements-lock.txt` mengunci versi dependensi. Bobot model di-cache selama aplikasi hidup; recurrent state dan sesi tracking selalu baru untuk setiap file. Pemakaian pertama RVM membutuhkan warm-up TorchScript, sehingga klip pendek pertama dapat terasa jauh lebih lambat.

### Pilihan model

- **Manusia:** RVM MobileNetV3, TorchScript FP16 pada CUDA. Memakai recurrent states antarfame, menghasilkan foreground beserta alpha matte. Mode Detail menaikkan resolusi tahap coarse untuk full-body; bukan jaminan selalu lebih baik daripada Cepat.
- **Objek umum:** SAM 2.1 Hiera Small melalui Transformers, BF16 autocast. Klik titik hijau di objek pada frame pertama, titik merah di latar yang perlu dikecualikan. Semua titik merupakan prompt untuk satu objek. Riwayat tracking dibatasi sesuai jendela memori model, sementara frame referensi pertama dipertahankan.
- Foto memakai model yang sama: otomatis untuk manusia atau pilihan titik untuk objek umum. Output PNG RGBA, maksimal 3840×2160 / 2160×3840.

SAM merupakan segmentasi, bukan matting transparansi fisik: mask dipisahkan pada ambang nol dan hanya tepinya diperhalus 0,6 piksel agar objek solid tetap opak. Ini bukan rekonstruksi rambut/kaca. RVM tidak dijamin mempertahankan benda yang dipegang. Pilih mode sesuai subjek; objek yang keluar frame, tertutup lama, atau scene cut dapat membuat tracking meleset. Gunakan satu shot kontinu per pekerjaan, lalu periksa hasil sebelum dipakai.

### Ekspor

- **MP4 Layar Hijau (Chroma Key):** video H.264/AAC standar dengan latar belakang hijau murni (`#00FF00`). Sangat ringan (~2–5 MB), bisa langsung diputar di semua pemutar Windows/Mac/HP, dan siap pakai di CapCut, Premiere, Canva, dll. dengan 1 klik Chroma Key.
- **MOV ProRes 4444:** alpha transparan asli dengan audio PCM; resolusi sumber. Cocok untuk editor profesional (Premiere, DaVinci, After Effects) yang mendukung ProRes alpha. File berukuran besar (~100 MB per 20 detik).
- **MP4 Layar Hitam:** video H.264/AAC standar dengan latar belakang hitam solid.
- **MKV FFV1 mask:** alpha grayscale lossless dengan audio sumber (PCM). Putih = subjek, hitam = latar. Pasang sebagai luma matte di atas video sumber dalam editor.
- **Preview MP4:** hanya lima detik pertama, resolusi ringan, pola kotak, dengan audio AAC dari 5 detik yang sama.
- **PNG:** hasil foto dengan kanal alpha transparan.

Input tidak pernah ditimpa. Hasil foto, video, transkrip, dan unduhan YouTube ditampilkan di aplikasi dan disimpan sementara di folder temp Windows agar bisa dipratinjau atau diunduh. Hasil tidak disalin ke Downloads kecuali pengguna menekan tombol Unduh. Cache dibersihkan saat aplikasi ditutup normal atau saat dijalankan kembali. Log aplikasi: `data/app.log`. Upload sementara dikelola Gradio di folder temp sistem.

Pipeline membaca frame berurutan, mempertahankan timestamp termasuk VFR, menangani rotasi 90°, dan tidak menampung semua frame di memori. Video HDR ditolak agar tidak terjadi perubahan warna tanpa pemberitahuan. Input/output AI memakai RGB/alpha 8-bit; ekspor ProRes 10-bit tidak menciptakan kembali detail 10-bit yang hilang. Tidak ada klaim hasil identik dengan sumber atau garansi real-time.

Tombol Batalkan berhenti setelah operasi frame/model aktif selesai. Unduhan model awal belum dapat diputus lewat tombol ini. Jika disk hampir penuh atau proses gagal, file parsial pekerjaan tersebut dibersihkan.

## Struktur layer

```text
src/removebg/
  ui/app.py                  # Gradio, input, titik pilihan, progress, pembatalan
  ui/theme.py                # Tema merah-ember gelap dan CSS (hanya font sistem, tetap offline)
  application/service.py     # Urutan proses video/foto, lifecycle job dan hasil
  infrastructure/models.py   # Adapter RVM/SAM, CUDA, download/cache dan memori
  infrastructure/media.py    # PyAV decode/encode, FFmpeg audio, preview
  infrastructure/youtube_transcription.py # Audio YouTube sementara untuk transkripsi
  infrastructure/youtube_video.py # Pengunduh video YouTube, Instagram, TikTok, dan Twitter/X
  infrastructure/youtube_common.py # Validasi tautan YouTube
  application/transcription.py # Whisper multilingual, kata dan timestamp, ekspor
  application/youtube_download.py # Alur unduh video dan penyimpanan hasil sementara
  domain.py                  # Metadata video dan validasi titik
  config.py                  # Lokasi output/model
tests/test_pipeline.py       # Kontrak ekspor, timestamp, cleanup, audio, mask
setup.ps1 / run.ps1 / run.bat
```

UI tidak melakukan inference langsung. Untuk model tambahan, buat adapter dengan `process(rgb) -> (foreground_rgb, alpha_uint8)` lalu sambungkan melalui `create_model`. Model harus menyimpan state temporal di instance sendiri. Satu pekerjaan GPU diproses pada satu waktu. Tidak ada database, server eksternal, atau framework frontend tambahan.

## Verifikasi

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m compileall -q src
```

Tes pipeline menggunakan matte sintetis untuk memverifikasi codec alpha, mask lossless, timestamp VFR, audio, batas preview, rotasi, validasi pilihan, dan cleanup. Ini terpisah dari penilaian kualitas AI pada footage asli.

Untuk pemeriksaan GPU nyata, unduh [sampel astronaut scikit-image](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/astronaut.png) ke `data/samples/astronaut.png`, lalu jalankan `.venv/Scripts/python.exe scripts/smoke_gpu.py`. Script menguji dua model, batas riwayat SAM, dan ekspor klip 1080p sintetis satu detik. Hasil di `data/samples/smoke-report.json`; angka ini bukan benchmark footage bergerak atau uji 15 menit. Contoh astronaut berasal dari NASA melalui scikit-image.

## Sumber dan lisensi model

- [RVM](https://github.com/PeterL1n/RobustVideoMatting), GPL-3.0; [inference](https://github.com/PeterL1n/RobustVideoMatting/blob/master/documentation/inference.md).
- [SAM 2](https://github.com/facebookresearch/sam2), kode/model utama Apache-2.0; [streaming Transformers](https://huggingface.co/docs/transformers/model_doc/sam2_video).
- [FFmpeg codecs](https://ffmpeg.org/ffmpeg-codecs.html); FFmpeg yang disertakan imageio-ffmpeg memiliki ketentuan lisensi build tersendiri.

Model diunduh sebagai dependensi eksternal, bukan kode buatan proyek ini. Periksa kewajiban lisensinya sebelum mendistribusikan aplikasi. MatAnyone/VideoMaMa tidak dibundel karena batasan penggunaan dan kebutuhan integrasi berbeda.
