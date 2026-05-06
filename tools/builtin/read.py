"""文件读取工具"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool, ToolParameter


def safe_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


class ReadTool(Tool):
    """读取文件内容，支持限制行数"""

    def __init__(self):
        super().__init__(name="read", description="Read a file and return its contents.")

    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters.get("path", "")
        limit = parameters.get("limit")
        if not path:
            return "Error: path is required"
        try:
            limit = int(limit) if limit is not None else None
        except (ValueError, TypeError):
            return "Error: limit must be an integer"
        return self._read(path, limit)

    def _read(self, path: str, limit: int = None) -> str:
        try:
            lines = safe_path(path).read_text(encoding="utf-8").splitlines()
            if limit and limit < len(lines):
                lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
            return "\n".join(lines)[:50000]
        except Exception as e:
            return f"Error: {e}"

    def get_parameters(self):
        return [
            ToolParameter(name="path", type="string", description="文件路径", required=True),
            ToolParameter(name="limit", type="integer", description="最多读取的行数", required=False),
        ]
