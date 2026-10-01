# Türkiye STK, vakıf ve dernek kaynak haritası

**Keşif tarihi:** 29.09.2026 (UTC). **Kapsam:** 500 kurum; 456 doğrulanmış canlı ana site ve 456 kaynak kaydı. `ilerleme.json` içindeki 768 adayın hafif keşfi tamamlandı; seçimde doğrulanmış haber girişleri, Ankara yakınlığı ve aday önceliği kullanıldı. Aday havuzunda aynı ana siteyi kullanan 15 yinelenen kayıt görüldü; seçimde tekil site tercih edildi. Bu harita Türkiye'deki bütün STK'ların envanteri değildir.

## Seçim ve doğrulama kaynakları

- [İçişleri Bakanlığı Sivil Toplumla İlişkiler Genel Müdürlüğü – Kamu Yararına Çalışan Dernekler](https://www.siviltoplum.gov.tr/kamu-yararina-calisan-dernekler): dernek unvanı ve merkez ili için resmî liste. Listedeki statü yayın sıklığını kanıtlamaz.
- [Gelir İdaresi Başkanlığı – Vergi Muafiyeti Tanınan Vakıflar](https://cdn.gib.gov.tr/api/gibportal-file/file/getFileResources?objectKey=arsiv%2Fyardim-kaynaklar%2Fyararli-bilgiler%2FVak%C4%B1flarListesi.pdf): vakıf unvanı ve merkez ili için resmî liste.
- [TÜSEV Mütevelliler Heyeti](https://tusev.org.tr/hakkimizda/mutevelliler-heyeti/): üye kurumlar ve doğrudan site bağlantıları.
- [STGM BİRLİKTE](https://www.stgm.org.tr/birlikte-degistirmek-icin-yeniden-yola-ciktik) ve [Finansal Güçlenme](https://www.stgm.org.tr/finansal-guclenme-programinda-birlikte-calisacagimiz-orgutler-belli-oldu): program katılımcıları ve yayımlanan kurum bağlantıları.
- [AFAD akreditasyon portalı](https://akreditasyon.afad.gov.tr/) ile kamu kurumlarının resmî siteleri, afet ve kamu adaylarını belirlemek için incelendi. Akreditasyon durumu kurum bazında çıkarılmadı.

Her pozitif site ve haber girişi HTTP 200 ile ilgili içerik türü ve sayfa/feed/JSON yapısı kontrol edilerek yazıldı. Doğrulanamayan URL'ler `null` bırakıldı. `robots.txt` okundu; `robots_kisitli: true` olan yolun taranması önerilmez. Keşif aynı hostta en az iki saniye aralık ve toplam en fazla sekiz eşzamanlı istekle yapıldı; derin tarama veya JavaScript çalıştırma yapılmadı.

## Kapsam ve yöntemler

| Ölçüt | Kurum | Canlı siteler içindeki pay |
|---|---:|---:|
| Canlı ana site | 456 | %100.0 |
| WordPress REST posts doğrulandı | 105 | %23.0 |
| RSS/Atom doğrulandı | 111 | %24.3 |
| Yalnız HTML haber/duyuru/etkinlik listesi | 177 | %38.8 |
| JS render gerekli görünüyor | 6 | %1.3 |
| Canlı fakat doğrulanmış haber girişi yok | 162 | %35.5 |
| `robots.txt` kısıtı işaretlendi | 1 | %0.2 |

WP, RSS ve JS satırları örtüşebilir. HTML satırı yalnız REST ve RSS bulunmayanları kapsar. Ayrı toplumsal katkı/sosyal sorumluluk/sürdürülebilirlik sayfası **27** kurumda; `toplumsal_katki_odakli` kaynak işareti **27** kurumda bulunuyor. İşaret, ayrı bir alt birim bulunduğunu tek başına kanıtlamaz; `birim` alanlarında adı açıkça yazılı ayrı birim sayısı **0**.

### Kurum türü

| Tür | Kurum |
|---|---:|
| vakif | 248 |
| dernek | 240 |
| kamu_kurumu | 10 |
| stk_diger | 2 |

### Faaliyet alanı

| Alan | Kurum |
|---|---:|
| diğer | 212 |
| eğitim | 78 |
| sağlık | 49 |
| yoksullukla mücadele | 38 |
| kültür | 22 |
| çocuk | 21 |
| engelli | 20 |
| çevre | 18 |
| kadın | 17 |
| afet | 14 |
| gönüllülük | 7 |
| göç | 4 |

### Merkez ili

| İl | Kurum |
|---|---:|
| ANKARA | 203 |
| İSTANBUL | 201 |
| belirsiz | 24 |
| İZMİR | 21 |
| ADANA | 4 |
| BURSA | 4 |
| ESKİŞEHİR | 4 |
| İZMIR | 3 |
| KONYA | 3 |
| KOCAELİ | 3 |
| ÇANAKKALE | 3 |
| BALIKESİR | 3 |
| ANTALYA | 2 |
| ERZURUM | 2 |
| RİZE | 2 |
| GAZİANTEP | 2 |
| AFYONKARAHİSAR | 1 |
| DENIZLI | 1 |
| HATAY | 1 |
| NEVŞEHİR | 1 |
| ERZİNCAN | 1 |
| DENİZLİ | 1 |
| MERSIN | 1 |
| ŞANLIURFA | 1 |
| SAMSUN | 1 |
| MERSİN | 1 |
| MALATYA | 1 |
| ISPARTA | 1 |
| KÜTAHYA | 1 |
| DIYARBAKIR | 1 |
| ELAZIĞ | 1 |
| TRABZON | 1 |

`il: belirsiz` ve `faaliyet_alani_il: belirsiz` doğrulanmış merkez/coğrafi kapsam bilgisi olmayan kayıtları gösterir. `faaliyet_alani_il` için merkez ili bir başlangıç vekili olarak kullanıldı; adında “Türkiye/Türk/Ulusal” bulunan kurumlar ve merkezi kamu kurumları `ulusal` olarak sınıflandı. Bu alan gerçek faaliyet coğrafyasının doğrulanmış dökümü değildir. Kapsam değeri dağılımı: ulusal 165, İSTANBUL 142, ANKARA 109, İZMİR 19, belirsiz 18, BURSA 4, İZMIR 3, ADANA 3, KONYA 3, KOCAELİ 3, ÇANAKKALE 3, ANTALYA 2, ERZURUM 2, RİZE 2, BALIKESİR 2, ESKİŞEHİR 2, GAZİANTEP 2, AFYONKARAHİSAR 1, DENIZLI 1, HATAY 1, NEVŞEHİR 1, ERZİNCAN 1, DENİZLİ 1, MERSIN 1, ŞANLIURFA 1, SAMSUN 1, MERSİN 1, MALATYA 1, ISPARTA 1, KÜTAHYA 1, DIYARBAKIR 1, ELAZIĞ 1, TRABZON 1.

## Ankara merkezli kurumlar

Seçilen **203** Ankara merkezli kurumun **159** tanesinin ana sitesi canlı. Öncelik sırasındaki yöntem göstergeleri aşağıdadır.

| Kurum | En iyi doğrulanmış haber girişi |
|---|---|
| Afet ve Acil Durum Yönetimi Başkanlığı | HTML |
| Ankara Büyükşehir Belediyesi | HTML |
| Keçiören Belediyesi | HTML |
| Sağlık Bakanlığı | HTML |
| Türk İşbirliği ve Koordinasyon Ajansı Başkanlığı | WP REST |
| Aile ve Sosyal Hizmetler Bakanlığı | giriş yok |
| Ankara Valiliği | giriş yok |
| Gençlik ve Spor Bakanlığı | giriş yok |
| Millî Eğitim Bakanlığı | giriş yok |
| Çankaya Belediyesi | giriş yok |
| ADALET TEŞKİLATINI GÜÇLENDİRME VAKFI | WP REST |
| ALTI NOKTA KÖRLER DERNEĞİ | HTML |
| ANADOLU KULÜBÜ DERNEĞİ | HTML |
| ANADOLU ÇAĞDAŞ EĞİTİM VAKFI (ANAÇEV) | HTML |
| ANKARA FOTOĞRAF SANATÇILARI DERNEĞİ | WP REST |
| ANKARA KULÜBÜ DERNEĞİ | HTML |
| ANKARA MİKROBİYOLOJİ DERNEĞİ | HTML |
| ANKARA TELSİZ VE RADYO AMATÖRLERİ KULÜBÜ DERNEĞİ | WP REST |
| ANKARA TIPLILAR DERNEĞİ | HTML |
| ANKARA ÇOKSESLİ MÜZİK DERNEĞİ | WP REST |
| ANKARA ÜNİVERSİTESİ GELİŞTİRME VAKFI | WP REST |
| ATATÜRKÇÜ DÜŞÜNCE DERNEĞİ | WP REST |
| Aramızda Toplumsal Cinsiyet Araştırmaları Derneği | WP REST |
| AİLE VE SOSYAL HİZMETLER BAKANLIĞI ŞEYH ZAYED ÇOCUK KORUMA VAKFI (ESKİ ADI: SOSYAL HİZMETLER VE ÇOCUK ESİRGEME KURUMU GENEL MÜDÜRLÜĞÜ ŞEYH ZAYED ÇOCUK KORUMA VAKFI) | WP REST |
| BİRLEŞMİŞ MİLLETLER TÜRK DERNEĞİ | HTML |
| DÜNYA ENERJİ KONSEYİ TÜRK MİLLİ KOMİTESİ DERNEĞİ | HTML |
| ELAZIĞ KÜLTÜR VE TANITMA VAKFI | HTML |
| Eğitimde Görme Engelliler Derneği | HTML |
| GÜVEN EĞİTİM VE SAĞLIK VAKFI | HTML |
| GÜÇSÜZLER YURDU DERNEĞİ | HTML |
| HABERAL EĞİTİM VAKFI | HTML |
| HAYVANLARI KORUMA DERNEĞİ | HTML |
| Hayat Sende Gençlik Akademisi Derneği | WP REST |
| HÜSEYİN GAZİ KÜLTÜR VE SANAT VAKFI | WP REST |
| ISPARTA İLİ KALKINDIRMA DERNEĞİ | WP REST |
| JANDARMA ASAYİŞ VAKFI | WP REST |
| KAMU ARAŞTIRMALARI VAKFI | HTML |
| KAYSERİ İLİ YARDIM DERNEĞİ | HTML |
| KIRIM TÜRKLERİ KÜLTÜR VE YARDIMLAŞMA DERNEĞİ | HTML |
| KIRŞEHİR ÖĞRENİM GENÇLİĞİNE YARDIM DERNEĞİ | WP REST |
| Lösemili Çocuklar Sağlık ve Eğitim Vakfı | HTML |
| MİLLİ GENÇLİK VAKFI | HTML |
| RÖNESANS EĞİTİM VAKFI | HTML |
| SAĞLIK VE SOSYAL YARDIM VAKFI | WP REST |
| SEMA YAZAR GENÇLİK VAKFI | HTML |
| SEREBRAL PALSİLİ ÇOCUKLAR DERNEĞİ | WP REST |
| SEVDA CENAP AND MÜZİK VAKFI | HTML |
| SEVGİ VAKFI (ESKİ ADI: SEVGİ KURAN KURSU İMAM HATİP VE YÜKSEK OKUL OĞRENCİLERİNİ KORUMA EĞİTİM VAKFI) | WP REST |
| SOSYOLOJİ DERNEĞİ | HTML |
| Sevgi Gönüllüleri Derneği | RSS/Atom |
| Sivil Toplum Geliştirme Merkezi Derneği | HTML |
| SİYASET EKONOMİ TOPLUM ARAŞTIRMALARI VAKFI | HTML |
| TÜKETİCİ HAKLARI DERNEĞİ | WP REST |
| TÜRK ANNELER DERNEĞİ | HTML |
| TÜRK EĞİTİM DERNEĞİ | WP REST |
| TÜRK FİZYOLOJİK BİLİMLER DERNEĞİ | HTML |
| TÜRK GASTROENTEROLOJİ DERNEĞİ | WP REST |
| TÜRK GÜREŞ VAKFI | WP REST |
| TÜRK HEMŞİRELER DERNEĞİ | HTML |
| TÜRK HUKUK KURUMU DERNEĞİ | WP REST |
| TÜRK JAPON VAKFI | WP REST |
| TÜRK JİNEKOLOJİ VE OBSTETRİK DERNEĞİ | WP REST |
| TÜRK KADINLAR KONSEYİ DERNEĞİ | WP REST |
| TÜRK KÜTÜPHANECİLER DERNEĞİ | WP REST |
| TÜRK NÖROLOJİ DERNEĞİ | HTML |
| TÜRK ORTOPEDİ VE TRAVMATOLOJİ BİRLİĞİ DERNEĞİ | HTML |
| TÜRK PARLAMENTERLER BİRLİĞİ DERNEĞİ | WP REST |
| TÜRK POLİS TEŞKİLATINI GÜÇLENDİRME VAKFI | HTML |
| TÜRK SOSYAL BİLİMLER DERNEĞİ | HTML |
| TÜRK SİLAHLI KUVVETLERİ DAYANIŞMA VAKFI | HTML |
| TÜRK SİLAHLI KUVVETLERİ EĞİTİM VAKFI | HTML |
| TÜRK SİLAHLI KUVVETLERİ MEHMETÇİK VAKFI | HTML |
| TÜRK TANITMA VAKFI | HTML |
| TÜRK TIBBİ REHABİLİTASYON KURUMU DERNEĞİ | WP REST |
| TÜRK ZİRAAT YÜKSEK MÜHENDİSLERİ BİRLİĞİ DERNEĞİ | WP REST |
| TÜRKMENELİ İŞBİRLİĞİ VE KÜLTÜR VAKFI | WP REST |
| TÜRKİYE DİYABET DERNEĞİ | HTML |
| TÜRKİYE DİYANET VAKFI | WP REST |
| TÜRKİYE EKONOMİK VE KÜLTÜREL DAYANIŞMA VAKFI | WP REST |
| TÜRKİYE EMEKLİ ASTSUBAYLAR DERNEĞİ | WP REST |
| TÜRKİYE EMEKLİ SUBAYLAR DERNEĞİ | HTML |
| TÜRKİYE EVDE SAĞLIK VE SOSYAL HİZMETLER DERNEĞİ | WP REST |
| TÜRKİYE FELSEFE KURUMU DERNEĞİ | HTML |
| TÜRKİYE FOTO MUHABİRLERİ DERNEĞİ | WP REST |
| TÜRKİYE GAZİLER VE ŞEHİT AİLELERİ KÜLTÜR VE YARDIMLAŞMA VAKFI (ESKİ ADI:TÜRKİYE GAZİLER VE KÜLTÜR VE DAYANIŞMA VAKFI) | HTML |
| TÜRKİYE KIZ İZCİLER DERNEĞİ | WP REST |
| TÜRKİYE ORGAN NAKLİ VE YANIK TEDAVİ VAKFI | WP REST |
| TÜRKİYE TABİATINI KORUMA DERNEĞİ | HTML |
| TÜRKİYE TANITIM ARAŞTIRMA DEMOKRASİ VE LAİK OLUŞUM VAKFI | WP REST |
| TÜRKİYE TEKNOLOJİ GELİŞTİRME VAKFI | HTML |
| TÜRKİYE YARDIM SEVENLER DERNEĞİ | RSS/Atom |
| TÜRKİYE ZİRAATÇILAR DERNEĞİ | WP REST |
| Türk Kızılay | HTML |
| Türkiye Kadın Dernekleri Federasyonu | HTML |
| ULUSLARARASI MÜSLÜMAN TOPLULUKLARLA DAYANIŞMA VAKFI (ESKİ ADI: TOKYO CAMİİ VAKFI) | HTML |
| ULUSLARARASI iSLAM DÜŞÜNCE VAKFI | HTML |
| Uluslararası Çocuk Merkezi Derneği | HTML |
| Uçan Süpürge Vakfı | WP REST |
| VİTALEN VAKFI | HTML |
| YAMANTÜRK VAKFI | HTML |
| YEŞİL TÜRKİYE ORMANCILAR DERNEĞİ | HTML |
| Çiğdem Eğitim, Çevre ve Dayanışma Derneği (Çiğdemim Derneği) | HTML |
| İBRAHİM ÇEÇEN VAKFI | WP REST |
| İLGİ OTİZM DERNEĞİ | WP REST |
| İNÖNÜ VAKFI | WP REST |
| AHMET MUHİP-MÜNİRE DIRANAS EĞİTİM VAKFI | site doğrulanmadı |
| ANITKABİR DERNEĞİ | giriş yok |
| ANKARA ATATÜRK LİSESİ EĞİTİM VAKFI | giriş yok |
| ANKARA HAMİYET VE İRFAN (A.H.İ) VAKFI | giriş yok |
| ANKARA KADIN VE ÇOCUK SAĞLIĞI DERNEĞİ | site doğrulanmadı |
| ANKARA PATOLOJİ DERNEĞİ | giriş yok |
| ANKARA ÖĞRETİM DERNEĞİ TEVFİK FİKRET EĞİTİM VAKFI | site doğrulanmadı |
| ANKARA İŞİTME ENGELİLER DERNEĞİ | site doğrulanmadı |
| AZERBAYCAN KÜLTÜR DERNEĞİ | giriş yok |
| BULGARİSTAN TÜRKLERİ KÜLTÜR VE YARDIMLAŞMA DERNEĞİ | site doğrulanmadı |
| BİRLEŞMİŞ MİLLETLER ÇOCUKLARA YARDIM FONU (UNICEF) TÜRKİYE MİLLİ KOMİTESİ DERNEĞİ | site doğrulanmadı |
| BİTLİS EĞİTİM VE TANITMA VAKFI | site doğrulanmadı |
| EKONOMİK VE SOSYAL ARAŞTIRMALAR MERKEZİ DERNEĞİ | giriş yok |
| EMNİYET TEŞKİLATI VAZİFE MALULÜ VE ŞEHİT AİLELERİ VAKFI | giriş yok |
| ERZİNCAN İLİ KÜLTÜR VE EĞİTİM DERNEĞİ | site doğrulanmadı |
| FENİLKETONÜRİLİ ÇOCUKLARI TARAMA VE KORUMA DERNEĞİ | site doğrulanmadı |
| GÖRMEYENLER KÜLTÜR VE BİRLEŞME DERNEĞİ | site doğrulanmadı |
| HACI BEKTAŞ VELİ ANADOLU KÜLTÜR VAKFI | site doğrulanmadı |
| HALK SAĞLIĞINI KORUMA DERNEĞİ | giriş yok |
| HEMPA ÇOCUK DERNEĞİ | giriş yok |
| KADININ SOSYAL HAYATINI ARAŞTIRMA VE İNCELEME DERNEĞİ | site doğrulanmadı |
| KALP HASTALARINA YARDIM VE ARAŞTIRMA DERNEĞİ | site doğrulanmadı |
| KANSERLİ ÇOCUKLARA YARDIM DERNEĞİ | site doğrulanmadı |
| KARTAL VAKFI | giriş yok |
| KIBRIS TÜRK KÜLTÜR DERNEĞİ | site doğrulanmadı |
| KIZILCAHAMAM-ÇAMLIDERE EĞİTİM VE SOSYAL YARDIMLAŞMA VAKFI | giriş yok |
| KONYA EĞİTİM KÜLTÜR VE SAĞLIK VAKFI | giriş yok |
| Kırmızı Şemsiye Cinsel Sağlık ve İnsan Hakları Derneği | site doğrulanmadı |
| MAHALLİ İDARELER DERNEĞİ | giriş yok |
| MANİSA YÜKSEK ÖĞRENİM ÖĞRENCİ VAKFI (ESKİ ADI: MANİSA YÜKSEK TAHSİL ÖĞRENCİ YURDU VAKFI) | site doğrulanmadı |
| MESLEKİ EĞİTİM VE KÜÇÜK SANAYİİ DESTEKLEME VAKFI | giriş yok |
| MURADİYE KÜLTÜR VAKFI | giriş yok |
| MÜLKİYELİLER BİRLİĞİ DERNEĞİ | giriş yok |
| MİLLİ EĞİTİM VAKFI (ESKİ ADI:MİLLİ EĞİTİM BAKANLIĞI VAKFI ) | giriş yok |
| ODTÜ MEZUNLARI BİRLİĞİ VAKFI | giriş yok |
| ODTÜ ÖĞRENCİ DESTEKLEME DERNEĞİ | giriş yok |
| ORMANCILIĞI GELİŞTİRME VE ORMAN YANGINLARI İLE MÜCADELE HİZMETLERİNİ DESTEKLEME VAKFI (OGEM-VAK) | site doğrulanmadı |
| ORTA DOĞU TEKNİK ÜNİVERSİTESİ GELİŞTİRME VAKFI | site doğrulanmadı |
| SAMİ EFENDİ İLİM VE KÜLTÜR YARDIMLAŞMA VAKFI | giriş yok |
| SOSYAL HİZMETLER EĞİTİM VE YARDIM VAKFI | site doğrulanmadı |
| SÜLEYMANİYE KÜLTÜR SANAT EĞTİM VE SAĞLIK VAKFI | giriş yok |
| TUSAŞ ELİNİ UZAT YARDIMLAŞMA DERNEĞİ | site doğrulanmadı |
| TÜRK BİYOKİMYA DERNEĞİ | site doğrulanmadı |
| TÜRK EĞİTİM DERNEĞİ ANKARA KOLEJİ VAKFI | site doğrulanmadı |
| TÜRK FARMAKOLOJİ DERNEĞİ | giriş yok |
| TÜRK HAVA KURUMU | giriş yok |
| TÜRK KADINLAR BİRLİĞİ DERNEĞİ | site doğrulanmadı |
| TÜRK KADINLARI KÜLTÜR DERNEĞİ | giriş yok |
| TÜRK KANSER ARAŞTIRMA VE SAVAŞ KURUMU DERNEĞİ | giriş yok |
| TÜRK KOOPERATİFÇİLİK KURUMU DERNEĞİ | giriş yok |
| TÜRK KÜLTÜRÜNÜ ARAŞTIRMA ENSTİTÜSÜ DERNEĞİ | site doğrulanmadı |
| TÜRK OCAKLARI DERNEĞİ | giriş yok |
| TÜRK PLASTİK REKONSTRÜKTİF VE ESTETİK CERRAHİ DERNEĞİ | giriş yok |
| TÜRK PSİKOLOGLAR DERNEĞİ | site doğrulanmadı |
| TÜRK RADYOLOJİ DERNEĞİ | giriş yok |
| TÜRK TÜBERKÜLOZ VE TORAKS DERNEĞİ | giriş yok |
| TÜRK İDARECİLER DERNEĞİ | giriş yok |
| TÜRKİYE ANITLAR DERNEĞİ | site doğrulanmadı |
| TÜRKİYE AZERBAYCAN DOSTLUK, İŞBİRLİĞİ VE DAYANIŞMA VAKFI | giriş yok |
| TÜRKİYE BİLİŞİM DERNEĞİ | giriş yok |
| TÜRKİYE DEVLET HASTANELERİ VE HASTALARA YARDIM VAKFI | site doğrulanmadı |
| TÜRKİYE EKONOMİ KURUMU DERNEĞİ | giriş yok |
| TÜRKİYE EĞİTİM, SAĞLIK, BİLİM VE ARAŞTIRMA VAKFI | giriş yok |
| TÜRKİYE FİLARMONİ DERNEĞİ | site doğrulanmadı |
| TÜRKİYE GRUP PSİKOTERAPİLERİ DERNEĞİ | giriş yok |
| TÜRKİYE GÖZ BANKASI DERNEĞİ | site doğrulanmadı |
| TÜRKİYE GÜÇSÜZLER VE KİMSESİZLERE YARDIM VAKFI | giriş yok |
| TÜRKİYE HAYIRLAR YAPTIRMA VE İDAME ETTİRME DERNEĞİ | site doğrulanmadı |
| TÜRKİYE KALKINMA VAKFI | giriş yok |
| TÜRKİYE KIZILAY DERNEĞİ | site doğrulanmadı |
| TÜRKİYE MODERN CERRAHİ EĞİTİM VE ARAŞTIRMA DERNEĞİ | giriş yok |
| TÜRKİYE MUHARİP GAZİLER DERNEĞİ | giriş yok |
| TÜRKİYE ODALAR VE BORSALAR EĞİTİM VE KÜLTÜR VAKFI | site doğrulanmadı |
| TÜRKİYE ORMANCILAR DERNEĞİ | giriş yok |
| TÜRKİYE ROMATİZMA ARAŞTIRMA VE SAVAŞ DERNEĞİ | giriş yok |
| TÜRKİYE SOSYAL PSİKİYATRİ DERNEĞİ | giriş yok |
| TÜRKİYE SİNİR VE RUH SAĞLIĞI DERNEĞİ | giriş yok |
| TÜRKİYE TRAFİK KAZALARI YARDIM VAKFI | giriş yok |
| TÜRKİYE VERİMLİLİK VAKFI | giriş yok |
| TÜRKİYE YAZARLAR BİRLİĞİ DERNEĞİ | site doğrulanmadı |
| TÜRKİYE ÇOCUK VE GENÇ PSİKİYATRİSİ DERNEĞİ | site doğrulanmadı |
| TÜRKİYE İL GENEL MECLİSİ ÜYELERİ DERNEĞİ | site doğrulanmadı |
| TÜRKİYE İSRAFI ÖNLEME VAKFI | giriş yok |
| ULUSLARARASI AKADEMİSYENLER DERNEĞİ | site doğrulanmadı |
| UĞUR MUMCU ARAŞTIRMACI GAZETECİLİK VAKFI | giriş yok |
| ZÜBEYDE HANIM ŞEHİT ANALARINI KORUMA VAKFI | site doğrulanmadı |
| ZİHİNSEL YETERSİZ ÇOCUKLARI YETİŞTİRME VE KORUMA VAKFI | site doğrulanmadı |
| ZİRAAT BANKASI EĞİTİM VAKFI | giriş yok |
| ÇELİKLER VAKFI | giriş yok |
| ÇEVRE EĞİTİM SAĞLIK VE SOSYAL YARDIM VAKFI (ESKİ ADI:SİSATEV- SOSYAL SİGORTALAR KURUMU SAĞLIK TESİSLERİNİ GÜÇLENDİRME VAKFI) | giriş yok |
| ÇOCUK HASTALIKLARI ARAŞTIRMA VAKFI | site doğrulanmadı |
| ÇOCUK SEVENLER DERNEĞİ | giriş yok |
| Çağdaş Drama Derneği | site doğrulanmadı |
| ÖĞRETİLEBİLİR ÇOCUKLARI KORUMA DERNEĞİ | site doğrulanmadı |
| İHSAN DOĞRAMACI BİLİM VE ARAŞTIRMA VAKFI(ESKİADI:HACETTEPE TIP MERKEZİ VAKFI) | giriş yok |
| İHSAN DOĞRAMACI EĞİTİM VAKFI(ESKİ ADI:HACETTEPE ÜNİVERSİTESİ VAKFI) | site doğrulanmadı |
| İHSAN DOĞRAMACI SAĞLIK VAKFI (ESKİ ADI:HACETTEPE ÇOCUK SAĞLIĞI ENSTİTÜSÜ VAKFI) | site doğrulanmadı |
| İHSAN DOĞRAMACI VAKFI | giriş yok |

## Crawler'a ekleme önceliği

1. Ankara merkezli, doğrulanmış WP REST girişi bulunan kurumlar. Pozitif `wp_rest` işaretinde kurumun ana site kökünden `/wp-json/wp/v2/posts` yolunu kullanın; gönderi bağlantısını ve tarihini kaydedin.
2. Ankara merkezli RSS/Atom, ardından diğer ulusal kurumların WP REST ve RSS kaynakları. `rss_url` yalnız gerçek `<item>`/`<entry>` döndüren feed'lerde doludur.
3. Doğrulanmış HTML `haber_url`, `duyuru_url`, `etkinlik_url` kaynakları. Her site için başlık, tarih, bağlantı ve sayfalama çıkarımını örnek sayfalarda test edin.
4. JS render işaretli ve canlı olduğu halde haber girişi bulunmayan siteleri sınırlı manuel incelemeye alın. `robots_kisitli: true` olan yolları otomatik tarama kuyruğuna eklemeyin.

Günde üç taramada ETag/Last-Modified, içerik karması ve kaynak başına son görülen bağlantı ile yinelenen indirmeleri azaltın. Haber tarih ve güncelliği bu keşifte ölçülmediğinden, canlı site sayısı düzenli yayın yapan site sayısı olarak okunmamalıdır.

## Sorunlar ve sınırlar

- 44 kurumun ana sitesi HTTP 200/kurum kimliği ile doğrulanamadı; URL uydurulmadı. Canlı olan 162 kurumda da doğrudan haber girişi bulunamadı.
- Arama sonucunda kuruma ait site yerine üçüncü taraf haber, rehber, sosyal medya hesabı veya tekil makale/profil çıktığında bu bağlantılar yayın kaynağı sayılmadı; bunlara bağlı haber URL'leri temizlendi.
- Bazı kurumlar aynı ana siteyi kullanıyor; yinelenen kayıtlar `ilerleme.json` içinde duruyor. `harita.json` taranabilir farklı girişleri öne çıkarıyor.
- 24 seçili kurumun merkez ili doğrulanamadı. Bu kurumlar Ankara merkezli olarak işaretlenmedi.
- Yüzeysel keşif ana site bağlantıları, standart REST/feed/sitemap yolları ve birkaç liste bağlantısıyla sınırlıydı. Alt alan adları, sayfalama, yayın sıklığı ve geçmiş arşiv kapsamı ayrıca ölçülmelidir.
