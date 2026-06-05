"""
RAG Service 主入口。
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


from app.routers import upload, query, conversation
from app.config import settings
from app.db import engine
from app.logging_config import configure_logging


# ---------- 日志 ----------
# 必须在任何 logger 使用前先配好管道
configure_logging()
logger = structlog.get_logger()

# ---------- 生命周期 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的钩子。"""
    logger.info("startup")
    yield
    logger.info("shutdown")
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

# ---------- 中间件:trace_id + 请求耗时 ----------
@app.middleware("http")
async def trace_context_middleware(request: Request, call_next):
    """给每个请求绑定 trace_id,使本次请求的所有日志自动带上它;
    请求结束打一条 access 日志(method/path/status/耗时),并通过响应头回传 trace_id。"""
    trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:12]
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        response.headers["X-Trace-Id"] = trace_id
        return response
    finally:
        # 请求结束清掉,避免 trace_id 残留到下一个复用的协程上下文
        structlog.contextvars.clear_contextvars()

# ---------- 全局异常处理 ----------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底未捕获异常,避免 stacktrace 泄露给客户端。"""
    trace_id = structlog.contextvars.get_contextvars().get("trace_id")
    logger.exception("unhandled_exception", method=request.method, url=str(request.url))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {type(exc).__name__}", "trace_id": trace_id},
    )

# ---------- 路由 ----------
app.include_router(upload.router)
app.include_router(query.router)
app.include_router(conversation.router)

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

# ---------- 静态前端 ----------
# 把 web/ 挂到 /ui,和 API 同源,前端 fetch 用相对路径即可(无 CORS 问题)。
# html=True:访问 /ui/ 时自动返回 index.html。放在所有 API 路由之后挂载。
_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if _WEB_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=_WEB_DIR, html=True), name="ui")