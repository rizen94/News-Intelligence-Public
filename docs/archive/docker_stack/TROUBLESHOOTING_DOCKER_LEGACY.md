# Docker-oriented troubleshooting (legacy)

**Superseded:** Use [`docs/TROUBLESHOOTING.md`](../../TROUBLESHOOTING.md) for bare metal (uvicorn, Vite, Widow PostgreSQL).

```bash
docker ps
docker restart news-intelligence-api
docker logs news-intelligence-api --tail 50
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT 1;"
docker-compose down && docker-compose up -d
```
