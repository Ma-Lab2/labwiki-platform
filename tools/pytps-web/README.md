# PyTPS Tool Integration

This directory contains the TPS web analysis tool integrated into the private LabWiki site.

- Frontend path: `/tools/tps/`
- Backend API path: `/tools/tps/api/`
- WebSocket path: `/tools/tps/ws/`

The tool keeps lab-specific TPS defaults in a persistent config directory and reads raw image files from the host directory mounted through `TPS_IMAGE_DIR`.

## Local development

```bash
# Backend
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

In dev mode, Vite proxies `/api` and `/ws` to the backend. In the integrated deployment, Caddy mounts the tool under `/tools/tps/`.
