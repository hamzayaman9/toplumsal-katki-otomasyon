# Codex görevi: Türkiye geneli kaynak haritalarını tarayıcıya entegre et

## Proje bağlamı
Bu repo (`katki` Python paketi) Ankara Üniversitesi Toplumsal Katkı Koordinatörlüğü için bir haber tarama + sınıflandırma sistemidir. Önce README.md'yi ve `katki/` altındaki modülleri oku:
- `db.py` (SQLAlchemy modelleri: Source, Article, Classification, CrawlRun; `init_db()` eksik sütunları ALTER TABLE ile ekler)
- `discover.py` (her Source için yöntem: WordPress REST > RSS > liste sayfası > LLM ile liste bulma; Angular site ise `none` ya da `ubys_cms`)
- `crawl.py` (adaptörler + `crawl_all`, canlı olay yayını `on_event`)
- `classify.py`, `llm.py` (OpenRouter sınıflandırma — BUNLARA DOKUNMA)
- `web.py` + `static/index.html` (panel) + `static/canli.html` (canlı animasyon)
- `cli.py` (`python -m katki <komut>`)
Şu an veritabanında (`data/katki.db`, SQLite) sadece Ankara Üniversitesi'nin 114 kaynağı ve ~1.826 kayıt var. Mevcut akış BOZULMAMALI.

Yeni veri: `research/uni-devlet/harita.json` (129 devlet üni.), `research/uni-vakif/harita.json` (78 vakıf üni./MYO), `research/stk/harita.json` (505 STK/vakıf/dernek/kamu kurumu). Her kurum objesinde `kurum`, `kurum_turu`, `il`, `ana_site`, `canli`, `kaynaklar[]` (her biri `birim`, `host`, `haber_url`, `duyuru_url`, `etkinlik_url`, `rss_url`, `wp_rest`, `cms`, `js_render_gerekli`, `toplumsal_katki_odakli` ...) var. Önce dosyaların gerçek yapısını incele; alan adları küçük farklılıklar gösterebilir.

## Yapılacaklar
1. **Şema:** `Source` modeline `org_type` (kurum_turu), `city` (il) ve `focus` (toplumsal_katki_odakli: bool) sütunlarını ekle. Mevcut `org` alanı kurum adıdır (Ankara kaynaklarında "Ankara Üniversitesi"). Mevcut Ankara kaynakları için `org_type="devlet_universitesi"`, `city="Ankara"` olarak doldur.
2. **İçe aktarma komutu:** `python -m katki harita-yukle [--dosya ...] [--sadece-kolay]`
   - Her kurumun her kaynağı için bir Source oluştur (host benzersiz; aynı host varsa atla/güncelle). `*.ankara.edu.tr` hostlarını ATLA (zaten var).
   - `name` = birim adı (yoksa kurum kısa adı), `org` = kurum adı, `org_type`, `city`, `focus`, `feed_url` = rss_url, `list_urls` = {haber, duyuru, etkinlik} (null olmayanlar), `active` = canli.
   - `--sadece-kolay`: yalnızca `wp_rest` true veya `rss_url` dolu kaynakları al.
   - Özet yazdır: kurum türüne göre kaç kaynak eklendi/atlandı.
3. **Keşif:** `discover` mevcut haliyle yeni kaynaklarda çalışmalı. Harita `list_urls` verdiyse keşif onları korumalı (şu an recon JSON'u sadece Ankara dosyasından okunuyor; `cmd_discover` içindeki `load_recon()` mantığını, veritabanındaki `list_urls`'i de kullanacak şekilde genelleştir). `js_render_gerekli` olanları `none` bırak ve not düş.
4. **Panel:** `web.py` API'lerine (`/api/ozet`, `/api/kayitlar`, `/api/birimler`) `org_type` ve `org` filtreleri ekle; `/api/kurumlar` uç noktası ekle. `index.html`'de filtre satırına "Kurum türü" ve "Kurum" seçicileri ekle (mevcut stil/tokenlarla), başlıktaki "Ankara Üniversitesi" alt yazısını seçime göre güncelle. "En çok katkı üreten birimler" grafiğinde birim adını "Kurum · birim" göster. Tabloya kurum bilgisini ekle.
5. **Canlı sayfa:** `canli.html` kaynak ızgarası ~500-900 kareyi taşıyabilmeli (kare boyutunu kaynak sayısına göre küçült; kaynakları kurum türüne göre gruplayıp küçük başlıklarla göster).
6. **Test (KÜÇÜK ölçek, zorunlu kurallar):**
   - `harita-yukle --sadece-kolay` çalıştır.
   - Yeni kaynaklardan sadece **15 tanesinde** (her kurum türünden birkaç) `discover` ve `crawl --limit 5` çalıştır (`--host` ile). TÜM kaynakları tarama.
   - `classify --limit 20` ile en fazla 20 kayıt sınıflandır (LLM maliyeti var; daha fazlasını çalıştırma).
   - Paneli **8010** portunda başlatıp (`python -m katki web --port 8010`; 8000 portu kullanımda) API'lerin yeni filtrelerle çalıştığını HTTP istekleriyle doğrula, sonra sunucuyu kapat.
7. README'ye yeni komutu ve alanları kısaca ekle.

## Kurallar
- Çalıştırma: `C:\Users\User1\AppData\Local\hermes\bin\uv.exe run python -m katki ...` ; `PYTHONIOENCODING=utf-8` ayarla.
- Kod stili: mevcut kodla aynı (Türkçe kısa yorumlar, tip ipuçları, gereksiz soyutlama yok).
- `classify.py`, `llm.py`, `.env` DOSYALARINA DOKUNMA. git commit YAPMA. `data/katki.db` dışında veri dosyası silme.
- Siteleri yorma: mevcut `Fetcher` ayarları (host başına ≥2 sn) dışına çıkma.
- Son mesajında: değişen dosyalar, yeni komutlar, test sonuçları (kaç kaynak eklendi, 15 kaynağın keşif sonucu, kaç kayıt geldi, kaç sınıflandırıldı), bilinen sorunlar.
