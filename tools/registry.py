"""工具注册表 - HelloAgents原生工具系统"""

from typing import Dict,  Optional, Any, Callable, Union
from .base import Tool
from .response import ToolResponse, ToolStatus

class ToolRegistry:
    """
    HelloAgents工具注册表

    提供工具的注册、管理和执行功能。
    支持两种工具注册方式：
    1. Tool对象注册（推荐）
    2. 函数直接注册（简便）
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._functions: dict[str, dict[str, Any]] = {}

    def register_tool(self, tool: Tool, auto_expand: bool = True):
        """
        注册Tool对象

        Args:
            tool: Tool实例
            auto_expand: 是否自动展开可展开的工具（默认True）
        """
        # 检查工具是否可展开
        if auto_expand and hasattr(tool, 'expandable') and tool.expandable:
            expanded_tools = tool.get_expanded_tools()
            if expanded_tools:
                # 注册所有展开的子工具
                for sub_tool in expanded_tools:
                    if sub_tool.name in self._tools:
                        print(f"⚠️ 警告：工具 '{sub_tool.name}' 已存在，将被覆盖。")
                    self._tools[sub_tool.name] = sub_tool
                print(f"✅ 工具 '{tool.name}' 已展开为 {len(expanded_tools)} 个独立工具")
                return

        # 普通工具或不展开的工具
        if tool.name in self._tools:
            print(f"⚠️ 警告：工具 '{tool.name}' 已存在，将被覆盖。")

        self._tools[tool.name] = tool
        print(f"✅ 工具 '{tool.name}' 已注册。")

    def register_function(self, name: str, description: str, func: Callable[[str], str]):
        """
        直接注册函数作为工具（简便方式）

        Args:
            name: 工具名称
            description: 工具描述
            func: 工具函数，接受字符串参数，返回字符串结果
        """
        if name in self._functions:
            print(f"⚠️ 警告：工具 '{name}' 已存在，将被覆盖。")

        self._functions[name] = {
            "description": description,
            "func": func
        }
        print(f"✅ 工具 '{name}' 已注册。")

    def unregister(self, name: str):
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            print(f"🗑️ 工具 '{name}' 已注销。")
        elif name in self._functions:
            del self._functions[name]
            print(f"🗑️ 工具 '{name}' 已注销。")
        else:
            print(f"⚠️ 工具 '{name}' 不存在。")

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取Tool对象"""
        return self._tools.get(name)

    def get_function(self, name: str) -> Optional[Callable]:
        """获取工具函数"""
        func_info = self._functions.get(name)
        return func_info["func"] if func_info else None

    def execute_tool(self, name: str, parameters: Dict[str, Any]) -> str:
        """
        执行工具（向后兼容接口，返回字符串视图）

        Args:
            name: 工具名称
            parameters: 工具参数字典（兼容 Anthropic SDK block.input 对象）

        Returns:
            工具执行结果字符串。若工具返回 ToolResponse：
            - success → 返回 text
            - partial → 返回 "[partial] text"
            - error   → 返回 "[error CODE] message"
        """
        resp = self.execute_tool_structured(name, parameters)
        return self._response_to_text(resp)

    def execute_tool_structured(self, name: str, parameters: Dict[str, Any]) -> ToolResponse:
        """
        执行工具并始终返回结构化 ToolResponse。

        工具可返回 ToolResponse 或 str；str 结果会被包装成 success/error：
        包含 "Error" / "错误" 前缀的字符串会被识别为 error，其余为 success。

        Args:
            name: 工具名称
            parameters: 工具参数字典

        Returns:
            ToolResponse 对象
        """
        # 确保 parameters 是普通 dict（兼容 Anthropic SDK 返回的类 dict 对象）
        if not isinstance(parameters, dict):
            parameters = dict(parameters)

        # 优先查找 Tool 对象
        if name in self._tools:
            tool = self._tools[name]
            missing = [
                p.name for p in tool.get_parameters()
                if p.required and p.name not in parameters
            ]
            if missing:
                return ToolResponse.error(
                    code="MISSING_PARAM",
                    message=f"工具 '{name}' 缺少必需参数: {', '.join(missing)}",
                    context={"tool": name, "missing": missing},
                )
            try:
                raw = tool.run(parameters)
            except Exception as e:
                return ToolResponse.error(
                    code="TOOL_EXCEPTION",
                    message=f"执行工具 '{name}' 时发生异常: {str(e)}",
                    context={"tool": name, "exception": type(e).__name__},
                )
            return self._normalize_result(name, raw)

        # 查找函数工具
        elif name in self._functions:
            func = self._functions[name]["func"]
            try:
                raw = func(parameters)
            except Exception as e:
                return ToolResponse.error(
                    code="TOOL_EXCEPTION",
                    message=f"执行工具 '{name}' 时发生异常: {str(e)}",
                    context={"tool": name, "exception": type(e).__name__},
                )
            return self._normalize_result(name, raw)

        return ToolResponse.error(
            code="TOOL_NOT_FOUND",
            message=f"未找到名为 '{name}' 的工具。",
            context={"tool": name},
        )

    @staticmethod
    def _normalize_result(name: str, raw: Any) -> ToolResponse:
        """把工具的原始返回值规范化为 ToolResponse"""
        if isinstance(raw, ToolResponse):
            return raw
        text = raw if isinstance(raw, str) else str(raw)
        # 兼容旧式字符串错误：以 "Error" / "错误" 开头视作 error
        stripped = text.lstrip()
        if stripped.startswith("Error") or stripped.startswith("错误"):
            return ToolResponse.error(
                code="LEGACY_ERROR",
                message=text,
                context={"tool": name},
            )
        return ToolResponse.success(text=text, context={"tool": name})

    @staticmethod
    def _response_to_text(resp: ToolResponse) -> str:
        """把 ToolResponse 转为给 LLM 阅读的字符串视图"""
        if resp.status is ToolStatus.SUCCESS:
            return resp.text
        if resp.status is ToolStatus.PARTIAL:
            return f"[partial] {resp.text}"
        code = (resp.error_info or {}).get("code", "ERROR")
        return f"[error {code}] {resp.text}"

    def get_tools_description(self) -> str:
        """
        获取所有可用工具的格式化描述字符串

        Returns:
            工具描述字符串，用于构建提示词
        """
        descriptions = []

        # Tool对象描述
        for tool in self._tools.values():
            descriptions.append(f"- {tool.name}: {tool.description}")

        # 函数工具描述
        for name, info in self._functions.items():
            descriptions.append(f"- {name}: {info['description']}")

        return "\n".join(descriptions) if descriptions else "暂无可用工具"

    def list_tools(self) -> list[str]:
        """列出所有工具名称"""
        return list(self._tools.keys()) + list(self._functions.keys())

    def get_all_tools(self) -> list[Tool]:
        """获取所有Tool对象"""
        return list(self._tools.values())

    def clear(self):
        """清空所有工具"""
        self._tools.clear()
        self._functions.clear()
        print("🧹 所有工具已清空。")

    def get_all_tools_to_cc(self) -> list[dict[str, Any]]:
        # """获取所有工具的 Claude 格式 schema 列表"""
        return [tool.to_cc_schema() for tool in self._tools.values()]

# 全局工具注册表
global_registry = ToolRegistry()