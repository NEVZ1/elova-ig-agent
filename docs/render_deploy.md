# Render deploy (kısa)

## 1) Git repo

Bu klasörü GitHub’a push et.

## 2) Render Blueprint

Render → **New** → **Blueprint** → repo’yu seç → `render.yaml` ile oluştur.

Oluşacak servisler:
- `elova-dm-api` (web)
- `elova-dm-worker` (worker)
- `elova-dm-beat` (beat)
- `elova-dm-redis` (redis)
- `elova-dm-postgres` (postgres)

## 3) Secret env’ler

Render’da aşağıdakileri gir:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `ADMIN_API_KEY`
- `IG_VERIFY_TOKEN`
- `IG_APP_SECRET` (webhook signature doğrulaması için)
- `IG_PAGE_ID`
- `IG_PAGE_ACCESS_TOKEN`
- `WHATSAPP_NUMBER`
- `BOOKING_URL`

## 4) Meta webhook

Webhook URL:
- `https://<render-domain>/webhooks/instagram`

Verify token:
- `IG_VERIFY_TOKEN`

Sağlık kontrolü:
- `https://<render-domain>/health/ready`
