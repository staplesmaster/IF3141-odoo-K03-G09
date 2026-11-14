# KNR - Pengelolaan Pesanan Institusi

Addon Odoo 17 untuk mendukung proses PB-04 Pemesanan dan Pengiriman Catering/Snack Box institusi Kedai Nyonya Rumah.

## Fitur dan layar

1. **Daftar Pesanan / Form Pesanan** — nomor unik, klien, item, kuantitas, jadwal, alamat, jarak, catatan, total dan ongkos kirim.
2. **Detail & Riwayat Pesanan** — chatter, riwayat perubahan, riwayat kapasitas, status pemenuhan, dan catatan pengiriman.
3. **Konfirmasi Kapasitas** — Kepala Bakery dan Kepala Dapur Saji mencatat Sanggup/Tidak Sanggup beserta alasan. Status Kapasitas Dikonfirmasi hanya tercapai jika seluruh departemen yang dibutuhkan menyatakan sanggup.
4. **Kebutuhan Produksi per Tanggal** — filter tanggal dan departemen serta rincian produk/jumlah yang perlu dipenuhi.
5. **Jadwal Pengiriman per Tanggal** — daftar pesanan berdasarkan waktu layanan dan alamat tujuan.
6. **CRM & Peluang** — tahap Baru, Ditawarkan, Disepakati, Batal, catatan interaksi, nilai perkiraan, dan tindak lanjut.
7. **Master Data & Administrasi** — klien, produk/paket, ketentuan ongkos kirim, dan pengguna/hak akses.
8. **Rekap Pencocokan POS CSA** — menyimpan hasil pencocokan manual Sesuai/Selisih. Tidak ada integrasi atau pemrosesan pembayaran.

## Instalasi

Dari root repository:

```bash
docker compose up -d
docker compose run --rm web odoo -d odoo_app -i knr_order --stop-after-init
```

Kemudian buka Odoo, aktifkan Developer Mode bila perlu, lalu Apps → Update Apps List. Jika modul sudah terpasang dan kode diperbarui:

```bash
docker compose run --rm web odoo -d odoo_app -u knr_order --stop-after-init
```

Setelah itu masuk kembali ke Odoo. Grup **Kepala Administrasi** otomatis diberikan ke user admin saat modul diinstal; user lain ditetapkan melalui menu **Pengguna dan Hak Akses** → Users → tab Access Rights → kategori Kedai Nyonya Rumah.

## Pembuatan akun

Akun dibuat satu per satu melalui Odoo setelah modul KNR terpasang:

1. Login sebagai `admin`, lalu buka **Pengelolaan Pesanan KNR → Master Data & Administrasi → Pengguna dan Hak Akses**.
2. Buat pengguna, isi nama dan login/email, lalu pilih tipe **Internal User**.
3. Pada tab **Access Rights**, pilih grup di kategori **Kedai Nyonya Rumah** sesuai matriks role di bawah. Controller dan Petugas Pengganti memakai grup yang sama.
4. Simpan, lalu gunakan **Action → Change Password** untuk menetapkan password. Ulangi untuk akun berikutnya.

Jika akun Kepala Administrasi juga bertugas mengelola pengguna, berikan hak **Administration → Access Rights** bawaan Odoo melalui akun `admin`.

`.env` hanya mengatur koneksi PostgreSQL, nama database, dan port. Akun, password, dan data operasional diisi manual melalui Odoo.

## Matriks role

- Kepala Controller / Petugas Pengganti: membuat/mengubah/membatalkan pesanan, melihat klien dan riwayat, meminta konfirmasi kapasitas ulang.
- Kepala Administrasi: mengelola master data, tarif ongkir, akun/hak akses, dan pencocokan POS CSA.
- Kepala Cake Shop: melihat rincian dan kapasitas pesanan.
- Kepala Bakery / Kepala Dapur Saji: mengonfirmasi kapasitas departemennya dan memperbarui status produksi.
- Petugas Pengiriman: melihat jadwal, menandai Dikirim dan Selesai.
- Kepala Marketing: mengelola peluang dan meninjau riwayat klien.
- Pengguna Berwenang: dapat melakukan penyesuaian ongkos kirim manual dengan alasan.

## Konfigurasi awal

1. Buat data **Ketentuan Ongkos Kirim** dengan tarif per kilometer dan batas jarak gratis sesuai keputusan manajemen. Nilai tidak diisi otomatis karena dokumen kebutuhan tidak menetapkan angka tarif.
2. Masukkan data klien institusi dan produk/paket.
3. Pastikan setiap produk mempunyai bagian produksi penanggung jawab (Bakery atau Dapur Saji).
4. Buat akun Odoo untuk pegawai dan tetapkan grup sesuai matriks akses.
5. Buat pesanan dengan minimal satu baris produk.

## Catatan ruang lingkup

- Resep, data kepegawaian, inventaris, akuntansi, pembayaran dan optimasi rute tidak dibuat.
- Komunikasi pelanggan tetap dapat dilakukan melalui WhatsApp; pemberitahuan internal dicatat melalui chatter pesanan.
- Pembayaran tetap diperiksa manual di POS CSA. Modul hanya menyimpan hasil pencocokan.
- Nilai ongkos kirim manual memerlukan grup Kepala Administrasi atau Pengguna Berwenang dan alasan penyesuaian.
- Perubahan produk/jumlah/waktu setelah kapasitas dikonfirmasi mengembalikan pesanan ke Diterima dan meminta konfirmasi ulang.

## Pemetaan layar Milestone 4 ke use case

| Layar | Use case yang didukung |
|---|---|
| Daftar Pesanan | UC-03, UC-05, UC-06, UC-08, UC-12 |
| Form Pesanan | UC-03, UC-04, UC-05, UC-06 |
| Detail & Riwayat Pesanan | UC-05, UC-06, UC-08, UC-09, UC-12 |
| Konfirmasi Kapasitas | UC-07 |
| Daftar Produksi & Pengiriman | UC-10, UC-11 |
| CRM & Peluang | UC-13 |
| Master Data & Akses | UC-01, UC-02, UC-04, UC-14 |
| Rekap Pencocokan | UC-15 |

UC-08/UC-09 dan kebutuhan FR-08 juga didukung dari tampilan detail pesanan melalui statusbar, tombol proses, chatter, serta catatan konfirmasi. Pemberitahuan yang dibuat modul ini tampil sebagai pesan internal pada chatter pesanan.
