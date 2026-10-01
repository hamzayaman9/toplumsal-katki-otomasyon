# Ankara Üniversitesi alt siteleri: haber/duyuru/etkinlik keşfi

**Tarih:** 29 Eylül 2026 (Europe/Istanbul)  
**Kapsam:** `*.ankara.edu.tr` için pasif alan adı keşfi ve düşük hızlı HTTP incelemesi. Makinece okunabilir kayıtlar [kaynaklar_ankara.json](kaynaklar_ankara.json) dosyasındadır.

## Sonuç

| Ölçü | Sayı |
|---|---:|
| crt.sh içinde farklı alan adı | 52 |
| crt.sh, RapidDNS ve HackerTarget birleşiminde geçerli farklı aday | 194 |
| Gürültü ön elemesi, indekslenmiş birim sayfaları ve `www` varyantları sonrası HTTP denenen host | 170 |
| HTTP ile açılan host | 130 |
| Açılmayan host | 40 |
| Canlı olup `robots.txt` içinde `User-agent: *` için `Disallow: /` bulunan host | 87 |
| Tam yasak bulunmayan canlı host | 43 (ikisi başka hosta yönleniyor; 41 ayrı host) |
| Tam yasak bulunmayanlarda doğrulanan haber / duyuru / etkinlik listesi | 12 / 26 / 26 |
| Tam yasak bulunmayanlarda doğrulanan RSS/Atom / XML sitemap | 25 / 28 |
| XML sitemap kök dosyasında `<lastmod>` bulunan | 1 |

Oranların paydası, yönlendirme takma adları çıkarıldığında **41 ayrı ve tümüyle yasaklanmamış canlı host**tur: RSS %61, sitemap %68, haber listesi %29. Tam yasaklı 87 hostun içerik adresleri JSON’da boş bırakıldı; **crawler bu hostları taramamalı**. `canli: true` yalnızca HTTP erişimini anlatır; tarama izni anlamına gelmez.

## Keşif ve doğrulama yöntemi

- [crt.sh sertifika kayıtları](https://crt.sh/?q=%25.ankara.edu.tr&output=json): 449 kayıt, wildcard öneki ayıklandıktan sonra 52 farklı host.
- [RapidDNS pasif sonuçları](https://rapiddns.io/subdomain/ankara.edu.tr?full=1): ilk erişilebilir sonuçlarda 99 host. Sayfa toplam 12.502 kayıt bildirdiği halde tam dışa aktarım sunmadığı için bu sayı **tam envanter değildir**. [HackerTarget host araması](https://api.hackertarget.com/hostsearch/?q=ankara.edu.tr) 51 satır verdi. Bu kaynakların birleşimi 194 geçerli farklı adaydır. Sayısal sunucu adları, `bidNNN`, mail/webmail, cpanel, API ve CDN benzeri altyapı hostları yayın kaynağı listesinden ön elendi.
- [Ana sitenin akademik/idari birim sayfaları](https://www.ankara.edu.tr/akademik-ve-idari-birimler/Fakulteler) Angular uygulaması olarak yalnızca boş HTML kabuğu gönderiyor; ham HTML’de birim linkleri yok. Uygulamanın kullandığı `ubys.ankara.edu.tr/api/Kapi/GetUnits` uç noktası bu istemciye HTTP 403 verdi. [Uyum Programı’nın fakülte ve yüksekokul sayfaları](https://uyum.ankara.edu.tr/fakulteler/) birim adlarının çapraz kontrolünde kullanıldı. İndekslenmiş birim sayfaları ve `www` varyantları ile adaylar genişletildi.
- Her hostta önce `robots.txt` istendi. İlk ana sayfa yoklamasında robots gruplarının büyük/küçük harfini ayırt eden ayrıştırıcı, bazı `Disallow: /` kurallarını kaçırdı ve bu hostların ana sayfasına **birer hatalı istek** gönderildi. Hata fark edilince robots ayrıştırması düzeltildi; yasaklı hostlara başka içerik isteği yapılmadı, ilk yoklamadan elde edilen içerik adresleri sonuçtan çıkarıldı. Yasaksız hostlarda liste sayfası, RSS ve XML sitemap HTTP/XML yanıtıyla doğrulandı. İstekler `AU-ToplumsalKatki-Recon/0.1` kimliğiyle, host başına en az 1 saniye aralıkla ve en çok 5 eşzamanlı işçiyle yapıldı.

**Kapsama sınırı:** Ana birim dizini API ile geldiği ve API 403 döndürdüğü için “tüm alt siteler” kesin olarak kanıtlanamıyor. Sertifika/pasif DNS kayıtları da eksiksiz yayın envanteri değildir. JSON, bu keşifte saptanan ve ön elemeden geçen hostların durumunu gösterir; bulunmamış bir hostun yokluğu anlamına gelmez.

## Ortak yapı kalıpları

130 canlı hostun 113’ü ana sayfa izlerine göre WordPress. Çok sayıda birim aynı WordPress ağının izlerini (`wp-content/uploads/sites/...`) taşıyor. Açık hostlarda doğrulanmış yaygın yollar:

| İçerik | En sık yol | Açık host sayısı |
|---|---|---:|
| Haber | `/tum-haberler/` | 4 |
| Duyuru | `/tum-duyurular/` | 19 |
| Etkinlik | `/tum-etkinlikler/` | 15 |

`/category/haber/`, `/category/duyuru/`, `/category/etkinlik/`, `/haberler/`, `/events/` ve birleşik haber/duyuru arşivleri de var. WordPress sitelerinin doğrulanan RSS adresi çoğunlukla `/feed/`; doğrulanan sitemap adresi çoğunlukla `/wp-sitemap.xml`. WordPress kök sitemap dosyaları bu örneklerde `<lastmod>` içermiyor. [Ana sitenin sitemap’i](https://www.ankara.edu.tr/sitemap.xml) 2.508 URL ve `<lastmod>` içeriyor; **2.508 tarihin tamamı `2026-04-17T11:20:32.108+03:00`**, bu yüzden yeni içerik seçmek için kullanılamaz.

Ana site ayrı bir Angular/özel uygulama. Uygulama paketinde liste yolları `/kategori/haberler/1`, `/kategori/duyurular/1`, `/kategori/etkinlikler/1` ve detay yolu `/haber/:slug` olarak tanımlı. Ana sitenin RSS’i doğrulanmadı. Bazı fakültelerde yalın host TCP bağlantısını reddederken `www` varyantı çalışıyor; 16 böyle eşleşme bulundu. `adayogrenci.ankara.edu.tr` ana siteye, `ankuzem.ankara.edu.tr` ise `ankuzef.ankara.edu.tr` adresine yönleniyor; bunlar ayrı yayın akışı sayılmamalı.

## Ana siteden üç haber detayı

Aşağıdaki üç URL, `AU-ToplumsalKatki-Recon/0.1` ile HTTP 200 döndürdü. Üçünün HTTP yanıtı da aynı 22.270 baytlık Angular kabuğu; başlık, tarih ve gövde **ilk HTML yanıtında bulunmuyor**. CSS seçicileri indirilen Angular detay bileşeni şablonundan çıkarıldı, çalıştırılmış DOM/API yanıtıyla doğrulanamadı.

| Örnek haber URL’si | Başlık bilgisi |
|---|---|
| [Disiplinlerarası Yapay Zekâ Proje Pazarı](https://www.ankara.edu.tr/haber/ankara-universitesinde-disiplinlerarasi-yapay-zek-proje-pazari) | URL adından çıkarıldı; gerçek metin API olmadan doğrulanamadı. |
| [Rektör Ünüvar: “Atatürk’ün Emanetini Daha İleriye Taşıyacağız”](https://www.ankara.edu.tr/haber/rektor-unuvar-ataturkun-emanetini-daha-ileriye-tasiyacagiz) | Arama dizininde görülen başlık. |
| [Araştırma Üniversiteleri Sıralamasında 4 Basamak Yükseldi](https://www.ankara.edu.tr/haber/ankara-universitesinden-onemli-basari-arastirma-universiteleri-siralamasinda-4-basamak-yukseldi) | URL adından çıkarıldı; gerçek metin API olmadan doğrulanamadı. |

Üçü için de şablondaki hedefler: **başlık** `.blog-post .wt-post-title h2.post-title`; **görünen tarih** `.blog-post .wt-post-meta li.post-date`; **gövde** `.blog-post .wt-post-text`. Tarih bileşeni `updatedDate` varsa onu, yoksa `createdDate` değerini gösteriyor. Gerçek tarih değerleri bu erişimle alınamadı. Uygulama `ubys.ankara.edu.tr` API’sine başvuruyor; API 403 olduğu için ana site detay çıkarımı üretim crawler’ında ayrıca çözümlenmeli.

## Sorunlu durumlar ve crawler önerileri

1. [Örnek birim robots dosyası](https://abamer.ankara.edu.tr/robots.txt) `User-agent: *`, `Disallow: /` ve `Crawl-delay: 60` içeriyor. Tam yasaklı **87 hostu tarama planına eklemeyin**. Bu birimlerin içeriği gerekiyorsa üniversiteden yazılı erişim/robots düzenlemesi isteyin. İzin alınsa bile `Crawl-delay` değeri kullanıcının 1 istek/saniye üst sınırından daha kısıtlayıcı olabilir.
2. Host başına robots kurallarını ayrı saklayın; `www` varyantını ve yönlendirme hedefini yeniden denetleyin. `robots.txt` erişim hatasında (örneğin `dtds.ankara.edu.tr`) otomatik içerik taramasını erteleyip yeniden deneyin.
3. Açık WordPress sitelerinde önce doğrulanmış RSS, ardından sitemap ve liste sayfasını kullanın. Haber, duyuru, etkinlik yollarını host başına JSON’dan alın; tüm hostlarda aynı yolu varsaymayın. Gönderi kalıcı URL’siyle tekilleştirin; tarih ve saatleri `Europe/Istanbul` olarak yorumlayın.
4. Ana site için sitemap URL keşfinde işe yarayabilir fakat tek tip/eski `lastmod` ile artımlı tarama yapılamaz. API erişimi ya da üniversitenin yayımlayacağı uygun bir besleme olmadan başlık, tarih ve gövdeyi güvenilir biçimde çıkarma tasarımı tamamlanmış sayılmamalı.
5. Günde üç tarama için her hostta koşullu GET (`ETag`/`Last-Modified`) ve değişen sayfalarla sınırlı ayrıştırma kullanın. İstek planlayıcı robots kurallarını, host başına en fazla 1 istek/saniyeyi ve toplam en fazla 5 eşzamanlı isteği birlikte uygulamalı.

**JSON okuma notu:** `null`, doğrulanmamış veya bulunamamış alanı gösterir. Tam yasaklı hostlarda içerik URL alanları özellikle boş bırakıldı; `notlar` alanındaki robots uyarısı geçerlidir. `sitemap_lastmod`, doğrulanan kök sitemap dosyasında `<lastmod>` etiketi bulunup bulunmadığını belirtir.
