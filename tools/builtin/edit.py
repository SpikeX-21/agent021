"""文件编辑工具"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool, ToolParameter
from ..response import ToolResponse


def safe_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


class EditTool(Tool):
    """替换文件中第一处匹配的文本"""

    def __init__(self):
        super().__init__(name="edit", description="Replace the first occurrence of old_text with new_text in a file.")

    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        path = parameters.get("path", "")
        old_text = parameters.get("old_text", "")
        new_text = parameters.get("new_text", "")
        if not path:
            return ToolResponse.error(code="INVALID_PARAM", message="path is required")
        if not old_text:
            return ToolResponse.error(code="INVALID_PARAM", message="old_text is required")
        return self._edit(path, old_text, new_text)

    def _edit(self, path: str, old_text: str, new_text: str) -> ToolResponse:
        try:
            fp = safe_path(path)
            c = fp.read_text(encoding="utf-8")
            if old_text not in c:
                return ToolResponse.error(
                    code="TEXT_NOT_FOUND",
                    message=f"Text not found in {path}",
                    context={"path": str(fp)},
                )
            occurrences = c.count(old_text)
            fp.write_text(c.replace(old_text, new_text, 1), encoding="utf-8")
            stats = {"total_matches": occurrences, "replaced": 1}
            context = {"path": str(fp)}
            if occurrences > 1:
                return ToolResponse.partial(
                    text=f"Edited {path} (replaced 1 of {occurrences} matches)",
                    data={"remaining_matches": occurrences - 1},
                    stats=stats,
                    context=context,
                )
            return ToolResponse.success(text=f"Edited {path}", stats=stats, context=context)
        except FileNotFoundError as e:
            return ToolResponse.error(code="FILE_NOT_FOUND", message=str(e),
                                      context={"path": path})
        except PermissionError as e:
            return ToolResponse.error(code="PERMISSION_DENIED", message=str(e),
                                      context={"path": path})
        except Exception as e:
            return ToolResponse.error(code="EDIT_FAILED", message=str(e),
                                      context={"path": path})

    def get_parameters(self):
        return [
            ToolParameter(name="path", type="string", description="目标文件路径", required=True),
            ToolParameter(name="old_text", type="string", description="要被替换的原始文本", required=True),
            ToolParameter(name="new_text", type="string", description="替换后的新文本", required=True),
        ]
