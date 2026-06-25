"""
MemBrain Streamlit Frontend
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

面试展示用前端，提供：
  - 登录 / 注册
  - 流式聊天（SSE + ReAct 推理过程可视化）
  - 文档管理（上传 / 列表 / 删除）
  - Agent 推理轨迹查看

用法：
  streamlit run streamlit_app.py
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generator

import httpx
import streamlit as st

# ── 配置 ──────────────────────────────────────────────────────────────────

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
PAGE_TITLE = "MemBrain AI"

# ── Session State 初始化 ──────────────────────────────────────────────────

_DEFAULT = {
    "token": None,
    "user": None,
    "conversations": [],
    "active_conv_id": None,
    "chat_messages": [],    # list[{"role": str, "content": str}]
    "last_tool_events": [], # 最近一轮 ReAct 的工具调用记录
}

for key, val in _DEFAULT.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── HTTP 工具 ─────────────────────────────────────────────────────────────

def _auth_headers() -> dict[str, str]:
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def _api_url(path: str) -> str:
    return f"{API_BASE}{path}"


def api_get(path: str) -> httpx.Response:
    """同步 GET 请求"""
    with httpx.Client(base_url=API_BASE, timeout=30) as c:
        return c.get(path, headers=_auth_headers())


def api_post(path: str, **kwargs) -> httpx.Response:
    """同步 POST 请求"""
    headers = {**_auth_headers(), **kwargs.pop("headers", {})}
    with httpx.Client(base_url=API_BASE, timeout=30) as c:
        return c.post(path, headers=headers, **kwargs)


def api_delete(path: str) -> httpx.Response:
    """同步 DELETE 请求"""
    with httpx.Client(base_url=API_BASE, timeout=30) as c:
        return c.delete(path, headers=_auth_headers())


# ── SSE 流式工具 ──────────────────────────────────────────────────────────

@dataclass
class ChatResult:
    """流式聊天结果"""
    text: str
    tool_events: list[dict]
    conversation_id: int | None = None


def stream_chat(
    messages: list[dict],
    conversation_id: int | None,
    token: str,
) -> Generator[str, None, ChatResult]:
    """异步消费 SSE 流，同步 yield 文本 token；结束后通过 StopIteration.value 返回 ChatResult。

    通过 threading + queue 桥接 async httpx → sync generator。
    token 参数在调用线程传入，避免后台线程访问 st.session_state。
    """
    token_queue: queue.Queue = queue.Queue()
    tool_events: list[dict] = []
    done_conv_id: int | None = conversation_id
    headers = {"Authorization": f"Bearer {token}"}

    async def _fetch():
        nonlocal done_conv_id
        timeout = httpx.Timeout(120.0, connect=30.0, read=120.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    _api_url("/api/v1/chat"),
                    json={
                        "messages": messages,
                        "conversation_id": conversation_id,
                    },
                    headers=headers,
                ) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        token_queue.put(
                            f"\n\n[服务器错误 {resp.status_code}: {error_body.decode()[:200]}]"
                        )
                        return
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        try:
                            data = json.loads(payload)
                            if data.get("done"):
                                done_conv_id = data.get("conversation_id", conversation_id)
                                break
                            elif "type" in data:
                                tool_events.append(data)
                                continue
                        except json.JSONDecodeError:
                            pass
                        token_queue.put(payload)
            except Exception as exc:
                token_queue.put(f"\n\n[连接错误: {exc}]")
            finally:
                token_queue.put(None)

    thread = threading.Thread(target=asyncio.run, args=(_fetch(),), daemon=True)
    thread.start()

    text_parts: list[str] = []
    while True:
        token = token_queue.get()
        if token is None:
            break
        text_parts.append(token)
        yield token

    thread.join()
    return ChatResult(
        text="".join(text_parts),
        tool_events=tool_events,
        conversation_id=done_conv_id if done_conv_id != conversation_id else None,
    )


# ── 页面组件 ──────────────────────────────────────────────────────────────

def show_tool_events():
    """在聊天消息下方展示 ReAct 工具调用过程"""
    events = st.session_state.last_tool_events
    if not events:
        return
    with st.expander("🧠 ReAct 推理过程", expanded=False):
        for ev in events:
            t = ev.get("type", "")
            content = ev.get("content", "")
            tool = ev.get("tool", "")
            query = ev.get("query", "")
            source = ev.get("source", "")
            summary = ev.get("summary", "")

            if t == "status":
                st.caption(f"⏳ {content}")
            elif t == "reasoning":
                st.info(f"💡 {content}")
            elif t == "tool_call":
                with st.container(border=True):
                    st.code(f"🔧 {tool}", language="")
                    if query:
                        st.text(f"  query: {query}")
            elif t == "tool_result":
                with st.container(border=True):
                    st.code(f"📥 {source}", language="")
                    if summary:
                        st.text(f"  summary: {summary[:120]}")
            st.divider()


# ── 登录页面 ──────────────────────────────────────────────────────────────

def login_page():
    st.title(PAGE_TITLE)
    tab_login, tab_register = st.tabs(["登录", "注册"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("邮箱", key="login_email")
            password = st.text_input("密码", type="password", key="login_pass")
            if st.form_submit_button("登录", use_container_width=True):
                if not email or not password:
                    st.error("请填写邮箱和密码")
                    return
                resp = api_post("/api/v1/auth/token", json={
                    "email": email,
                    "password": password,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    me = api_get("/api/v1/auth/me")
                    if me.status_code == 200:
                        st.session_state.user = me.json()
                    st.rerun()
                else:
                    try:
                        detail = resp.json().get("detail", resp.text)
                    except Exception:
                        detail = resp.text
                    st.error(f"登录失败: {detail}")

    with tab_register:
        with st.form("register_form"):
            reg_email = st.text_input("邮箱", key="reg_email")
            reg_user = st.text_input("用户名")
            reg_pass = st.text_input("密码", type="password", key="reg_pass")
            if st.form_submit_button("注册", use_container_width=True):
                if not reg_email or not reg_user or not reg_pass:
                    st.error("请填写所有字段")
                    return
                resp = api_post("/api/v1/auth/register", json={
                    "email": reg_email,
                    "username": reg_user,
                    "password": reg_pass,
                })
                if resp.status_code == 201:
                    st.success("注册成功，请登录")
                    st.rerun()
                else:
                    try:
                        detail = resp.json().get("detail", resp.text)
                    except Exception:
                        detail = resp.text
                    st.error(f"注册失败: {detail}")


# ── 聊天页面 ──────────────────────────────────────────────────────────────

def chat_page():
    st.title("💬 对话")

    # ─ 侧栏：历史对话列表 ─
    with st.sidebar:
        st.subheader("历史对话")
        if st.button("📄 刷新列表", use_container_width=True):
            _load_conversations()
        if st.button("➕ 新对话", use_container_width=True):
            st.session_state.active_conv_id = None
            st.session_state.chat_messages = []
            st.rerun()

        for conv in st.session_state.conversations:
            cid = conv["id"]
            title = conv.get("title", f"对话 #{cid}")
            active = cid == st.session_state.active_conv_id
            if st.button(
                f"{'●' if active else '○'} {title[:30]}",
                key=f"conv_{cid}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                _switch_conversation(cid)

    # ─ 聊天主区域 ─
    conv_id = st.session_state.active_conv_id

    # 显示历史消息
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 显示上一轮工具事件（如果有）
    if conv_id and st.session_state.last_tool_events:
        show_tool_events()

    # 输入框
    if prompt := st.chat_input("输入你的问题..."):
        _handle_user_message(prompt, conv_id)


def _load_conversations():
    resp = api_get("/api/v1/conversations")
    if resp.status_code == 200:
        st.session_state.conversations = resp.json()


def _switch_conversation(cid: int):
    st.session_state.active_conv_id = cid
    st.session_state.last_tool_events = []
    # 加载该对话的消息历史（从 API）
    resp = api_get(f"/api/v1/conversations")
    if resp.status_code == 200:
        # 当前 API 只返回会话列表，不返回消息详情
        # 重置消息显示，让用户在新消息里继续
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "继续之前的对话，请问有什么问题？"}
        ]
    st.rerun()


def _handle_user_message(prompt: str, conv_id: int | None):
    # 追加用户消息
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    st.session_state.last_tool_events = []

    with st.chat_message("user"):
        st.markdown(prompt)

    # 准备 API 消息格式
    api_messages = [{"role": m["role"], "content": m["content"]}
                    for m in st.session_state.chat_messages]

    with st.chat_message("assistant"):
        placeholder = st.empty()
        collected = ""
        chat_result = None

        try:
            gen = stream_chat(api_messages, conv_id, st.session_state.token)
            # 手动迭代以捕获 generator return value
            try:
                while True:
                    text_token = next(gen)
                    collected += text_token
                    placeholder.markdown(collected + "▌")
            except StopIteration as e:
                chat_result = e.value  # ChatResult(text, tool_events, conversation_id)

            placeholder.markdown(collected)

            # 更新 conversation_id
            if chat_result and chat_result.conversation_id:
                st.session_state.active_conv_id = chat_result.conversation_id
                st.session_state.last_tool_events = chat_result.tool_events
                _load_conversations()

        except Exception as e:
            placeholder.error(f"请求失败: {e}")
            collected = f"[错误] {e}"

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": collected}
        )

        # 展示工具调用
        if chat_result and chat_result.tool_events:
            show_tool_events()

        st.rerun()


# ── 文档管理页面 ──────────────────────────────────────────────────────────

def documents_page():
    st.title("📁 文档管理")

    # 上传区域
    with st.container(border=True):
        st.subheader("上传文档")
        uploaded = st.file_uploader(
            "选择文件（.txt / .md / .pdf）",
            type=["txt", "md", "pdf"],
            label_visibility="collapsed",
        )
        if uploaded and st.button("上传", type="primary", use_container_width=True):
            _upload_document(uploaded)

    # 文档列表
    st.divider()
    st.subheader("已上传文档")
    _render_document_list()


def _upload_document(uploaded):
    with st.spinner("正在上传并处理..."):
        files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
        resp = api_post("/api/v1/documents/upload", files=files)
    if resp.status_code == 200:
        data = resp.json()
        st.success(f"✅ 上传成功：{data['filename']}（status: {data['status']}）")
        time.sleep(0.5)
        st.rerun()
    else:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        st.error(f"上传失败: {detail}")


def _render_document_list():
    resp = api_get("/api/v1/documents/")
    if resp.status_code != 200:
        st.error("获取文档列表失败")
        return

    docs = resp.json()
    if not docs:
        st.info("还没有上传文档")
        return

    for doc in docs:
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
            col1.text(doc["filename"])
            col2.text(doc.get("file_type", ""))
            col3.text(f"{doc['file_size'] // 1024} KB" if doc.get("file_size") else "")
            col4.text(doc.get("status", ""))
            if col5.button("🗑️", key=f"del_{doc['id']}"):
                _delete_document(doc["id"])


def _delete_document(doc_id: int):
    resp = api_delete(f"/api/v1/documents/{doc_id}")
    if resp.status_code == 204:
        st.success("已删除")
        time.sleep(0.5)
        st.rerun()
    else:
        st.error("删除失败")


# ── Agent 轨迹页面 ────────────────────────────────────────────────────────

def traces_page():
    st.title("🔍 Agent 推理轨迹")

    resp = api_get("/api/v1/agent/traces?limit=20")
    if resp.status_code != 200:
        st.error("获取轨迹失败")
        return

    traces = resp.json()
    if not traces:
        st.info("暂无 Agent 推理记录")
        return

    for t in traces:
        created = t.get("created_at", "")[:19].replace("T", " ")
        with st.expander(
            f"[{created}] Q: {t.get('question', '')[:60]}"
            f" {'─' * 10} "
            f"{t.get('duration_ms', 0)}ms"
        ):
            st.text(f"来源: {t.get('sources_selected', 'N/A')}")
            st.text(f"轮次: {t.get('rounds', 0)}")
            context = t.get("context_used", "")
            if context:
                st.text_area("上下文片段", context[:500], height=100)


# ── 侧边栏 + 主入口 ──────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if not st.session_state.token:
        login_page()
        return

    # ─ 已登录：侧边栏 ─
    user = st.session_state.user or {}
    username = user.get("username", user.get("email", "用户"))

    with st.sidebar:
        st.markdown(f"### 👤 {username}")
        st.caption(f"Token: {st.session_state.token[:20]}...")

        page = st.radio(
            "导航",
            ["💬 对话", "📁 文档", "🔍 轨迹"],
            label_visibility="collapsed",
        )

        st.divider()
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()

    # ─ 页面路由 ─
    if page == "💬 对话":
        chat_page()
    elif page == "📁 文档":
        documents_page()
    elif page == "🔍 轨迹":
        traces_page()


if __name__ == "__main__":
    main()
