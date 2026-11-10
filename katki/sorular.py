"""Karar modeline (Jev, ileride eğitilmiş Laya) sorulan tipli sorular.

Laya'nın soru başlığı sınırı yüzünden 81 il tek soruda sorulmaz: önce bölge, sonra o bölgenin ili.
"""

from typing import Literal, get_args

Kategori = Literal[
    "Sağlık ve iyi yaşam",
    "Eğitim ve yaşam boyu öğrenme",
    "Çevre, iklim ve sürdürülebilirlik",
    "Kültür, sanat ve miras",
    "Sosyal içerme ve dezavantajlı gruplar",
    "Ekonomik kalkınma, girişimcilik ve istihdam",
    "Bilim iletişimi ve halkı bilgilendirme",
    "Afet, acil durum ve insani yardım",
    "Kamu politikası ve kurumlara danışmanlık",
    "Uluslararası iş birliği ve kalkınma",
    "Diğer",
]

FaaliyetTuru = Literal[
    "Toplumsal proje",
    "Gönüllülük faaliyeti",
    "Halka açık eğitim / kurs / seminer",
    "Ücretsiz hizmet (sağlık taraması, hukuki destek vb.)",
    "Bağış / yardım kampanyası",
    "Kurumlarla protokol / iş birliği",
    "Halka açık etkinlik (konferans, sergi, festival)",
    "Rapor / yayın / politika önerisi",
    "Diğer",
]

BOLGE_ILLERI = {
    "Marmara": ["Balıkesir", "Bilecik", "Bursa", "Çanakkale", "Edirne", "İstanbul", "Kırklareli", "Kocaeli",
                "Sakarya", "Tekirdağ", "Yalova"],
    "Ege": ["Afyonkarahisar", "Aydın", "Denizli", "İzmir", "Kütahya", "Manisa", "Muğla", "Uşak"],
    "Akdeniz": ["Adana", "Antalya", "Burdur", "Hatay", "Isparta", "Kahramanmaraş", "Mersin", "Osmaniye"],
    "İç Anadolu": ["Aksaray", "Ankara", "Çankırı", "Eskişehir", "Karaman", "Kayseri", "Kırıkkale", "Kırşehir",
                   "Konya", "Nevşehir", "Niğde", "Sivas", "Yozgat"],
    "Karadeniz": ["Amasya", "Artvin", "Bartın", "Bayburt", "Bolu", "Çorum", "Düzce", "Giresun", "Gümüşhane",
                  "Karabük", "Kastamonu", "Ordu", "Rize", "Samsun", "Sinop", "Tokat", "Trabzon", "Zonguldak"],
    "Doğu Anadolu": ["Ağrı", "Ardahan", "Bingöl", "Bitlis", "Elazığ", "Erzincan", "Erzurum", "Hakkari", "Iğdır",
                     "Kars", "Malatya", "Muş", "Tunceli", "Van"],
    "Güneydoğu Anadolu": ["Adıyaman", "Batman", "Diyarbakır", "Gaziantep", "Kilis", "Mardin", "Siirt", "Şanlıurfa",
                          "Şırnak"],
}
IL_BOLGESI = {il: bolge for bolge, iller in BOLGE_ILLERI.items() for il in iller}
# il sorusu sorulmayan, haritada il yerine sayaç olarak gösterilen kapsamlar
TURKIYE_GENELI, YURT_DISI, CEVRIMICI = "Türkiye geneli", "Yurt dışı", "Çevrimiçi"
GENEL_KAPSAMLAR = (TURKIYE_GENELI, YURT_DISI, CEVRIMICI)

KARAR_SORULARI = {
    "katki": {
        "type": "noul",
        "instructions": "Bu haber, kurumun (üniversite, vakıf, dernek, STK, kamu kurumu) bilgi, uzmanlık veya "
        "kaynaklarını toplumun yararına kullandığı bir toplumsal katkı faaliyetini mi anlatıyor?",
        "criteria": {
            "true": "Topluma doğrudan fayda: halka açık etkinlik/eğitim, ücretsiz hizmet, sosyal proje, yardım, "
            "gönüllülük, dezavantajlı gruplara destek, öğrencilere burs/yemek/barınma desteği, kurumlarla topluma "
            "yönelik iş birliği.",
            "false": "Kurum içi işleyiş: sınav/kayıt/ders programı, atama, ihale, genel kurul, akademik ödül veya "
            "sıralama başarısı, iş ilanı, taziye, tören.",
        },
    },
    "kategori": {
        "type": "choice",
        "instructions": "Faaliyet en çok hangi alana giriyor?",
        "criteria": {k: k for k in get_args(Kategori)},
    },
    "faaliyet": {
        "type": "choice",
        "instructions": "Faaliyetin türü nedir?",
        "criteria": {k: k for k in get_args(FaaliyetTuru)},
    },
}

# --- Çok etiketli sorular (LLM özeti yerine) -------------------------------------------
# Her etiket ayrı bir evet/hayır (noul) sorusu; hepsi karar sorularıyla aynı Jev isteğinde sorulur.
# Soru anahtarı = önek + kısa ad; olasılık >= ETIKET_ESIGI ise etiket verilir.
ETIKET_ESIGI = 0.5

# haber ne hakkında? (katkı olsun olmasın her habere)
KONULAR = {
    "egitim": ("Eğitim", "Okul, kurs, ders, atölye, seminer ya da eğitim programı"),
    "ogrenci_destek": ("Öğrenci destekleri", "Burs, yemek, barınma, ulaşım gibi öğrencilere sosyal destek"),
    "saglik": ("Sağlık", "Sağlık hizmeti, hastalık, tarama, tedavi, sağlıklı yaşam"),
    "hastane": ("Hastane ve klinik", "Hastane, klinik, poliklinik, hasta hizmetleri"),
    "ruh_sagligi": ("Ruh sağlığı", "Psikolojik destek, ruh sağlığı, bağımlılık"),
    "cevre": ("Çevre ve iklim", "Çevre, iklim değişikliği, geri dönüşüm, ağaçlandırma, doğa"),
    "enerji_su": ("Enerji ve su", "Enerji, yenilenebilir enerji, su kaynakları, sanitasyon"),
    "tarim_gida": ("Tarım ve gıda", "Tarım, hayvancılık, gıda, beslenme, çiftçiler"),
    "kultur_sanat": ("Kültür ve sanat", "Konser, sergi, tiyatro, sinema, edebiyat, sanat etkinliği"),
    "tarih_miras": ("Tarih ve kültürel miras", "Tarih, arkeoloji, müze, kültürel miras, restorasyon"),
    "spor": ("Spor", "Spor etkinliği, turnuva, fiziksel aktivite"),
    "bilim_teknoloji": ("Bilim ve teknoloji", "Bilimsel araştırma, bilim şenliği, teknoloji, Ar-Ge"),
    "dijital": ("Dijital beceriler", "Yazılım, kodlama, yapay zekâ, bilişim, dijital okuryazarlık"),
    "girisimcilik": ("Girişimcilik ve inovasyon", "Girişimcilik, kuluçka merkezi, teknopark, inovasyon"),
    "istihdam": ("İstihdam ve kariyer", "İş bulma, kariyer, mesleki beceri, staj"),
    "ekonomi": ("Ekonomi", "Ekonomik kalkınma, yerel ekonomi, finans, kooperatif"),
    "afet": ("Afet ve acil durum", "Deprem, sel, yangın, afet hazırlığı, ilk yardım"),
    "yardim_bagis": ("Yardım ve bağış", "Bağış kampanyası, kan bağışı, ayni/nakdi yardım"),
    "sosyal_icerme": ("Sosyal içerme", "Yoksulluk, dezavantajlı gruplar, eşitsizlik, sosyal destek"),
    "engelli": ("Engelliler ve erişilebilirlik", "Engelli bireyler, erişilebilirlik, özel gereksinim"),
    "kadin": ("Kadın ve toplumsal cinsiyet", "Kadınlar, kadın hakları, toplumsal cinsiyet eşitliği"),
    "cocuk_genclik": ("Çocuk ve gençlik", "Çocuklar, gençler, gençlik çalışmaları"),
    "yasli": ("Yaşlılar", "Yaşlılar, yaşlı bakımı, yaşlılara yönelik hizmetler"),
    "goc": ("Göç ve mülteciler", "Göçmenler, mülteciler, sığınmacılar"),
    "hukuk": ("Hukuk ve insan hakları", "Hukuki destek, insan hakları, tüketici hakları"),
    "kent_ulasim": ("Kent ve ulaşım", "Şehircilik, ulaşım, altyapı, konut"),
    "hayvan": ("Hayvanlar", "Hayvan hakları, sokak hayvanları, veteriner hizmetleri"),
    "medya": ("Medya ve iletişim", "Gazetecilik, medya, yayıncılık, iletişim"),
    "uluslararasi": ("Uluslararası iş birliği", "Yurt dışı kurumlarla ortak çalışma, uluslararası proje"),
    "kamu_politikasi": ("Kamu politikası", "Kamu kurumlarına danışmanlık, politika önerisi, rapor"),
}

SDG_ADLARI = {
    1: "Yoksulluğa son", 2: "Açlığa son", 3: "Sağlık ve kaliteli yaşam", 4: "Nitelikli eğitim",
    5: "Toplumsal cinsiyet eşitliği", 6: "Temiz su ve sanitasyon", 7: "Erişilebilir ve temiz enerji",
    8: "İnsana yakışır iş ve ekonomik büyüme", 9: "Sanayi, yenilikçilik ve altyapı",
    10: "Eşitsizliklerin azaltılması", 11: "Sürdürülebilir şehirler ve topluluklar",
    12: "Sorumlu üretim ve tüketim", 13: "İklim eylemi", 14: "Sudaki yaşam", 15: "Karasal yaşam",
    16: "Barış, adalet ve güçlü kurumlar", 17: "Amaçlar için ortaklıklar",
}

HEDEF_KITLELER = {
    "cocuklar": ("Çocuklar", "Okul öncesi ve ilk/ortaokul çağındaki çocuklar"),
    "gencler": ("Gençler ve öğrenciler", "Lise/üniversite öğrencileri, gençler"),
    "kadinlar": ("Kadınlar", "Kadınlar"),
    "yaslilar": ("Yaşlılar", "Yaşlılar"),
    "engelliler": ("Engelliler", "Engelli bireyler ve aileleri"),
    "gocmenler": ("Göçmenler ve mülteciler", "Göçmenler, mülteciler"),
    "hastalar": ("Hastalar", "Hastalar ve hasta yakınları"),
    "dezavantajli": ("Dezavantajlı gruplar", "Yoksul, kırsal ya da imkânı kısıtlı kesimler"),
    "afetzedeler": ("Afetzedeler", "Afetten etkilenenler"),
    "ogretmenler": ("Öğretmenler", "Öğretmenler ve eğitimciler"),
    "ciftciler": ("Çiftçiler ve üreticiler", "Çiftçiler, küçük üreticiler"),
    "isletmeler": ("Girişimciler ve işletmeler", "Girişimciler, KOBİ'ler, sanayi"),
    "kamu": ("Kamu kurumları", "Belediyeler, bakanlıklar ve diğer kamu kurumları"),
    "genel_halk": ("Genel halk", "Belirli bir grup değil, herkese açık"),
}

PAYDAS_TURLERI = {
    "belediye": ("Belediye / valilik", "Belediye, valilik, kaymakamlık gibi yerel yönetimler"),
    "bakanlik": ("Bakanlık / kamu kurumu", "Bakanlık, genel müdürlük, kamu kurumu"),
    "okul": ("Okul / MEB", "Okullar, il/ilçe millî eğitim müdürlükleri"),
    "universite": ("Başka üniversite", "Haberi yayımlayan kurumdan başka bir üniversite"),
    "stk": ("STK / vakıf / dernek", "Sivil toplum kuruluşları, vakıflar, dernekler"),
    "ozel_sektor": ("Özel sektör", "Şirketler, bankalar, meslek odaları"),
    "hastane": ("Hastane / sağlık kurumu", "Hastaneler ve sağlık kuruluşları"),
    "uluslararasi": ("Uluslararası kuruluş", "BM, AB, yabancı üniversite ya da kuruluş"),
}
AU_ADI = "Ankara Üniversitesi"


def _noul(soru: str, evet: str) -> dict:
    return {"type": "noul", "instructions": soru, "criteria": {"true": evet, "false": "Hayır ya da metinde geçmiyor."}}


ETIKET_SORULARI = {
    **{f"konu_{k}": _noul(f"Haber '{ad}' konusuyla ilgili mi?", aciklama) for k, (ad, aciklama) in KONULAR.items()},
    **{f"sdg_{n}": _noul(f"Faaliyet BM Sürdürülebilir Kalkınma Amacı {n} ({ad}) ile ilgili mi?", f"SDG {n}: {ad}")
       for n, ad in SDG_ADLARI.items()},
    **{f"kitle_{k}": _noul(f"Faaliyetten '{ad}' faydalanıyor mu?", aciklama)
       for k, (ad, aciklama) in HEDEF_KITLELER.items()},
    **{f"paydas_{k}": _noul(f"Faaliyette dış paydaş olarak '{ad}' yer alıyor mu?", aciklama)
       for k, (ad, aciklama) in PAYDAS_TURLERI.items()},
    "paydas_au": _noul(f"Faaliyette {AU_ADI} (birimleri dahil) paydaş ya da ortak olarak geçiyor mu?",
                       f"Metinde {AU_ADI} ya da bir fakültesi/birimi ortak olarak anılıyor."),
}


def etiketler(answers: dict, onek: str, sozluk: dict) -> list:
    """Olasılığı eşiği geçen etiketlerin adları (sözlük değeri tuple ise ilk eleman)."""
    out = []
    for k, v in sozluk.items():
        a = answers.get(f"{onek}{k}")
        if a is not None and float(a.get("noul", 0)) >= ETIKET_ESIGI:
            out.append(k if onek == "sdg_" else (v[0] if isinstance(v, tuple) else v))
    return out

# Laya her seçeneği 48 token'da kırpar: iller nüfus sırasıyla, sığmayanlar "ve diğer ... illeri"
# (Laya tokenizer'ıyla ölçüldü; Jev de aynı metni görür ki iki model aynı soruya cevap versin)
BOLGE_SECENEKLERI = {
    "Marmara": "İstanbul, Bursa, Kocaeli, Balıkesir, Tekirdağ, Sakarya, Çanakkale, Edirne, Kırklareli, Yalova, Bilecik",
    "Ege": "İzmir, Manisa, Aydın, Denizli, Muğla, Afyonkarahisar, Kütahya, Uşak",
    "Akdeniz": "Antalya, Adana, Mersin, Hatay, Kahramanmaraş, Osmaniye, Isparta, Burdur",
    "İç Anadolu": "Ankara, Konya, Kayseri, Eskişehir, Sivas, Aksaray, Yozgat, Niğde, Nevşehir, Kırıkkale, Karaman, "
                  "Kırşehir, Çankırı",
    "Karadeniz": "Samsun, Trabzon, Ordu, Zonguldak, Çorum, Tokat, Düzce, Giresun, Rize, Kastamonu ve diğer "
                 "Karadeniz illeri",
    "Doğu Anadolu": "Van, Erzurum, Malatya, Elazığ, Ağrı, Muş, Kars, Bitlis, Hakkari, Bingöl, Iğdır ve diğer "
                    "Doğu Anadolu illeri",
    "Güneydoğu Anadolu": "Şanlıurfa, Gaziantep, Diyarbakır, Mardin, Batman, Adıyaman, Şırnak, Siirt, Kilis",
}

BOLGE_SORUSU = {
    "bolge": {
        "type": "choice",
        "instructions": "Faaliyet nerede yapıldı ya da hangi yerin halkına yönelik? Tek bir ildeyse o ilin "
        "bölgesini seç. Metinde yer geçmiyorsa kurumun bulunduğu ili ('il' alanı) esas al.",
        "criteria": {
            **BOLGE_SECENEKLERI,
            TURKIYE_GENELI: "Birden çok bölgede ya da ülke çapında (ulusal kampanya, birçok ilde aynı anda).",
            YURT_DISI: "Türkiye dışında bir ülkede yapıldı ya da oradaki insanlara yönelik.",
            CEVRIMICI: "Yalnız çevrimiçi (webinar, internet yayını); fiziksel bir yeri yok.",
        },
    }
}


def il_sorusu(bolge: str) -> dict:
    return {
        "il": {
            "type": "choice",
            "instructions": f"Faaliyet {bolge} Bölgesi'nin hangi ilinde yapıldı ya da hangi ilin halkına yönelik? "
            "Metinde il geçmiyorsa kurumun bulunduğu ili ('il' alanı) esas al.",
            "criteria": {il: f"{il} ili (ilçeleri dahil)." for il in BOLGE_ILLERI[bolge]},
        }
    }
