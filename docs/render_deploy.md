# Render deploy (kısa)

## 1) Git repo

Bu klasörü GitHub’a push et.

## 2) Render Blueprint (düşük maliyet)

Render → **New** → **Blueprint** → repo’yu seç → `render.yaml` ile oluştur.

Oluşacak servisler:
- `elova-dm-api` (web, free plan)
- `elova-dm-worker` (worker, starter plan, `-B` ile beat dahil)

Bu Blueprint, Render’ın managed Postgres/Redis’ini kurmaz (maliyet düşürmek için).
Onun yerine dışarıdan sağlayacağın URL’leri env olarak girersin.

## 3) Secret env’ler

Render’da aşağıdakileri gir:
- `DATABASE_URL` (harici Postgres)
- `REDIS_URL` (harici Redis; Celery broker + backend)
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
