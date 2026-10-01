# Türkiye devlet üniversiteleri haber kaynak haritası

**Tarih:** 2026-09-29. **Kapsam:** 129 devlet üniversitesi; Ankara Üniversitesi dâhil, fakat ayrıca tarandığı için ayrıntılı keşif dışında tutuldu.

## Liste ve doğrulama

Kurum adı, il ve başlangıç alan adları [Eylül 2026 tarihli 129 üniversitelik listeden](https://www.turkedebiyati.org/universiteler/) alındı. Kaynak liste [YÖK yükseköğretim istatistiklerini](https://istatistik.yok.gov.tr/) ve YÖK üniversite dizinini dayanak gösteriyor; [YÖK'ün 2025 değerlendirme raporu](https://veriyonetim.yok.gov.tr/documentFiles/1766133304915.2025-universite-izleme-ve-degerlendirme-genel-raporu.pdf) da 129 devlet üniversitesi sayısını bildiriyor. İstenen [YÖK dizini](https://www.yok.gov.tr/universiteler/universitelerimiz) keşif tarihinde HTTP 404 verdi; bu nedenle doğrudan YÖK dizininden otomatik liste çekilemedi. Kurum adları ayrıca [e-Devlet üniversite hizmet listesi](https://www.turkiye.gov.tr/universite-hizmet-listesi) ile karşılaştırıldı: 129/129 bire bir metin eşleşmesi.
e-Devlet karşılaştırması kurum türünü tek başına doğrulamaz.

## Sonuçlar

| Ölçü | Kurum | Pay |
|---|---:|---:|
| Canlı ana site | 120/129 | 93,0% |
| WordPress REST doğrulandı | 8/128 | 6,3% |
| RSS/Atom doğrulandı | 10/128 | 7,8% |
| HTML haber/duyuru/etkinlik listesi doğrulandı | 86/128 | 67,2% |
| Yalnız HTML listesi (WP/RSS yok) | 75/128 | 58,6% |
| JS render işareti | 10/128 | 7,8% |
| Ayrı toplumsal katkı/sosyal sorumluluk/sürdürülebilirlik sayfası | 34/128 | 26,6% |
| Bunlardan farklı hostta olan | 26/34 | 76,5% |
| Kurumsal iletişim/basın sayfası | 39/128 | 30,5% |

Paydalar, “canlı ana site” satırında tüm 129 kurumu; diğer genel oranlarda Ankara Üniversitesi dışındaki 128 kurumu gösterir. WP REST ve RSS oranları birlikte görülebilir. JS render işareti, sayfanın gerçekten tarayıcıda çalıştırılması gerektiğinin kesin testi değildir.

## Gözlenen kalıplar ve sınırlar

- Canlı olduğu hâlde doğrulanmış haber/duyuru/etkinlik listesi, RSS veya WP REST bulunmayan 33 kurum var. Ana sayfası doğrulanamayan 9 kurum: Afyonkarahisar Sağlık Bilimleri Üniversitesi; Bitlis Eren Üniversitesi; Düzce Üniversitesi; İnönü Üniversitesi; İzmir Kâtip Çelebi Üniversitesi; Ordu Üniversitesi; Osmaniye Korkut Ata Üniversitesi; Türk-Japon Bilim ve Teknoloji Üniversitesi; Van Yüzüncü Yıl Üniversitesi. Bunlar kurumun gerçekten çevrimdışı olduğu anlamına gelmez; TLS, geçici sunucu hatası veya ağ erişimi de neden olabilir.
- Ana hostta robots.txt sonucu doğrulanamayan 37 kurum var. Alan `robots_kisitli: null` olarak bırakıldı. Erişilen robots.txt kuralları ilgili URL yolu için değerlendirildi; bilinmeyen yerlerde tarayıcı üretim öncesi tekrar kontrol etmeli.
- Üniversiteler haber, duyuru ve etkinlikleri çoğunlukla ayrı HTML listelerinde sunuyor. Toplumsal katkı ve sürdürülebilirlik birimleri sıkça ayrı alt alan adında; fakülte siteleri kapsam dışı bırakıldı ve yalnızca yapı gözlemi yazıldı.
- Bu çalışma ana sayfada görünen bağlantılarla sınırlı hafif keşiftir. Menüde bulunmayan alt birimler, arşiv sayfaları ve JavaScript ile sonradan yüklenen kaynaklar kaçmış olabilir. `null`, yokluk kanıtı değil, doğrulanamama anlamına gelir.
- Her doğrulanmış giriş URL’si HTTP 200 ve içerik türü/gövde kontrolünden geçti. Yalnız birim sayfası doğrulanan ama haber listesi bulunmayan kaynaklarda liste alanları `null` bırakıldı. `wp_rest: true` için geçerli yazı dizisi, `rss_url` için RSS/Atom öğesi arandı.

## Crawler’a ekleme sırası

1. Toplumsal katkı, topluma hizmet, sosyal sorumluluk ve sürdürülebilirlik birimlerinin doğrulanmış haber/duyuru/etkinlik listelerini öncelikli kaynak yapın; aynı hosttaki ana rektörlük listesinden gelen mükerrer içerikleri kanonik URL ile tekilleştirin.
2. `wp_rest: true` kaynaklarında `/wp-json/wp/v2/posts` uç noktasını; sonra doğrulanmış RSS/Atom bağlantılarını kullanın. Tarih ve içerik kimliğiyle artımlı çekim yapın; ETag/Last-Modified başlıklarını değerlendirin.
3. Doğrulanmış HTML listeleri için kurum bazlı seçiciler ve sayfalama ekleyin. `haber_url`, `duyuru_url`, `etkinlik_url` ayrı akışlar olsun; günde üç kez yapılan taramada kaynak başına son görülen URL/tarih tutun.
4. JS render işaretli ve canlı olup kaynak bulunamayan kurumları manuel inceleyin. Üretim taramasında her hostun robots.txt kuralını yeniden okuyun; host başına en fazla bir istek/2 saniye ve toplam en fazla 8 eşzamanlı istek sınırını koruyun.

## Yöntem ve veri dosyası

`harita.json` şema alanlarını kurum bazında içerir. Keşif betiği `kesif.js`, kaldığı yerden devam etmek için `ilerleme.json` kullanır; User-Agent `AU-ToplumsalKatki-Recon/0.1 (+Ankara Universitesi Toplumsal Katki Koordinatorlugu)` ve kurum başına en çok 15 üst düzey istek uygular. Yönlendirmeler ayrıca istek oluşturabilir. Ortamda istenen Python 3.11 çalıştırıcısı yürütülemediğinden keşif Node.js ile yürütüldü; bu yalnızca keşif aracını etkiler, JSON veri biçimini etkilemez.
