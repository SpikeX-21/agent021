"""文件写入工具"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool, ToolParameter


def safe_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


class WriteTool(Tool):
    """将内容写入文件，自动创建父目录"""

    def __init__(self):
        super().__init__(name="write", description="Write content to a file, creating parent directories as needed.")

    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters.get("path", "")
        content = parameters.get("content", "")
        if not path:
            return "Error: path is required"
        return self._write(path, content)

    def _write(self, path: str, content: str) -> str:
        try:
            fp = safe_path(path)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error: {e}"

    def get_parameters(self):
        return [
            ToolParameter(name="path", type="string", description="目标文件路径", required=True),
            ToolParameter(name="content", type="string", description="要写入的内容", required=True),
        ]
