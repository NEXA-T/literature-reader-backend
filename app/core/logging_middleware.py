import time
from fastapi import Request
from loguru import logger


async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} | "
        f"{duration_ms:.1f}ms | IP={client_ip}"
    )

    return response