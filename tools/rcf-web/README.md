# RCF Tool Integration

This directory contains the RCF stack design tool integrated into the private LabWiki site.

- Frontend path: `/tools/rcf/`
- Backend API path: `/tools/rcf/api/v1/`
- WebSocket path: `/tools/rcf/api/v1/ws/`

The frontend is a Vue + Vite app served by Nginx. The backend is a FastAPI service with persistent uploaded material storage.
