# News Intelligence System - Reboot Checklist

## ✅ Pre-Reboot Status (COMPLETED)
- [x] All containers stopped gracefully
- [x] All persistent volumes preserved
- [x] All critical files backed up
- [x] All configurations verified
- [x] Startup script created

## 🔄 Post-Reboot Actions
1. Navigate to project directory:
   ```bash
   cd /home/pete/Documents/projects/Projects/News\ Intelligence
   ```

2. Start the system:
   ```bash
   ./start_system.sh
   ```

3. Verify all services are running:
   ```bash
   docker ps
   ```

4. Test web interface:
   - Open: http://localhost
   - Check all pages load correctly
   - Verify data is displaying

5. Test API endpoints:
   - Articles: http://localhost:8000/api/articles/
   - Storylines: http://localhost:8000/api/storylines/
   - RSS Feeds: http://localhost:8000/api/rss/feeds/

## 📁 Backup Location
- Full backup: `backups/20250928_201450/`
- Contains: docker-compose.yml, api/, web/, nginx/

## 🎯 Expected Results
- Web interface loads completely
- All navigation works
- Data displays correctly
- ML system ready (model may need re-download)
- All 5 RSS feeds configured
- 20+ articles loaded
- 1+ storylines available

## 🚨 If Issues Occur
1. Check container logs: `docker logs <container_name>`
2. Restore from backup if needed
3. Verify volume mounts are correct
4. Check network connectivity

## 📊 System Health
- PostgreSQL: Persistent data volume
- Redis: Persistent cache volume  
- Ollama: Model storage volume
- Web: Static files served via Nginx
- API: FastAPI with all routes configured
