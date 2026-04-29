"""bash工具"""

from typing import Dict, Any

from ..base import Tool

class BashTool(Tool):
    """agent bash工具 - 通过执行shell命令来完成任务"""
    
    
    def __init__(self):
        super().__init__(
            name="bash",
            description="Run a shell command."
        )
    
    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行shell命令

        Args:
            parameters: 包含command参数的字典

        Returns:
            命令执行结果
        """
        # 支持两种参数格式：command 和 expression
        command = parameters.get("command", "") or parameters.get("expression", "")
        if not command:
            return "错误：命令不能为空"

        print(f"🧮 正在执行命令: {command}")

        try:
            # 解析并执行命令
            result = self.run_bash(command)
            print(f"✅ 命令执行结果: {result}")
            return result
        except Exception as e:
            error_msg = f"命令执行失败: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def get_parameters(self):
        """获取工具参数定义"""
        from ..base import ToolParameter
        return [
            ToolParameter(
                name="command",
                type="string",
                description="要执行的shell命令",
                required=True
            )
        ]
    
    def run_bash(command: str) -> str:
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
        if any(d in command for d in dangerous):
            return "Error: Dangerous command blocked"
        try:
            r = subprocess.run(command, shell=True, cwd=WORKDIR,
                            capture_output=True, text=True, timeout=120)
            out = (r.stdout + r.stderr).strip()
            return out[:50000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Timeout (120s)"   

# -----------------------------------------------------------------------------
