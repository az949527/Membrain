# MemBrain 部署指南

## 环境要求

- Python 3.10+
- Docker 及 Docker Compose（用于 Neo4j + Redis）
- AutoDL 或其他 Linux 云服务器（推荐 8GB+ 显存 GPU 实例）

---

## AutoDL 部署步骤

### 1. 创建实例

- 进入 AutoDL 控制台 → 创建实例
- **镜像**：选择 PyTorch 2.x / CUDA 12+ 的镜像（如 `PyTorch 2.5.0 / Python 3.12 / CUDA 12.4`）
- **数据盘**：项目代码放在 `/root/autodl-tmp/`（持久化存储，重启不丢）
- **GPU**：显存 8GB+ 即可（文本模型对显存要求低，如需运行 embedding 模型在本地则建议 16GB+）

### 2. 拉取代码

```bash
cd /root/autodl-tmp/
git clone <你的仓库地址> membrain
cd membrain
```

### 3. 创建虚拟环境并安装依赖

```bash
# 用 conda（镜像自带）
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
```

> **国内网络注意**：如果遇到 huggingface.co 下载慢或超时，设置镜像：
> ```bash
> export HF_ENDPOINT=https://hf-mirror.com
> ```

### 4. 启动基础设施（Neo4j + Redis）

```bash
docker-compose up -d

# 确认两个容器都在运行
docker ps
```

预期看到 `membrain-neo4j` 和 `membrain-redis` 两个容器正常运行。

### 5. 配置环境变量

```bash
cp .env.example .env
vi .env
```

至少需要修改的配置：

| 配置项 | 说明 | 必填 |
|--------|------|:----:|
| `LLM_API_KEY` | 你的 LLM API 密钥（如 DeepSeek / OpenAI） | ✅ |
| `SECRET_KEY` | 改为随机字符串（用于 JWT 签名） | ✅ |
| `NEO4J_PASSWORD` | 需与 `docker-compose.yml` 保持一致 | ✅ |

其他配置保持默认即可。

### 6. 启动服务

**后端 API：**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**前端界面（可选）：**
```bash
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0

看到如下日志表示启动成功：
```
INFO:     Started server process [xxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

> **后台运行**：使用 `nohup` 或 `tmux` 让服务在退出 SSH 后继续运行：
> ```bash
> nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
> ```

### 7. 端口映射（AutoDL 特有）

1. 进入 AutoDL 控制台 → 选中你的实例
2. 找到 **"自定义服务"** 或 **"端口映射"**
3. 添加映射：
   - 容器端口 `8000` → 公网端口（API）
   - 容器端口 `8501` → 公网端口（前端，如果部署了 Streamlit）
4. 得到公网访问地址，形如 `https://xxxxx.autodl.com`

### 8. 验证部署

```bash
# 测试聊天接口
curl -X POST "http://localhost:8000/chat/send" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": 1, "content": "你好，请介绍一下 MemBrain"}'

# 如果返回 401 未授权，先登录获取 token
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo123"}'
```

---

## Docker Compose 参考

项目使用 Docker Compose 管理 Neo4j 和 Redis：

```yaml
version: "3"
services:
  neo4j:
    image: neo4j:5
    ports:
      - "7474:7474"   # Web 控制台
      - "7687:7687"   # Bolt 协议
    environment:
      NEO4J_AUTH: neo4j/password123

  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

---

## 常见问题

### Q: Neo4j 连不上怎么办？
检查 `docker ps` 确认容器在运行，然后：
```bash
docker logs membrain-neo4j  # 查看 Neo4j 日志
```
首次启动 Neo4j 可能需要 10-20 秒初始化。

### Q: Redis 连不上怎么办？
```bash
docker logs membrain-redis  # 查看 Redis 日志
```
Redis 不可用时，MemBrain 会自动跳过缓存，不影响核心聊天功能。

### Q: 换一个 LLM 怎么配置？
修改 `.env` 中的三项：
```bash
LLM_API_KEY=你的新密钥
LLM_BASE_URL=https://api.new-provider.com
LLM_MODEL=new-model-name
```
无需修改代码。

### Q: huggingface 模型下载失败？
设置镜像后重试：
```bash
export HF_ENDPOINT=https://hf-mirror.com
# 然后重新运行服务
```
