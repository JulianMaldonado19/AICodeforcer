"""API Logger - 完整记录所有API请求和响应。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from google.genai import types


def _serialize_part(part: types.Part) -> dict[str, Any]:
    """序列化单个Part对象。"""
    result: dict[str, Any] = {}

    if part.text is not None:
        result["text"] = part.text

    if part.function_call is not None:
        fc = part.function_call
        result["function_call"] = {
            "name": fc.name,
            "args": dict(fc.args) if fc.args else {},
        }

    if part.function_response is not None:
        fr = part.function_response
        result["function_response"] = {
            "name": fr.name,
            "response": dict(fr.response) if fr.response else {},
        }

    # 检查是否是思考内容
    if hasattr(part, 'thought') and part.thought:
        result["thought"] = True

    return result


def _serialize_content(content: types.Content) -> dict[str, Any]:
    """序列化Content对象。"""
    return {
        "role": content.role,
        "parts": [_serialize_part(p) for p in content.parts] if content.parts else [],
    }


def _serialize_contents(contents: list[types.Content]) -> list[dict[str, Any]]:
    """序列化contents列表。"""
    return [_serialize_content(c) for c in contents]


def _serialize_candidate(candidate) -> dict[str, Any]:
    """序列化Candidate对象。"""
    result: dict[str, Any] = {}

    if candidate.content:
        result["content"] = _serialize_content(candidate.content)

    if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
        result["finish_reason"] = str(candidate.finish_reason)

    if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
        result["safety_ratings"] = [
            {"category": str(r.category), "probability": str(r.probability)}
            for r in candidate.safety_ratings
        ]

    return result


def _serialize_response(response) -> dict[str, Any]:
    """序列化Response对象。"""
    result: dict[str, Any] = {}

    if response.candidates:
        result["candidates"] = [_serialize_candidate(c) for c in response.candidates]

    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        um = response.usage_metadata
        result["usage_metadata"] = {
            "prompt_token_count": getattr(um, 'prompt_token_count', None),
            "candidates_token_count": getattr(um, 'candidates_token_count', None),
            "total_token_count": getattr(um, 'total_token_count', None),
        }

    return result


class APILogger:
    """完整API日志记录器。"""

    def __init__(self, log_dir: str | Path = "logs"):
        self.log_dir = Path(log_dir)
        self._full_log_file: TextIO | None = None
        self._full_log_path: Path | None = None
        self._request_count = 0

    def init(self, prefix: str = "solve", model: str = "") -> Path:
        """初始化日志文件。

        Args:
            prefix: 日志文件前缀
            model: 使用的模型名称

        Returns:
            完整日志文件路径
        """
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._full_log_path = self.log_dir / f"{prefix}_{timestamp}_full.log"
        self._full_log_file = open(self._full_log_path, "w", encoding="utf-8")
        self._request_count = 0

        # 写入头部信息
        header = {
            "type": "header",
            "timestamp": datetime.now().isoformat(),
            "model": model,
        }
        self._write_json(header)

        return self._full_log_path

    def _write_json(self, data: dict[str, Any]) -> None:
        """写入JSON格式的日志条目。"""
        if self._full_log_file:
            self._full_log_file.write(json.dumps(data, ensure_ascii=False, indent=2))
            self._full_log_file.write("\n\n")
            self._full_log_file.flush()

    def log_request(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig | None = None,
    ) -> None:
        """记录API请求。"""
        self._request_count += 1

        entry = {
            "type": "request",
            "request_id": self._request_count,
            "timestamp": datetime.now().isoformat(),
            "contents": _serialize_contents(contents),
        }

        if config:
            entry["config"] = {
                "temperature": getattr(config, 'temperature', None),
                "system_instruction": str(config.system_instruction)[:500] + "..."
                    if config.system_instruction and len(str(config.system_instruction)) > 500
                    else str(config.system_instruction) if config.system_instruction else None,
            }

        self._write_json(entry)

    def log_response(self, response, error: str | None = None) -> None:
        """记录API响应。"""
        entry: dict[str, Any] = {
            "type": "response",
            "request_id": self._request_count,
            "timestamp": datetime.now().isoformat(),
        }

        if error:
            entry["error"] = error
        elif response:
            entry["response"] = _serialize_response(response)

        self._write_json(entry)

    def log_tool_call(
        self,
        func_name: str,
        func_args: dict[str, Any],
        result: str,
    ) -> None:
        """记录工具调用。"""
        entry = {
            "type": "tool_call",
            "request_id": self._request_count,
            "timestamp": datetime.now().isoformat(),
            "function": func_name,
            "arguments": func_args,
            "result": result,
        }
        self._write_json(entry)

    def close(self) -> None:
        """关闭日志文件。"""
        if self._full_log_file:
            footer = {
                "type": "footer",
                "timestamp": datetime.now().isoformat(),
                "total_requests": self._request_count,
            }
            self._write_json(footer)
            self._full_log_file.close()
            self._full_log_file = None
            print(f"[完整日志] 已保存到: {self._full_log_path}")

    @property
    def path(self) -> Path | None:
        """返回日志文件路径。"""
        return self._full_log_path


# 全局单例
_global_logger: APILogger | None = None


def get_api_logger() -> APILogger:
    """获取全局API日志记录器。"""
    global _global_logger
    if _global_logger is None:
        _global_logger = APILogger()
    return _global_logger
