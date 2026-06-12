# MemBrain - 个人知识助手

## 快速启动

```bash
pip install -r requirements.txt
cp .env.example .env  # 填入你的 API Key
uvicorn app.main:app --reload --port 8000
```

## 请求示例

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"test","password":"123456"}'

# 登录
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"123456"}'

# 聊天
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"messages":[{"role":"user","content":"你好"}],"user_id":1,"conversation_id":1}'
```
