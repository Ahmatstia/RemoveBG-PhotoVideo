# RemoveBG Local

Tool lokal Windows untuk menghapus latar video (prioritas) dan foto. Ditargetkan untuk RTX 3050 Laptop 6 GB; input video SDR hingga 1920×1080 / 1080×1920 dan 15 menit. Tidak memerlukan akun atau layanan cloud.

## Menjalankan

1. Instal Python 3.11, [uv](https://docs.astral.sh/uv/getting-started/installation/), dan driver NVIDIA yang mendukung CUDA 12.8.
2. Buka PowerShell di folder proyek, lalu jalankan `./setup.ps1` sekali. PyTorch CUDA mengunduh beberapa GB.
3. Klik dua kali `run.bat` atau jalankan `./run.ps1`. Browser membuka alamat lokal yang ditampilkan terminal (biasanya http://127.0.0.1:7860).
4. Pilih video, pilih jenis subjek, lalu **Uji 5 detik pertama**. Jika hasil sesuai, jalankan **Proses video lengkap**.

Model diunduh dari repositori resmi pada pemakaian pertama dan disimpan di `models/`. Setelah model tersimpan, pemrosesan bisa dijalankan tanpa internet. Gradio tidak menggunakan share link; analytics Gradio dan telemetry Hugging Face dinonaktifkan.

`requirements-lock.txt` merekam versi yang diuji. Bobot model di-cache selama aplikasi hidup; recurrent state dan sesi tracking selalu baru untuk setiap file. Pemakaian pertama RVM membutuhkan warm-up TorchScript, sehingga klip pendek pertama dapat terasa jauh lebih lambat.

### Pilihan model

- **Manusia:** RVM MobileNetV3, TorchScript FP16 pada CUDA. Memakai recurrent states antarfame, menghasilkan foreground beserta alpha matte. Mode Detail menaikkan resolusi tahap coarse untuk full-body; bukan jaminan selalu lebih baik daripada Cepat.
- **Objek umum:** SAM 2.1 Hiera Small melalui Transformers, BF16 autocast. Klik titik hijau di objek pada frame pertama, titik merah di latar yang perlu dikecualikan. Semua titik merupakan prompt untuk satu objek. Riwayat tracking dibatasi sesuai jendela memori model, sementara frame referensi pertama dipertahankan.
- Foto memakai model yang sama: otomatis untuk manusia atau pilihan titik untuk objek umum. Output PNG RGBA, maksimal 3840×2160 / 2160×3840.

SAM merupakan segmentasi, bukan matting transparansi fisik: mask dipisahkan pada ambang nol dan hanya tepinya diperhalus 0,6 piksel agar objek solid tetap opak. Ini bukan rekonstruksi rambut/kaca. RVM tidak dijamin mempertahankan benda yang dipegang. Pilih mode sesuai subjek; objek yang keluar frame, tertutup lama, atau scene cut dapat membuat tracking meleset. Gunakan satu shot kontinu per pekerjaan, lalu periksa hasil sebelum dipakai.

### Ekspor

- **MOV ProRes 4444:** alpha transparan dengan audio (jika ada); resolusi sumber. Cocok untuk editor yang mendukung ProRes alpha. Bukan lossless; file 1080p berdurasi panjang dapat berukuran puluhan GB. Audio diubah ke PCM untuk kompatibilitas MOV.
- **MKV FFV1 mask:** alpha grayscale lossless dengan audio sumber (PCM). Putih = subjek, hitam = latar. Pasang sebagai luma matte di atas video sumber dalam editor. Ini mempertahankan video asli sebagai bahan compositing, tanpa re-encode warna sumber.
- **Preview MP4:** hanya lima detik pertama, resolusi ringan, pola kotak, dengan audio AAC dari 5 detik yang sama. Bukan file transparan final.
- **PNG:** hasil foto dengan kanal alpha.

Input tidak pernah ditimpa. Output berada di `data/outputs/<job-id>/`, beserta `report.json` (durasi, frame, waktu total, FPS pipeline). Hasil foto disimpan sebagai file PNG dengan ID unik. Log aplikasi: `data/app.log`. Upload sementara dikelola Gradio di folder temp sistem; output dipertahankan sampai pengguna menghapusnya.

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
