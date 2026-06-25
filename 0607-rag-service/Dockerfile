# slim = Debian + glibc:torch 等包的预编译 wheel 都给 glibc,alpine(musl)会退化成源码编译
FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE:容器里不写 .pyc(没意义还脏)
# PYTHONUNBUFFERED:stdout/stderr 不缓冲,docker logs 才能实时看到日志
# PIP_INDEX_URL:走清华源,装依赖快
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# WORKDIR 用 /code 而不是 /app,避开和 Python 包名 app/ 撞成 /app/app 的混淆
WORKDIR /code

# ---------- 依赖层(改代码不会动这两层,复用缓存) ----------
# rerank 改走 SiliconFlow API 后,本地不再需要 torch / sentence-transformers,
# 镜像随之瘦掉 ~4GB(也不再需要 libgomp1)。
COPY requirements.txt .
RUN pip install -r requirements.txt

# tiktoken 的 cl100k_base 词表:运行时(import app.chunking 即触发)会去 Azure blob 下载,
# 容器内网络常不通(实测 SSL EOF)。把宿主机已下好的词表烤进镜像,
# 设 TIKTOKEN_CACHE_DIR 指过去,运行时零联网。放依赖层,改业务代码不会重建这层。
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken_cache
COPY tiktoken_cache/ /opt/tiktoken_cache/

# ---------- 代码层(改代码只重建以下层) ----------
COPY app ./app
COPY scripts ./scripts
COPY web ./web
COPY entrypoint.sh .

# 文档用途,声明容器监听 8000(不实际开端口,开端口靠 compose 的 ports)
EXPOSE 8000

ENTRYPOINT ["sh", "entrypoint.sh"]
