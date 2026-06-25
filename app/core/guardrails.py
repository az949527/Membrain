"""
Guardrails / LLM 输出校验

三层校验：
1. validate_tool_calls — 校验 tool_calls 结构合法性
2. check_empty_result — 校验工具执行结果是否为空
3. 系统兜底 — 已有（try/except / 降级逻辑）
"""
import json
from app.core.logger import logger

# 必须与 tools.py 中的 TOOLS name 一一对应
VALID_TOOLS = {"rag_search", "graph_query", "web_search"}


def validate_tool_calls(tool_calls: list) -> list:
    """第 1 层：过滤非法 tool_calls，只返回合法的

    校验规则：
    - name 必须在 VALID_TOOLS 中
    - arguments 必须是合法 JSON

    参数:
        tool_calls: LLM 返回的原始 tool_calls 列表
    返回:
        合法的 tool_calls 列表（空列表 = 全部非法，需降级）
    """
    valid = []
    for tc in tool_calls:
        name = tc.function.name
        if name not in VALID_TOOLS:
            logger.warning("【Guardrails 拦截】非法工具名: %s", name)
            continue

        try:
            json.loads(tc.function.arguments)
        except (json.JSONDecodeError, TypeError):
            logger.warning("【Guardrails 拦截】参数解析失败: %s", tc.function.arguments)
            continue

        valid.append(tc)

    if len(valid) < len(tool_calls):
        logger.info("【Guardrails】%s 个 tool_calls 中 %s 个合法",
                     len(tool_calls), len(valid))

    return valid  # 空列表 → 降级


def check_empty_result(result, source_name: str = "") -> bool:
    """第 2 层：检查工具执行结果是否为空

    参数:
        result: 工具执行结果
        source_name: 工具名称（仅用于日志）
    返回:
        True = 结果非空，False = 结果为空
    """
    if not result:
        logger.warning("【Guardrails 空结果】%s 返回空，跳过该源", source_name)
        return False
    return True
