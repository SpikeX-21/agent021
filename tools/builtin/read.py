"""文件读取工具"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool, ToolParameter
from ..response import ToolResponse


def safe_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


class ReadTool(Tool):
    """读取文件内容，支持限制行数"""

    MAX_BYTES = 50000

    def __init__(self):
        super().__init__(name="read", description="Read a file and return its contents.")

    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        path = parameters.get("path", "")
        limit = parameters.get("limit")
        if not path:
            return ToolResponse.error(code="INVALID_PARAM", message="path is required")
        try:
            limit = int(limit) if limit is not None else None
        except (ValueError, TypeError):
            return ToolResponse.error(code="INVALID_PARAM", message="limit must be an integer")
        return self._read(path, limit)

    def _read(self, path: str, limit: int = None) -> ToolResponse:
        try:
            fp = safe_path(path)
            full = fp.read_text(encoding="utf-8")
            lines = full.splitlines()
            total_lines = len(lines)

            truncated_lines = False
            if limit and limit < total_lines:
                lines = lines[:limit] + [f"... ({total_lines - limit} more)"]
                truncated_lines = True

            text = "\n".join(lines)
            truncated_bytes = False
            if len(text) > self.MAX_BYTES:
                text = text[:self.MAX_BYTES]
                truncated_bytes = True

            stats = {"total_lines": total_lines, "returned_bytes": len(text)}
            context = {"path": str(fp)}

            if truncated_lines or truncated_bytes:
                reason = []
                if truncated_lines:
                    reason.append(f"limit={limit}")
                if truncated_bytes:
                    reason.append(f"max_bytes={self.MAX_BYTES}")
                return ToolResponse.partial(
                    text=text,
                    data={"truncated": True, "reason": ",".join(reason)},
                    stats=stats,
                    context=context,
                )
            return ToolResponse.success(text=text, stats=stats, context=context)
        except FileNotFoundError as e:
            return ToolResponse.error(code="FILE_NOT_FOUND", message=str(e),
                                      context={"path": path})
        except PermissionError as e:
            return ToolResponse.error(code="PERMISSION_DENIED", message=str(e),
                                      context={"path": path})
        except Exception as e:
            return ToolResponse.error(code="READ_FAILED", message=str(e),
                                      context={"path": path})

    def get_parameters(self):
        return [
            ToolParameter(name="path", type="string", description="文件路径", required=True),
            ToolParameter(name="limit", type="integer", description="最多读取的行数", required=False),
        ]
