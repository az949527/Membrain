"""
根据 eval_results.json 自动生成 REPORT.md

用法:
  1) 先跑 eval_retrieval.py 生成 eval_results/v2/eval_results.json
  2) python -m tests.generate_report

产出:
  eval_results/v2/REPORT.md
"""

import json
import os
from collections import Counter
from datetime import date


def load_results(path: str) -> dict | None:
    if not os.path.exists(path):
        print(f"[ERROR] 未找到结果文件: {path}")
        print("    请先运行 python -m tests.eval_retrieval")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generate(data: dict) -> str:
    details = data["details"]
    total = data["total"]
    recall = data["recall_at_3"]
    mrr = data["mrr"]

    hits = sum(1 for r in details if r["matched"])
    top1 = sum(1 for r in details if r["rank"] == 1)

    # 按场景分组
    topics = sorted(set(r["topic"] for r in details))
    topic_stats = []
    for t in topics:
        group = [r for r in details if r["topic"] == t]
        group_hits = sum(1 for r in group if r["matched"])
        topic_stats.append((t, group_hits, len(group)))

    # 失败分析
    failures = [r for r in details if not r["matched"] and r["topic"] != "边界无关"]
    irrelevant_errors = [
        r for r in details
        if r["topic"] == "边界无关" and r["matched"] == False
    ]

    lines = []
    lines.append(f"# RAG 评估基线报告\n")
    lines.append(f"日期: {date.today()}")
    lines.append(f"测试查询: {total} 条\n")
    lines.append("---\n")

    # 1. 总体指标
    lines.append("## 1. 检索质量评估\n")
    lines.append("### 总体指标\n")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| Recall@3 | {hits}/{total} = {recall:.1%} |")
    lines.append(f"| Top-1 命中率 | {top1}/{total} = {top1/total:.1%} |")
    lines.append(f"| MRR | {mrr:.4f} |\n")

    # 2. 按场景分析
    lines.append("### 按场景分析\n")
    lines.append("| 场景 | 命中率 | 说明 |")
    lines.append("|------|--------|------|")
    for t, h, n in topic_stats:
        ratio = h / n if n else 0
        if t == "边界无关":
            note = "正常拒绝" if ratio >= 0.75 else "阈值可能过低"
        elif ratio == 1.0:
            note = "全部命中"
        elif ratio >= 0.75:
            note = "表现良好"
        elif ratio >= 0.5:
            note = "部分漏检"
        else:
            note = "需要优化"
        lines.append(f"| {t} | {h}/{n} = {ratio:.0%} | {note} |")
    lines.append("")

    # 3. 失败分析
    lines.append("### 失败分析\n")
    if failures:
        lines.append("| 查询 | Score | 场景 | 可能原因 |")
        lines.append("|------|-------|------|---------|")
        for r in failures:
            score = r.get("top_score", 0)
            lines.append(f"| {r['query'][:20]}… | {score:.3f} | {r['topic']} | 含关键词的 chunk 未进入 top-k |")
        lines.append("")
    else:
        lines.append("所有非边界查询均已命中\n")

    if irrelevant_errors:
        lines.append(f"**边界误召回** ({len(irrelevant_errors)} 条)：")
        for r in irrelevant_errors:
            score = r.get("top_score", 0)
            lines.append(f"- `{r['query'][:20]}…` score={score:.3f}，阈值 0.3 过低导致误召回")
        lines.append("")

    # 4. v1 vs v2 对比（如果 v1 历史数据存在）
    v1_path = "eval_results/v1/eval_results.json"
    if os.path.exists(v1_path):
        with open(v1_path, encoding="utf-8") as f:
            v1 = json.load(f)
        v1_recall = v1["recall_at_3"]
        v1_mrr = v1["mrr"]
        diff_recall = recall - v1_recall
        diff_mrr = mrr - v1_mrr

        lines.append("## 2. v1 vs v2 对比\n")
        lines.append("| 指标 | v1 (18 条) | v2 (59 条) | 变化 |")
        lines.append("|------|-----------|-----------|------|")
        lines.append(f"| Recall@3 | {v1_recall:.1%} | {recall:.1%} | {diff_recall:+.1%} |")
        lines.append(f"| MRR | {v1_mrr:.4f} | {mrr:.4f} | {diff_mrr:+.4f} |")
        lines.append("")
        lines.append("> 注意：v1 和 v2 的数据集不同（v1=18 条, v2=59 条），\n")
        lines.append("> 指标差异部分源于数据集变化，不完全是 Reranker/HyDE 的效果。\n")
        lines.append("> 更准确的做法是在 59 条数据集上关掉 Reranker/HyDE 跑一次对照组。\n")

    lines.append("---\n")
    lines.append("_自动生成于 " + str(date.today()) + "_\n")

    return "\n".join(lines)


def main():
    path = "eval_results/v2/eval_results.json"
    data = load_results(path)
    if data is None:
        return

    report = generate(data)

    out_dir = "eval_results/v2"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "REPORT.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OK] 报告已生成: {out_path}")


if __name__ == "__main__":
    main()
