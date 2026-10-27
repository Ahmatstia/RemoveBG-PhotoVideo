# Verifikasi lokal — 27 Oktober 2026

Perangkat: NVIDIA GeForce RTX 3050 Laptop, VRAM 6144 MiB; Windows, Python 3.11.9, PyTorch 2.11.0+cu128. Versi dependensi lengkap tercatat di requirements-lock.txt.

- 11 tes pytest lulus: alpha ProRes, mask lossless, timestamp VFR, pembatalan, cleanup kegagalan, PNG RGBA, batas riwayat tracking, validasi titik, checkerboard, audio/preview, rotasi, dan penamaan file kustom/sanitasi.
- Ruff lulus; modul dapat dikompilasi dan konfigurasi UI dapat dibangun.
- Inferensi nyata RVM dan SAM 2 Small dijalankan pada CUDA, masing-masing 24 frame foto astronaut berulang. Riwayat SAM diverifikasi tidak melebihi 16 frame tracking + frame conditioning; hanya satu input frame disimpan.
- Video manusia sintetis 1920×1080, 30 frame / satu detik berhasil diekspor ke ProRes 4444. Alur upload, proses, preview dan link unduh diperiksa melalui browser. Uji UI pertama memerlukan 16,6 detik; uji kedua 9,4 detik. Ini termasuk overhead dan preview, bukan klaim throughput real-time. Pekerjaan pengujian lain juga sempat berjalan di perangkat yang sama.
- Foto kendaraan SAM: alpha latar dan piksel subjek diuji 0 dan 255 setelah perbaikan kontur; preview diperiksa secara visual. Beberapa detail tipis dan lubang di bagian roda tetap dapat memerlukan prompt tambahan.
- Video kendaraan dengan translasi sintetis 640×426, 12 frame berhasil diproses melalui SAM dan diekspor menjadi mask FFV1. Jumlah frame serta titik latar/subjek pada frame terakhir diverifikasi.
- Footage pengguna (testing/video.mp4, 576×1024, 20,8 detik, AAC): mode Manusia, ekspor MOV penuh 624 frame dalam 85,9 detik (7,3 fps pipeline), menghasilkan ProRes + audio PCM berdurasi sama. Ekspor mask MKV dan preview 5 detik juga memuat audio (PCM / AAC). Foto manusia.png menghasilkan PNG RGBA 1254×1254 dengan alpha 0–255. Kualitas tepi belum dinilai secara visual; objekLogo.png belum diuji karena memerlukan titik pilihan manual.

Artefak pengujian ada di data/samples dan data/outputs (diabaikan Git). Bukti UI: data/ui-verified.png. Sampel astronaut berasal dari NASA melalui scikit-image; gambar kendaraan dari https://github.com/facebookresearch/segment-anything/blob/main/notebooks/images/truck.jpg.

Belum diuji: footage pengguna, klip penuh 15 menit, stress test disk penuh, kompatibilitas editor pengguna, motion blur berat, scene cut, dan kualitas transparansi objek kaca. Batas input 15 menit sudah diterapkan; ini bukan bukti bahwa seluruh variasi klip 15 menit telah diuji. Video HDR ditolak dengan pesan jelas, bukan dikonversi diam-diam.
