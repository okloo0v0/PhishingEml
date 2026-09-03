"""Dashboard statistics and offline model metrics."""

from __future__ import annotations

import json
from typing import Any

from src.config import get_settings
from src.db.repositories import StatisticsRepository
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import (
    KnowledgeArticle,
    ModelMetrics,
    to_jsonable,
)


class StatisticsService:
    def __init__(self, statistics_repo: StatisticsRepository) -> None:
        self.statistics_repo = statistics_repo

    def overview(self) -> dict[str, Any]:
        data = self.statistics_repo.overview()
        return to_jsonable(data)

    def model_metrics(self) -> dict[str, Any]:
        meta_path = get_settings().model_dir / "model_meta.json"
        if not meta_path.is_file():
            raise DomainError(ErrorCode.MODEL_NOT_READY, "模型元数据不存在", 503)
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise DomainError(
                ErrorCode.MODEL_NOT_READY, "模型元数据读取失败", 503
            ) from exc

        metrics = ModelMetrics(
            model_name=payload.get("model_name", ""),
            model_version=payload.get("model_version", ""),
            feature_version=payload.get("feature_version", ""),
            trained_at=payload.get("trained_at", ""),
            sample_counts={
                "train": payload.get("train_count", 0),
                "valid": payload.get("valid_count", 0),
                "test": payload.get("test_count", 0),
            },
            metrics={str(k): float(v) for k, v in payload.get("metrics", {}).items()},
            confusion_matrix=payload.get("test_confusion_matrix", [[], []]),
        )
        return to_jsonable(metrics)


KNOWLEDGE_ARTICLES: list[dict[str, Any]] = [
    {
        "id": 1,
        "category": "识别",
        "title": "如何识别钓鱼邮件",
        "summary": "关注发件人、链接和紧迫性语言",
        "content": "检查发件人域名是否与声称机构一致；把鼠标悬停在链接上核对真实地址；警惕要求立即操作的邮件。",
        "sort_order": 1,
    },
    {
        "id": 2,
        "category": "应对",
        "title": "收到可疑邮件怎么办",
        "summary": "不点击、不回复、不下载附件",
        "content": "不要点击链接或下载附件；通过官方渠道核实；如已泄露账号请立即修改密码。",
        "sort_order": 2,
    },
]


def list_knowledge(keyword: str | None, category: str | None) -> list[dict[str, Any]]:
    articles = KNOWLEDGE_ARTICLES
    if category:
        articles = [a for a in articles if a["category"] == category]
    if keyword:
        keyword = keyword.lower()
        articles = [
            a
            for a in articles
            if keyword in a["title"].lower() or keyword in a["summary"].lower()
        ]
    return to_jsonable(
        [
            KnowledgeArticle(
                id=a["id"],
                category=a["category"],
                title=a["title"],
                summary=a["summary"],
                content=a["content"],
                sort_order=a["sort_order"],
            )
            for a in articles
        ]
    )
