# Architecture Overview

## Services
- Django REST API: authentication, document metadata, user dashboard endpoints.
- FastAPI services: async extraction and TTS orchestration entrypoints.
- PostgreSQL: persistent relational data.
- MinIO/S3: source files and generated audio objects.

## Core Flow
1. User uploads a PDF through web or API.
2. API validates file and stores object metadata.
3. Extraction service converts PDF to text.
4. TTS service converts text to audio.
5. API exposes audio URL and job status to clients.

## Future Extensions
- Celery or RQ workers with Redis broker.
- OAuth2 with social providers.
- Event-driven notifications (webhooks/email).
- Observability stack (Sentry + Prometheus + Grafana).
