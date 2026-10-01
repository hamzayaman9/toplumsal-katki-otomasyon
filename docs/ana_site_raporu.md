# Ankara Üniversitesi ana site: headless okuma denemesi

**Deneme tarihi:** 29 Eylül 2026. Playwright 1.63.0 ve headless Chromium ile, varsayılan User-Agent kullanılarak dokuz normal sayfa ziyareti yapıldı. Üretim crawler'ı yazılmadı. API'ye tarayıcı dışından istek gönderilmedi; yalnızca `page.on("response")` ile tarayıcının kendiliğinden aldığı yanıtların URL'si ve JSON yapısı gözlendi. Sayfa ziyaretlerinin başlangıcı arasında en az 2,2 saniye bırakıldı.

## Sonuç ve örnek kayıtlar

**Evet, render sonrasında veriler DOM'dan okunabiliyor.** Ham HTML Angular kabuğu olsa da üç kategori listesinin ilk iki sayfasında 20'şer kart bulundu. Başlık, bağlantı ve görünen tarih toplam 120 karttan alındı. İlk üç haber detayında başlık, yayın tarihi ve gövde metni çıkarıldı. Tüm kayıtlar `ornek_haberler.json` dosyasında kategori ve sayfa altında yer alıyor. `metin_ilk_300` yalnızca açılan üç haber detayında dolu; liste üzerinden görülen diğer kayıtlarda `null`.

| Sayfa | DOM kaydı | İlk kaydın başlığı | İlk kaydın tarihi |
| --- | ---: | --- | --- |
| Haberler 1 | 20 | Ankara Üniversitesinde "COP 31 Öncesinde İklim Dezenformasyonu" Paneli | 26 Eylül 2026 |
| Haberler 2 | 20 | Ankara Üniversitesi Yönetimi ile Suriye Yükseköğretim Heyeti Arasında İstişare Toplantısı | 07 Ağustos 2026 |
| Duyurular 1 | 20 | 2547–Arnavutluk Bilimsel Araştırma ve İnovasyon Ulusal Ajansı (NASRI) ile İkili İşbirliği Programı Başvuru Sonuçları Açıklandı | 29 Eylül 2026 |
| Duyurular 2 | 20 | Ankara Üniversitesi Sağlık Bilimleri Fakültesi Doçentlik Sözlü Sınav Duyurusu | 15 Eylül 2026 |
| Etkinlikler 1 | 20 | Elektronik Belgelerin Geleceği ve Geleceğin Belgeleri | 25 Eylül 2026 |
| Etkinlikler 2 | 20 | Ankara Üniversitesi Sağlık Bilimleri Fakültesi "Mezuniyetten Mesleğe: Sağlıkta Kariyerin Yol Haritası" Etkinliği | 06 Mayıs 2026 |

Etkinliklerde `tarih`, kartta görüntülenen etkinlik tarihidir; API'deki `publishDate` ile aynı anlama geldiği varsayılmamalıdır. Üç haber detayının gövde uzunluğu, boşluklar normalize edildikten sonra sırasıyla 6.289, 4.547 ve 10.896 karakterdi.

## Çalışan DOM seçicileri

| Alan | Seçici / işlem |
| --- | --- |
| Üç kategori listesinde başlık ve bağlantı | `.post-title a.site-text-secondry` → `inner_text()` ve `href` |
| Kartın görünen tarihi | Başlık bağlantısının en yakın `.wt-post-info` kartındaki `.wt-post-readmore` → `inner_text()` |
| Haber detay başlığı | `h2.post-title` |
| Haber detay yayın tarihi | `.wt-post-info .post-date` |
| Haber detay gövdesi | `.wt-post-info .wt-post-text` → `inner_text()` |
| Sayfa numaraları | `a.page-link` içindeki `/kategori/<kategori>/<n>` adresleri |

Detay sayfasındaki ilk genel `h1`, haber başlığı değildir; ilgili başlık `h2.post-title` altında. Etkinlik kartlarının bazı `href` değerleri `etkinlik/<slug>` biçiminde, başında `/` bulunmuyor. Bunlar mevcut `/kategori/...` yoluna göre çözülürse hatalı adres oluşur; `https://www.ankara.edu.tr/` köküne göre çözülmelidir.

## Tarayıcının gördüğü API yanıtları

Gözlenen bütün CMS yanıtları HTTP 200 idi. Her sayfada genel ayar/menü için `https://ubys.ankara.edu.tr/api/CMS/GetMain?&websiteId=1&languageCode=tr-TR` da çağrıldı. Veri uç noktaları:

| İçerik | Tarayıcının yaptığı istek |
| --- | --- |
| Haber listesi, sayfa 1 | `https://ubys.ankara.edu.tr/api/CMS/GetMainNews?Page=0&PageSize=20&&websiteId=1&languageCode=tr-TR` |
| Haber listesi, sayfa 2 | Aynı uç nokta, `Page=1` |
| Haber detayı | `https://ubys.ankara.edu.tr/api/CMS/GetMainNewsSlug?&websiteId=1&languageCode=tr-TR&categorySlug=<slug>` |
| Duyurular | `https://ubys.ankara.edu.tr/api/CMS/GetMainNotices?Page=0&PageSize=20&&websiteId=1&languageCode=tr-TR`; sayfa 2 için `Page=1` |
| Etkinlikler | `https://ubys.ankara.edu.tr/api/CMS/GetMainevents?Page=0&PageSize=20&&websiteId=1&languageCode=tr-TR`; sayfa 2 için `Page=1` |

Yanıtların **kısaltılmış şekli** (alan adları ve örnek veri tipleri; gerçek yanıtın tam kopyası değil):

```json
{
  "items": [
    {
      "baslik": "metin",
      "url": "slug/metin",
      "publishDate": "tarih/metin",
      "icerik": "HTML/metin",
      "category": { "...": "..." }
    }
  ],
  "categories": ["..."],
  "index": 0,
  "size": 0,
  "count": 776,
  "pages": 39,
  "hasPrevious": false,
  "hasNext": true
}
```

Bu sayısal değerler haber listesinin ilk sayfasındaki gözlemdir. Liste yanıtlarında `items` 20 öğe içeriyordu; `size` alanı 0 görünürken istek parametresi `PageSize=20` idi. Duyurular için `count=1207, pages=61`, etkinlikler için `count=1172, pages=59` gözlendi. Etkinlik öğelerinde ayrıca `eventDateTime` ve `eventEndDateTime` alanları vardı. Detay yanıtı `{ "item": { "baslik", "publishDate", "icerik", "..." }, "items": [10 ilişkili öğe] }` biçimindeydi. Script içerik veya kimlik bilgisi yerine yalnızca alan adlarını ve sayfalama sayıları gibi yapısal bilgileri ağ gözlemine kaydeder.

## Sayfalama ve süre

Üç kategoride de `/kategori/<kategori>/1` ve `/kategori/<kategori>/2` çalıştı; ikinci sayfadaki 20 kayıt ilk sayfadan farklıydı. Görünen sayfa numarası **1 tabanlı**, API `Page` parametresi **0 tabanlı**. Kategori listelerinde sayfa numaraları gerçek `a.page-link` bağlantıları. "Sonraki" ve "Önceki" bağlantılarında `javascript:void(0);` bulunduğundan crawler için numaralı URL'leri üretmek daha güvenilir.

Hazır DOM seçicisinin görünmesine kadar ölçülen süreler: haber listesi 1/2 için 5,71/1,68 sn; üç haber detayı için 2,67/2,09/0,83 sn; duyuru listesi 1/2 için 1,52/0,69 sn; etkinlik listesi 1/2 için 0,93/1,48 sn. Dokuz sayfada ölçüm aralığı 0,69–5,71 sn, ortanca 1,52 sn. Bunlar tek oturumdaki gözlemler; ağ ve sunucu yüküne göre değişebilir. Ziyaretler arasında ayrıca en az 2,2 sn başlangıç aralığı uygulandı.

## Önerilen crawler yaklaşımı

Tek headless Chromium oturumu kullanıp kategori sayfalarını sırayla açmak, liste kartlarından URL ve görünen tarihi almak, ardından gerekli haber detaylarını açıp `.wt-post-text` gövdesini okumak yeterli. Her yeni üst düzey sayfa ziyaretinden önce en az 2 saniyelik aralık bırakılmalı; görünür DOM seçicisi için süre sınırı ve küçük sayıda yeniden deneme kullanılmalı. URL'ler tekilleştirilmeli, etkinlik bağlantıları site köküne göre normalize edilmeli, sayfalama `pages`/`hasNext` gözlemi ve numaralı kategori URL'si üzerinden sonlandırılmalı. Seçici veya yanıt şekli değişirse izleme/uyarı gerekir. API URL'leri yalnızca teşhis bilgisidir; doğrudan API çağrısı veya JS paketinden kimlik bilgisi çıkarımı bu denemenin parçası değildir.

Tekrar çalıştırma (PowerShell):

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Get-Location).Path '.pw-browsers')
.\.venv-win\Scripts\python.exe deneme_playwright.py
```
