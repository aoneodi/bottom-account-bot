#!/bin/zsh
# Sekali jalan: siapkan bucket privat untuk arsip screenshot Bottom Account,
# beri bot izin TULIS, dan buat service account terpisah untuk sistem lain
# yang hanya perlu MEMBACA.
#
# Jalankan sebagai claudia.ong@ahacommerce.net (sudah aktif di gcloud).
# Ubah BUCKET kalau namanya sudah dipakai orang lain — nama bucket GCS
# harus unik secara global.

set -e
PROJECT="fbi-dev-484410"
BUCKET="aha-bottom-account-screenshots"
LOCATION="asia-southeast2"          # Jakarta
BOT_SA="bottom-ads-bot-shopee@${PROJECT}.iam.gserviceaccount.com"
READER_SA_NAME="bottom-account-reader"
READER_SA="${READER_SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

echo "==> 1/4 Membuat bucket privat gs://${BUCKET}"
# --public-access-prevention menutup kemungkinan bucket ini dibuat publik
# di kemudian hari; isinya ROAS dan pengeluaran iklan klien.
gcloud storage buckets create "gs://${BUCKET}" \
  --project="${PROJECT}" \
  --location="${LOCATION}" \
  --uniform-bucket-level-access \
  --public-access-prevention

echo "==> 2/4 Memberi bot izin tulis + baca"
# Tulis untuk mengunggah. Baca DIPERLUKAN karena bot membuat signed URL agar
# Google Slides bisa mengambil gambarnya saat penyisipan: signed URL hanya sah
# sejauh izin penandatangannya, jadi tanpa izin baca URL-nya akan ditolak.
# Tetap bukan objectAdmin — bot tidak boleh menghapus arsip.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${BOT_SA}" \
  --role="roles/storage.objectCreator"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${BOT_SA}" \
  --role="roles/storage.objectViewer"

echo "==> 3/4 Membuat service account khusus untuk sistem lain (hanya BACA)"
gcloud iam service-accounts create "${READER_SA_NAME}" \
  --project="${PROJECT}" \
  --display-name="Bottom Account screenshots reader" || echo "   (sudah ada, dilewati)"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${READER_SA}" \
  --role="roles/storage.objectViewer"

echo "==> 4/4 Membuat kunci untuk sistem lain"
gcloud iam service-accounts keys create "gcs-reader-key.json" \
  --iam-account="${READER_SA}"

echo
echo "SELESAI."
echo "  Bucket        : gs://${BUCKET}  (privat, public access dicegah)"
echo "  Bot menulis   : ${BOT_SA}"
echo "  Sistem lain   : ${READER_SA}  -> kuncinya di gcs-reader-key.json"
echo
echo "PENTING: gcs-reader-key.json adalah kunci privat. Serahkan lewat jalur"
echo "aman ke sistem yang membutuhkan, JANGAN commit ke git, lalu hapus dari"
echo "mesin ini setelah dipindahkan."
echo
echo "Lalu isi GCS_BUCKET di config.py dengan: ${BUCKET}"
