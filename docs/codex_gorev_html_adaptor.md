# Codex görevi: HTML liste sayfası adaptörünü üretim kalitesine getir

## Bağlam
Bu repo (`katki`) kurum sitelerindeki haberleri tarayıp toplumsal katkı açısından sınıflandırır. Önce README.md'yi ve `katki/discover.py`, `katki/crawl.py`, `katki/db.py`, `katki/cli.py` dosyalarını oku.
Şu an WordPress REST ve RSS adaptörleri iyi çalışıyor (~260 kaynak). Ama Türkiye haritalarında (`research/*/harita.json`) kurumların çoğunda yalnız **HTML liste sayfası** var (devlet üni. 75, vakıf üni. 53, STK 177 kurum). Mevcut `list` adaptörü (`crawl.py: _article_links` + `crawl_list`) basit bir sezgisel kural kullanıyor (menü/başlık/altbilgi at, slug'da ≥2 tire olan aynı-host linkler) ve detay sayfasından `trafilatura` ile metin çıkarıyor. Bu, çok sayıda sitede ya hiç link bulamaz ya da menü/kategori linklerini haber sanar.

## Hedef
HTML-only kaynakları güvenilir biçimde tarayabilmek: her liste sayfasından **gerçek haber detay linklerini** bul, detaydan **başlık + metin + yayın tarihi** çıkar.

## Yapılacaklar
1. **İçe aktarma:** `python -m katki harita-yukle` (bayraksız) zaten HTML-only kaynakları `list_urls` ile ekleyebiliyor; çalıştır ve sonucu doğrula (host tekrarları atlanır).
2. **Link kuralı öğrenme (keşif aşamasında, kaynak başına bir kez):**
   - Liste sayfasındaki aynı-host linkleri topla; haber linklerini ayırt eden bir **kural** çıkar (ör. ortak yol öneki `/haber/`, `/duyurular/detay/`, sayısal ID kalıbı, tekrar eden kart yapısı/CSS seçicisi). Önce deterministik yöntem dene (en sık tekrar eden yol kalıbı + liste içindeki tekrar eden DOM konteyneri).
   - Deterministik yöntem güvenilir değilse, link listesini (metin -> URL, en fazla 200) mevcut `katki.llm.chat_json` ile LLM'e ver ve bir **regex/yol kalıbı + örnek linkler** döndürt (pydantic şeması ile). LLM çağrısı kaynak başına **en fazla 1 kez**, sonuç veritabanında saklanır.
   - Kuralı `Source` üzerinde yeni bir JSON sütununda sakla (ör. `list_rules`: {liste_url: {"link_regex": ..., "css": ..., "ornek": [...]}}). `db.py`'deki mevcut sütun ekleme mekanizmasını kullan.
3. **Tarama:** `crawl_list` kuralı kullanarak linkleri seçsin; detayda `trafilatura.bare_extraction` ile başlık/metin/tarih; tarih yoksa sayfadaki `<time>`, `meta[property=article:published_time]`, Türkçe tarih formatları (ör. "29 Eylül 2026", "29.09.2026") için basit bir yedek ayrıştırıcı ekle. Metni 100 karakterden kısa olanları kaydetme.
4. **Mükerrer kontrolü:** Aynı kurumda (`Source.org`) son 60 gün içinde **normalize edilmiş başlığı aynı** olan bir kayıt varsa yenisini kaydetme (farklı birim sitelerinde aynı haber yayınlanıyor). Bu kontrolü tüm adaptörler için `crawl_all` içindeki kayıt aşamasına ekle.
5. **Ölçüm scripti:** `scripts/html_adaptor_testi.py` — verilen N HTML-only kaynakta keşif+tarama yapıp kaynak başına: bulunan link sayısı, çıkarılan kayıt, tarihli kayıt oranı, ortalama metin uzunluğu, LLM kullanıldı mı; ve genel başarı oranını yazdırsın.
6. **Test (KÜÇÜK ölçek, zorunlu):** Her haritadan ~10'ar olmak üzere **30 HTML-only kaynakta** `discover` + `crawl --limit 5` çalıştır ve ölçüm scriptinin çıktısını raporla. Tüm kaynakları TARAMA. `classify` ÇALIŞTIRMA (sınıflandırmayı ben yapacağım).

## Kurallar
- Çalıştırma: `C:\Users\User1\AppData\Local\hermes\bin\uv.exe run python -m katki ...` (erişim reddi alırsan önceki seferde yaptığın gibi mevcut `.venv` Python'unu kullan), `PYTHONIOENCODING=utf-8`.
- `classify.py`, `llm.py`, `jev.py`, `config.py`, `.env`, `static/*` DOSYALARINA DOKUNMA. git commit YAPMA.
- Siteleri yorma: mevcut `Fetcher` (host başına ≥2 sn, toplam 5 eşzamanlı) dışına çıkma; kaynak başına keşifte en fazla ~10 istek.
- Kod stili mevcut kodla aynı (Türkçe kısa yorumlar, tip ipuçları, gereksiz soyutlama yok).
- Başka bir süreç aynı anda `data/katki.db`'ye sınıflandırma yazıyor olabilir; SQLite kilit hatası alırsan kısa bekleyip tekrar dene.
- Son mesajında: değişen dosyalar, yeni sütun/komutlar, 30 kaynaklık test sonuçları (başarı oranı, tarihli kayıt oranı, LLM'e düşen kaynak sayısı), bilinen sorunlar.
