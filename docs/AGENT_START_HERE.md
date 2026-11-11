# MyTools — Panduan agent

Project ini adalah aplikasi MyTools yang sudah berjalan. Fitur analisis keputusan merupakan modul `decision_support` di dalamnya, bukan aplikasi terpisah. Lihat `PRODUCT_DECISION_ASSISTANT_SPEC.md` untuk kebutuhan awal dan `PRODUCT_DECISION_ASSISTANT_INTEGRATION_PLAN.md` untuk struktur implementasi terkini.

Backend FastAPI dan UI Next.js dipisah di `apps/api` dan `apps/web`. Modul fitur berada di `apps/api/src/removebg/modules/decision_support` dan `apps/web/features/decision-support`. Pelatihan serta artefak model berada di `ml/`.

Jangan mengubah workflow media yang sudah ada ketika mengembangkan fitur analisis keputusan. Jangan mengklaim analisis AI aktif sebelum model terlatih pada dataset berlabel yang sesuai.
