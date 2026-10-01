# Toplumsal Katkı Tarayıcısı

Ankara Üniversitesi Toplumsal Katkı Koordinatörlüğü için: Ankara ve Türkiye geneli kurum sitelerindeki haber/duyuru/etkinlikleri
günde 3 kez tarar, yenilerini kaydeder ve toplumsal katkı açısından sınıflandırır.

## Akış

```
kaynaklar (config/kaynaklar_ankara.json)
  → discover : her site için yöntem seç (WordPress REST API > RSS > liste sayfası; bulunamazsa LLM'e sor)
  → crawl    : yeni kayıtları çek, URL + içerik hash'i ile tekilleştir
  → classify : OpenRouter (typesafe/jev-router) ile JSON şemalı sınıflandırma (kategori, faaliyet türü, SDG, özet)
  → export   : rapor için CSV/JSON
```

## Kurulum

```bash
uv sync
cp .env.example .env        # gerekirse düzenle; OPENROUTER_API_KEY sistem ortamından da okunur
uv run python -m katki seed      # kaynak listesini veritabanına yükle
uv run python -m katki harita-yukle --sadece-kolay  # üç Türkiye haritasından WP/RSS kaynakları
uv run python -m katki discover  # tarama yöntemlerini belirle (tek seferlik, arada bir tekrarlanabilir)
```

## Kullanım

```bash
uv run python -m katki run              # tara + sınıflandır
uv run python -m katki stats            # özet
uv run python -m katki sources          # kaynak durumu
uv run python -m katki export --days 30 --only-katki   # data/disa_aktarim.csv
```

`harita-yukle` varsayılan olarak `research/uni-devlet`, `research/uni-vakif` ve `research/stk`
altındaki `harita.json` dosyalarını okur. Tek dosya için `--dosya yol/harita.json`
(birden fazla dosya için tekrar edilebilir) kullanılır. `--sadece-kolay` yalnızca
WordPress REST veya RSS işaretli kaynakları ekler. Aynı host ikinci kez eklenmez;
Ankara Üniversitesi hostları mevcut `seed` akışında kalır. Kaynaklarda kurum adı (`org`),
kurum türü (`org_type`), il (`city`) ve toplumsal katkı odağı (`focus`) tutulur.
Keşif haritadaki liste URL'lerini korur; JS render gereken siteleri notla bekletir.
Panelde kurum türü ve kurum filtreleri bulunur.

Yeni kaynakları sınırlı denemek için `discover --host site.example` ve
`crawl --host site.example --limit 5` kullanılabilir. `--host` tekrarlanabilir.
HTML liste kaynaklarında keşif, haber linki kuralını `sources.list_rules` alanına kaydeder;
sonraki taramalar aynı kuralı kullanır. Üç haritadan dengeli küçük örnek ölçümü için
`python scripts/html_adaptor_testi.py --n 30 --limit 5` çalıştırılır. Bu komut sınıflandırma yapmaz.

## Haftalık çalıştırma (şimdilik elle)

`haftalik_calistir.bat` dosyasına çift tıkla: veritabanını `data/yedek/` altına yedekler (son 5 tutulur),
tüm kaynakları tarar, yeni kayıtları sınıflandırır ve `raporlar/` altına sayısal rapor yazar:

- `raporlar/<tarih>_ozet.md` — okunabilir özet (kurum türü, kategori, SDG, en çok katkı üreten kurumlar, paydaşlar, maliyet)
- `raporlar/<tarih>_ozet.json` — aynı sayılar, makine için
- `raporlar/haftalik_ozet.csv` — her çalıştırmada bir satır; haftalar arası karşılaştırma

Tek tek: `python -m katki run`, `python -m katki rapor`, `python -m katki yedekle`.
Panel açıkken (`panel_ac.bat`) ilerleme `http://localhost:8000/canli` adresinden canlı izlenir.

İleride otomatikleştirmek için: `powershell -File scripts/zamanla.ps1` (Windows Görev Zamanlayıcı; henüz kurulmadı).

## Ayarlar (.env)

| Değişken | Açıklama |
|---|---|
| `ROBOTS_POLICY` | `ignore`: robots.txt Disallow yok sayılır (şu anki karar). `respect`: uyulur. Crawl-delay her durumda uygulanır (`MAX_CRAWL_DELAY` ile sınırlı). |
| `LLM_MODEL` | OpenRouter model adı. TypeSafe API anahtarı gelince doğrudan Jev'e geçilecek (`katki/llm.py`). |
| `MIN_HOST_DELAY` | Aynı siteye iki istek arası en az bekleme (sn). |

## Bilinen eksikler

- `www.ankara.edu.tr` Angular ile yüklendiği için şu an taranmıyor → Playwright adaptörü gerekli.
- WordPress etkinlik eklentilerinin özel içerik türleri (ör. etkinlik takvimi) henüz çekilmiyor, sadece `posts`.
- Keşif ayrıntıları: `docs/kesif_raporu.md`.
