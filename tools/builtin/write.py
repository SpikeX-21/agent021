"""文件写入工具"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool, ToolParameter
from ..response import ToolResponse


def safe_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


class WriteTool(Tool):
    """将内容写入文件，自动创建父目录"""

    def __init__(self):
        super().__init__(name="write", description="Write content to a file, creating parent directories as needed.")

    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        path = parameters.get("path", "")
        content = parameters.get("content", "")
        if not path:
            return ToolResponse.error(code="INVALID_PARAM", message="path is required")
        return self._write(path, content)

    def _write(self, path: str, content: str) -> ToolResponse:
        try:
            fp = safe_path(path)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
            return ToolResponse.success(
                text=f"Wrote {len(content)} bytes to {path}",
                data={"bytes_written": len(content)},
                context={"path": str(fp)},
            )
        except PermissionError as e:
            return ToolResponse.error(code="PERMISSION_DENIED", message=str(e),
                                      context={"path": path})
        except Exception as e:
            return ToolResponse.error(code="WRITE_FAILED", message=str(e),
                                      context={"path": path})

    def get_parameters(self):
        return [
            ToolParameter(name="path", type="string", description="目标文件路径", required=True),
            ToolParameter(name="content", type="string", description="要写入的内容", required=True),
        ]
