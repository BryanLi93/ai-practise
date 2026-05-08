"""
RAG Service 主入口。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from app.routers import upload, query
from app.config import settings
from app.db import engine


# ---------- 日志 ----------

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------- 生命周期 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的钩子。"""
    logger.info("RAG service starting up")
    yield
    logger.info("RAG service shutting down")
    await engine.dispose()

# ---------- 应用实例 ----------
app = FastAPI(
    title="Rag Service",
    description="一个最小可用的 RAG 问答服务",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------- 中间件:CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 学习阶段宽松,生产要限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 全局异常处理 ----------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底未捕获异常,避免 stacktrace 泄露给客户端。"""
    logger.exception("unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {type(exc).__name__}"},
    )

# ---------- 路由 ----------
app.include_router(upload.router)
app.include_router(query.router)

@app.get("/")
async def root():
    return {
        "service": "RAG Service",
        "version": "0.1.0",
        "docs": "/docs",
    }

@app.get("/health")
async def health():
    """健康检查端点(后续 Docker / k8s 健康探针用)。"""
    return {"status": "ok"}