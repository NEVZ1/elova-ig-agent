# Elova IG Chatbot — Render Background Worker Analiz Raporu

Tarih: 2026-04-23  
Kapsam: `/Users/sevogumusboga/Desktop/elona_automation/ig_chatbot` repo analizi, Render background worker deploy yolu, Celery/Redis/Postgres bağımlılıkları.

> Güvenlik notu: `.env` içindeki gizli değerler bu rapora yazılmadı. Sadece değişken isimleri ve yapısal durum incelendi.

## 1. Mevcut mimari

Proje bir FastAPI + Celery + Redis + PostgreSQL Instagram DM agent backend’i:

- Web API: `app.main:app`
- Instagram webhook: `POST /webhooks/instagram`
- Queue publish: `process_incoming_dm.delay(...)`
- Worker app: `app.workers.celery_app.celery`
- Ana DM task: `app.workers.tasks.process_incoming_dm`
- Follow-up task: `app.followup_engine.tasks.send_due_followups`
- Beat schedule: 5 dakikada bir follow-up task çalıştırıyor.

Worker’ın çalışması için zorunlu servisler:

1. Postgres `DATABASE_URL`
2. Redis-compatible queue `REDIS_URL` veya `CELERY_BROKER_URL` + `CELERY_RESULT_BACKEND`
3. Instagram outbound için `IG_PAGE_ID`, `IG_PAGE_ACCESS_TOKEN`
4. LLM için seçilen provider anahtarı: önerilen varsayılan `LLM_PROVIDER=openai` ve `OPENAI_API_KEY`; Gemini kullanılacaksa `LLM_PROVIDER=gemini` ve `GEMINI_API_KEY` gerekir.

## 2. Repo içinde bulunan kritik bulgular

### 2.1 Blueprint GitHub/GitLab karışıklığı

`render.yaml` içindeki iki servis daha önce sabit olarak GitLab repo URL’sine işaret ediyordu:

- web servis
- worker servis

Sen “blueprint GitHub’a deploy edildi” dediğin için bu karışıklık worker oluşturma/deploy aşamasında sorun çıkarabilir. Render Blueprint dokümanına göre `repo` alanı boş bırakılırsa Render, blueprint dosyasının bulunduğu repo’yu kullanır. Bu nedenle `repo:` satırları kaldırıldı.

### 2.2 Background worker ücretsiz değildir

Render’da free instance desteklenen servis tipleri web service, Postgres, Key Value ve static site tarafındadır; background worker free değildir. Blueprint’te worker `plan: starter` olarak doğru görünüyor. Render hesabında ödeme yöntemi / starter plan yetkisi yoksa worker deploy edilemez.

### 2.3 Celery broker yerelde yanlış görünüyor

Yerel `.env` içinde:

- `REDIS_URL`: harici/uzun bir URL olarak set edilmiş.
- `CELERY_BROKER_URL`: localhost Redis’e işaret ediyor.
- `CELERY_RESULT_BACKEND`: localhost Redis’e işaret ediyor.

Kod mantığı şu: `CELERY_BROKER_URL` boşsa `REDIS_URL` kullanılır. Ama `CELERY_BROKER_URL` doluysa onu öncelikli alır. Bu yüzden yerelde veya Render env’de bu iki Celery değişkeni yanlışlıkla localhost kalırsa worker Redis’e bağlanamaz.

Render’da yapılması gereken: `CELERY_BROKER_URL` ve `CELERY_RESULT_BACKEND` hiç set edilmeyecekse sorun yok; kod `REDIS_URL`’e düşer. Eğer set edilecekse ikisi de gerçek Redis URL olmalı.

### 2.4 `.env` içinde bozuk satır var

`.env` dosyasında eşittir işareti olmayan bir satır tespit edildi. Bu genellikle bir API key’in iki satıra bölünmesinden olur. Bu satır Render’a taşınmamalı. Render env panelinde değerler tek satır olmalı.

### 2.5 Worker task import testi başarılı

Yerel venv Python 3.11.15 ile worker modülleri import edildi ve Celery task’ları kayıtlı göründü:

- `app.workers.tasks.process_incoming_dm`
- `app.followup_engine.tasks.send_due_followups`

Yani temel Python import/entrypoint problemi görünmüyor.

### 2.6 Python versiyonu

Repo README’si Python 3.11–3.13 öneriyor; sistem default Python 3.14 ama `.venv` Python 3.11.15. Render native Python runtime’da Python versiyonunu sabitlemek için gerekirse repo köküne `.python-version` eklenebilir:

```text
3.11.15
```

Bu opsiyoneldir ama build sürprizlerini azaltır.

## 3. Yapılan repo değişikliği

`render.yaml` güncellendi:

1. Sabit GitLab `repo:` satırları kaldırıldı. Böylece GitHub Blueprint kendi repo’sunu kullanır.
2. Worker start komutuna düşük kaynak kullanımı için `--concurrency=1` eklendi:

```bash
celery -A app.workers.celery_app.celery worker -B -l info --concurrency=1
```

Bu tek instance worker + embedded beat yapısında maliyet ve RAM açısından daha güvenli.

## 4. Render’da doğru deployment ayarları

### Web service

- Type: Web Service
- Runtime: Python
- Plan: Free olabilir
- Build command:

```bash
pip install -r requirements.txt
```

- Pre-deploy command:

```bash
alembic upgrade head
```

- Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- Health check path:

```text
/health/ready
```

### Background worker

- Type: Background Worker
- Runtime: Python
- Plan: Starter veya üstü gerekir
- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
celery -A app.workers.celery_app.celery worker -B -l info --concurrency=1
```

## 5. Render env checklist

Aşağıdaki env’ler web ve worker tarafında tutarlı olmalı.

### İkisine de koy

- `ENV=production`
- `LOG_LEVEL=INFO`
- `DATABASE_URL=<Postgres URL>`
- `REDIS_URL=<Redis/Key Value URL>`
- `LLM_PROVIDER=gemini` veya `openai`
- `LLM_UNIFIED_MODE=true`
- `GEMINI_API_KEY=<tek satır>` eğer provider gemini ise
- `OPENAI_API_KEY=<tek satır>` eğer provider openai ise
- `IG_PAGE_ID=<...>`
- `IG_PAGE_ACCESS_TOKEN=<...>`
- `WHATSAPP_NUMBER=<...>`
- `BOOKING_URL=<...>`

### Web için ayrıca

- `ADMIN_API_KEY=<...>`
- `IG_VERIFY_TOKEN=<...>`
- `IG_APP_SECRET=<...>`

### Dikkat

- `CELERY_BROKER_URL` ve `CELERY_RESULT_BACKEND` boş bırakılabilir. Kod `REDIS_URL` kullanır.
- Eğer Render env’de `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` varsa, localhost olmamalı; gerçek Redis URL olmalı.
- API key’ler tek satır olmalı; kopyalama sırasında bölünmemeli.

## 6. En olası deploy hata senaryoları ve çözüm

### Senaryo A — Worker hiç oluşmuyor

Muhtemel nedenler:

- Render free plan ile worker açmaya çalışmak.
- Hesapta ödeme yöntemi yok.
- Blueprint eski `repo:` alanı yüzünden GitLab repo erişimi bekliyor.

Çözüm:

1. Bu repo değişikliğini GitHub’a push et.
2. Blueprint’i yeniden sync et.
3. Worker planının `starter` olduğundan ve ödeme yönteminin aktif olduğundan emin ol.

### Senaryo B — Worker build oluyor ama start sonrası crash

Muhtemel nedenler:

- `DATABASE_URL` eksik/yanlış.
- `REDIS_URL` eksik/yanlış.
- `CELERY_BROKER_URL` localhost kalmış.
- API key satırı bozuk veya iki satıra bölünmüş.

Çözüm:

1. Render worker logs’da ilk traceback’e bak.
2. Env panelinde `CELERY_BROKER_URL` ve `CELERY_RESULT_BACKEND` varsa kaldır veya gerçek Redis URL yap.
3. `REDIS_URL` gerçek Redis/Key Value URL mi kontrol et.
4. `DATABASE_URL` Postgres URL mi kontrol et.

### Senaryo C — Webhook 200 dönüyor ama cevap gitmiyor

Muhtemel nedenler:

- Web servis queue’ya publish edemiyor; Redis yanlış.
- Worker çalışmıyor.
- Instagram access token/permission outbound send için yetersiz.
- LLM provider key eksik.

Çözüm:

1. Web loglarında `queue_publish_failed` var mı bak.
2. Worker loglarında `dm_replied` veya `dm_reply_failed` var mı bak.
3. Worker loglarında LLM hata varsa provider/key düzelt.
4. Instagram Graph token yetkilerini tekrar kontrol et.

## 7. Deployment sonrası test yolu

1. GitHub’a push:

```bash
git add render.yaml docs/background_worker_render_analysis_2026-04-23.md
git commit -m "Fix Render worker blueprint config"
git push origin main
```

2. Render → Blueprint → Sync / Apply changes.

3. Web service hazır mı kontrol et:

```text
https://<api-domain>/health
https://<api-domain>/health/ready
```

4. Worker logs’da aşağı benzeri bir başlangıç bekle:

```text
celery@... ready.
```

5. Render Shell / one-off job imkanı varsa task publish smoke test:

```bash
python - <<'PY'
from app.followup_engine.tasks import send_due_followups
r = send_due_followups.delay()
print(r.id)
PY
```

6. Gerçek webhook testinde web loglarında:

- `instagram_webhook_post`
- `dm_received`

Worker loglarında:

- `dm_replied`

beklenir.

## 8. Önerilen sonraki mimari iyileştirme

Şimdilik tek worker servisinde `-B` ile Celery Beat gömülü çalışıyor. Bu maliyet açısından iyi. Ancak ileride worker birden fazla instance’a çıkarılırsa Beat duplicate follow-up üretebilir. Ölçekleme zamanı geldiğinde ikiye ayır:

1. `elova-dm-worker`: sadece worker
2. `elova-dm-beat`: sadece beat

veya follow-up için Render Cron Job kullan.

## 9. Kaynaklar

- Render Background Workers: background worker’lar sürekli çalışan ve queue poll eden servislerdir.
- Render Celery quickstart: Celery worker için Redis/Key Value broker önerilir.
- Render Blueprint spec: `type: worker`, `startCommand`, `plan`, `repo` davranışı.
- Render Free docs: background worker free instance destekli servis tipleri arasında değildir.

## 10. Ek teşhis — `db_unreachable` devam ederse

2026-04-23 ek bulgu: lokal makinede mevcut Supabase direct host (`db.<project-ref>.supabase.co:5432`) ile `SELECT 1` başarılı oldu; fakat Render tarafında `/health/ready` hâlâ `{"detail":"db_unreachable"}` dönüyorsa en güçlü kök neden Render ↔ Supabase direct connection IPv6 uyumsuzluğudur.

Supabase dokümanı direct connection string’in IPv6 kullandığını, IPv6 desteklemeyen platformlarda Supavisor pooler kullanılması gerektiğini belirtir. Aynı Supabase troubleshooting dokümanı IPv6 desteklemeyen örnek platformlar arasında Render’ı açıkça listeler.

Render için önerilen `DATABASE_URL`:

```text
postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres?sslmode=require
```

Önemli seçim:

- Render web service + worker gibi sürekli çalışan servisler için **Session Pooler / port 5432** kullan.
- Transaction Pooler / port 6543 serverless işlerde iyidir; ancak bazı Postgres client’larında prepared statement sorunları çıkarabilir. Bu projede en güvenli ilk tercih Session Pooler’dır.

Yeni teşhis scripti:

```bash
python scripts/check_db_connection.py
```

Render Shell veya local ortamda gizli şifreleri yazdırmadan DB host/port/driver bilgisini ve `SELECT 1` sonucunu gösterir.

## 11. Yeni bulgu — Worker artık broker değil memory yüzünden düşüyor

2026-04-23 tarihli yeni Render logu şunu gösteriyor:

- broker çözülmüş (`transport: redis://...` görünüyor)
- task'lar yüklenmiş
- ama worker `concurrency: 16 (prefork)` ile başlıyor
- sonra `Ran out of memory (used over 512MB)` ile instance restart oluyor

Bu şu anlama gelir:

1. `No such transport` problemi çözülmüş veya aşılıp Redis bağlantısı kurulmuş.
2. Yeni ana problem Render starter instance üzerinde Celery'nin varsayılan prefork worker havuzu.
3. 16 prefork process, 512MB RAM'de bu proje için fazla.

Doğru Render davranışı yeni kod deploy edilince şu olmalı:

- start command: `python -m app.workers.run_worker`
- Celery pool: `solo`
- concurrency: `1`

Eğer loglarda hâlâ `concurrency: 16 (prefork)` görüyorsan, Render eski start command / eski commit ile çalışıyordur.

### Beklenen yeni log

```text
starting_celery_worker broker=redis://<host>:6379 backend=redis://<host>:6379
```

ve Celery banner tarafında prefork yerine solo / concurrency 1 görünmelidir.

### Acil çözüm

1. Son commit'leri GitHub'a push et.
2. Render worker service için **Manual Deploy → Clear build cache & deploy latest commit** çalıştır.
3. Worker settings içinde Start Command gerçekten `python -m app.workers.run_worker` mı kontrol et.
4. Deploy sonrası logda artık `concurrency: 16 (prefork)` görünmemeli.

### Gerekirse ek sert düşürme

Eğer yine memory sıkışırsa iki seçenek var:

- Worker'ı `-B` olmadan çalıştırıp beat'i ayrı servise almak
- Veya worker planını bir seviye yükseltmek

Ama ilk denenecek çözüm kesinlikle `solo + concurrency=1` ile redeploy'dur.
