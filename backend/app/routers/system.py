import shutil
import time

from fastapi import APIRouter, Depends

from .. import config, db, providers, security

router = APIRouter(prefix="/api/system", tags=["system"])
START = time.time()


def rss_mb() -> float | None:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None


@router.get("/status")
def status(user=Depends(security.auth)):
    try:
        db.one("SELECT 1 AS ok")
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    svc = providers.SearchService(db.get_settings())
    du = shutil.disk_usage(config.DATA_DIR)
    return {
        "version": config.VERSION, "uptime_s": int(time.time() - START), "database": {"ok": db_ok, "size_kb": round(config.DB_PATH.stat().st_size / 1024, 1) if config.DB_PATH.exists() else 0},
        "memory_mb": rss_mb(), "disk": {"free_gb": round(du.free / 1e9, 1), "total_gb": round(du.total / 1e9, 1)},
        "providers": {"searxng": bool(svc.searxng), "brave": bool(svc.brave), "wikipedia": True},
        "ocr": shutil.which("tesseract") is not None,
        "search_ready": bool(svc.configured()), "max_upload_mb": config.MAX_UPLOAD_MB,
    }
