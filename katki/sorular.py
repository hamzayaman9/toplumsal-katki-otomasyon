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
