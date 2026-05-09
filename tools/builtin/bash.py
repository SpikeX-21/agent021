"""bash工具"""

from typing import Dict, Any
import subprocess
import os
from ..base import Tool, ToolParameter
from ..response import ToolResponse


class BashTool(Tool):
    """agent bash工具 - 通过执行shell命令来完成任务"""

    MAX_BYTES = 50000
    TIMEOUT_SEC = 120
    DANGEROUS = ("rm -rf /", "sudo", "shutdown", "reboot", "> /dev/")

    def __init__(self):
        super().__init__(
            name="bash",
            description="Run a shell command."
        )

    def run(self, parameters: Dict[str, Any]) -> ToolResponse:
        """
        执行shell命令

        Args:
            parameters: 包含command参数的字典

        Returns:
            ToolResponse 结构化响应
        """
        command = parameters.get("command", "")
        if not command:
            return ToolResponse.error(code="INVALID_PARAM", message="命令不能为空")

        print(f"🧮 正在执行命令: {command}")

        if any(d in command for d in self.DANGEROUS):
            return ToolResponse.error(
                code="DANGEROUS_COMMAND",
                message=f"Dangerous command blocked: {command}",
                context={"command": command},
            )

        try:
            r = subprocess.run(
                command, shell=True, cwd=os.getcwd(),
                capture_output=True, text=True, timeout=self.TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            return ToolResponse.error(
                code="TIMEOUT",
                message=f"Timeout ({self.TIMEOUT_SEC}s)",
                context={"command": command, "timeout": self.TIMEOUT_SEC},
            )
        except Exception as e:
            return ToolResponse.error(
                code="EXEC_FAILED",
                message=str(e),
                context={"command": command},
            )

        out = (r.stdout + r.stderr).strip()
        truncated = False
        if len(out) > self.MAX_BYTES:
            out = out[:self.MAX_BYTES]
            truncated = True
        text = out if out else "(no output)"
        print(f"✅ 命令执行结果: {text}")

        stats = {"returncode": r.returncode, "bytes": len(out)}
        context = {"command": command}

        if r.returncode != 0:
            return ToolResponse.partial(
                text=text,
                data={"returncode": r.returncode},
                stats=stats,
                context=context,
            )
        if truncated:
            return ToolResponse.partial(
                text=text,
                data={"truncated": True, "max_bytes": self.MAX_BYTES},
                stats=stats,
                context=context,
            )
        return ToolResponse.success(text=text, stats=stats, context=context)

    def get_parameters(self):
        from ..base import ToolParameter
        return [
            ToolParameter(
                name="command",
                type="string",
                description="要执行的shell命令",
                required=True
            )
        ]

# -----------------------------------------------------------------------------
