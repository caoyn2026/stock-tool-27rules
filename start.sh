#!/bin/bash
# 27条铁律选股决策系统 - 启动脚本 v2
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 杀旧进程
lsof -ti:5190 | xargs kill -9 2>/dev/null
sleep 1

# 激活Python环境
export PATH="/Users/cyn/Library/Python/3.9/bin:$PATH"

echo '🎯 启动27条铁律·选股决策系统...'
nohup /usr/bin/python3 server.py >> /tmp/stock-tool.log 2>&1 &

# 等待启动
for i in {1..10}; do
  if curl -s http://127.0.0.1:5190 > /dev/null 2>&1; then
    echo "✅ 服务已启动: http://127.0.0.1:5190"
    exit 0
  fi
  sleep 1
done
echo "❌ 启动失败，请检查 /tmp/stock-tool.log"
exit 1
