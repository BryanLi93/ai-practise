#!/bin/sh
set -e

# 建表:create_all 幂等,只建缺的表,不动已有数据。
# compose 的 depends_on: service_healthy 已保证此刻 postgres 可连。
echo "[entrypoint] creating tables if not exist..."
python -m scripts.init_db

echo "[entrypoint] starting uvicorn..."
# exec:让 uvicorn 取代 shell 成为容器 PID 1,docker stop 的 SIGTERM 才能直达它优雅退出
#       (不加 exec,SIGTERM 发给 sh,uvicorn 收不到,只能等 10s 被强杀)
# --host 0.0.0.0:容器内必须监听所有网卡。你本地用 127.0.0.1 是因为同机访问;
#                容器里用 127.0.0.1 的话,宿主机的端口映射进不来,curl 会连接被拒
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
