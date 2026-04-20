# API Starter Endpoints

## Django API
- GET `/api/health/` - basic health probe
- GET `/api/documents/` - list current user documents
- POST `/api/documents/` - upload/create a new document
- GET `/api/documents/{id}/` - retrieve a document record

## FastAPI Services
- GET `/health` - service health
- POST `/v1/extract` - extraction job stub
- POST `/v1/tts` - tts job stub
