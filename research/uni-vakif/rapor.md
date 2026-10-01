# Vakıf yükseköğretim kurumları haber kaynak haritası

Keşif tarihi: 2026-09-29 (UTC).

## Kapsam ve kaynak

[YÖK Vakıf Üniversiteleri](https://www.yok.gov.tr/tr/university?type=2) ve [YÖK Vakıf Meslek Yüksekokulları](https://www.yok.gov.tr/tr/university?type=3) kartlarından kurum adı, il ve resmî site adresi alındı. Eski `/universiteler/universitelerimiz` adresi 404 döndüğü için güncel dizin kullanıldı. MYO'lar istenen şemaya uygun olarak `vakif_universitesi` türü ve `vakıf MYO` notuyla kaydedildi.

Toplam **78 kurum**: **74 vakıf üniversitesi**, **4 bağımsız vakıf MYO**. Ana sitesi doğrulanan: **68/78**.

## Giriş noktaları

| Kanal | Kurum | Toplam içindeki oran |
|---|---:|---:|
| WordPress REST | 12 | %15.4 |
| RSS/Atom | 14 | %17.9 |
| Yalnız doğrulanmış HTML liste | 53 | %67.9 |
| JS render olasılığı (heuristik) | 1 | %1.3 |

Toplumsal katkı/topluma hizmet/sosyal sorumluluk/sürdürülebilirlik sayfası: **39/78**; bunların **8** tanesinde ayrı haber girişi doğrulandı. Kurumsal iletişim/basın sayfası: **20/78**. robots.txt kurallarıyla kısıtlı kaynak görülen kurum: **0**; robots durumu bilinmeyen kurum: **3**.

Bu kanallar örtüşebilir. `js_render_gerekli` alanı yalnızca hafif HTML keşfindeki olasılığı belirtir; tarayıcıyla doğrulanmış bir karar değildir. `null` doğrulanamayan bilgidir. Liste sayfaları HTTP 200, ilgili başlık ve çoklu bağlantıyla; feed ve API yanıtları içerik biçimiyle doğrulandı. Toplumsal katkı sayfası sayısına politika/proje sayfaları da dahildir; hepsi ayrı haber üreten birim değildir.

## Ortak kalıplar ve sorunlar

- Kurumların çoğunda haber, duyuru ve etkinlik ayrı HTML bağlantılarıdır; yalnız ana sayfa akışına güvenmek kapsama alanını azaltır.
- Toplumsal katkı ve sürdürülebilirlik sayfaları ayrı haber akışı içermeyebilir; bu durumda rektörlük akışı ve konu etiketleri izlenmelidir.
- Ana sayfa bağlantıları ile sınırlı sitemap incelemesi, menüde görünmeyen birimleri kaçırabilir; `null` yokluk kanıtı değildir.
- Fakülte bağlantısı düzeni yalnız doğrulanmış ana sayfa bağlantılarından özetlendi; bağlı fakülte sayfalarına gidilmedi. Bu nedenle `alt_alan_adi_yapisi` gözlemseldir, eksiksiz fakülte envanteri değildir.
- Ayrı toplumsal katkı/sürdürülebilirlik akışı doğrulanan öncelikli kurumlar: KAPADOKYA ÜNİVERSİTESİ, LOKMAN HEKİM ÜNİVERSİTESİ, NUH NACİ YAZGAN ÜNİVERSİTESİ, PİRİ REİS ÜNİVERSİTESİ, İSTANBUL AREL ÜNİVERSİTESİ, İSTANBUL NİŞANTAŞI ÜNİVERSİTESİ, İSTANBUL TOPKAPI ÜNİVERSİTESİ, İSTANBUL YENİ YÜZYIL ÜNİVERSİTESİ.
- Ana sitesi doğrulanamayan kurumlar (10): DEMİROĞLU BİLİM ÜNİVERSİTESİ, KOÇ ÜNİVERSİTESİ, OSTİM TEKNİK ÜNİVERSİTESİ, SANKO ÜNİVERSİTESİ, TÜRK HAVA KURUMU ÜNİVERSİTESİ, YAŞAR ÜNİVERSİTESİ, ÇAĞ ÜNİVERSİTESİ, İSTANBUL AYDIN ÜNİVERSİTESİ, İSTANBUL RUMELİ ÜNİVERSİTESİ, İSTANBUL TİCARET ÜNİVERSİTESİ.
- Canlı olduğu hâlde doğrulanmış haber girişi bulunmayan kurumlar (0): yok.

## Crawler'a ekleme sırası

1. Doğrulanmış WordPress REST akışlarını kullanın; kurum başına son kayıt tarihini saklayın.
2. RSS/Atom bulunan kurumları feed ETag/Last-Modified ile izleyin.
3. Doğrulanmış HTML haber, duyuru ve etkinlik listeleri için kuruma özgü seçici ve tarih ayrıştırıcı ekleyin.
4. Toplumsal katkı odaklı ayrı akışı olan birimleri ayrıca tarayın; diğerleri için rektörlük akışında konu sınıflandırması uygulayın.
5. Doğrulanmış giriş noktası bulunmayanları elle gözden geçirin; JS olasılığı olanlarda kontrollü tarayıcı keşfi yapın. robots.txt kısıtlarını tarama öncesi yeniden değerlendirin.

Keşifte Python 3.11.9 ve `AU-ToplumsalKatki-Recon/0.1 (+Ankara Universitesi Toplumsal Katki Koordinatorlugu)` kullanıcı aracısı kullanıldı. Aynı host için en az 2 saniye aralık ve en fazla 8 eşzamanlı istek uygulandı. İlk geçişte kurum başına 15 istek sınırı vardı; yeniden deneme ve kalite kontrol ek HTTP doğrulamaları gerektirdi.
