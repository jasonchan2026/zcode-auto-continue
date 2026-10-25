#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auto-continue Stop 钩子：回合结束时判断是否需要自动续接。

检测策略（命中任一即输出 {"decision":"block","reason":...} 请求续接）：
  1. 繁忙/临时错误：响应文本命中繁忙模式（先过排除清单，防把非临时错误当临时错误）。
  2. 空响应重试：响应为空或纯空白（仅 stop_hook_active=false 时，只重试一次）。
  3. 截断恢复：响应在代码围栏中途被截断（围栏数为奇数；同样只重试一次）。

其余情况一律空输出放行；任何内部异常也放行（失效开放，绝不阻塞会话）。
平台对 Stop 续接有硬上限（3 次），本脚本无需自行计数总次数。

可选配置：${ZCODE_PLUGIN_DATA}/config.json
  {
    "enabled": true,            // false 时整体停用
    "includePatterns": [...],   // 覆盖默认繁忙模式表（小写子串）
    "excludePatterns": [...],   // 覆盖默认排除模式表（小写子串）
    "lengthGuard": 2000,        // 响应长度超过该值不做繁忙匹配（真实内容是长文）
    "backoffSeconds": 3         // 繁忙续接前退避等待秒数
  }
"""

import json
import os
import re
import sys
import time

DEFAULT_INCLUDE_PATTERNS = [
    # 中文临时错误
    "系统繁忙", "服务繁忙", "服务器繁忙", "当前繁忙", "网络繁忙",
    "请求过于频繁", "稍后再试", "稍后重试", "请重试", "重新尝试",
    "网络异常", "网络错误", "连接超时", "请求超时", "响应超时",
    "服务暂时不可用", "暂时无法", "服务不稳定", "并发过高",
    "负载过高", "容量不足", "限流", "上游错误",
    # 英文临时错误（只收强特征词；裸的 timeout/503 等词会出现在正常回答里，
    # 如需可经 config.json 的 includePatterns 自行补充）
    "overloaded", "overload_error", "rate limit", "rate_limit", "ratelimit",
    "too many requests", "service unavailable", "temporarily unavailable",
    "internal server error", "bad gateway", "gateway timeout",
    "timed out", "timeout exceeded", "timeout error", "request timeout",
    "etimedout", "econnreset", "econnrefused", "ehostunreach", "enotfound",
    "fetch failed", "failed to fetch", "network error", "connection reset",
    "connection refused", "connection error", "socket hang up",
    "upstream error", "stream disconnected", "high load",
    "model is at capacity", "try again later", "please retry",
    "please try again", "server_error", "stream error",
    # ZCode 自有错误呈现
    "failure:",
]

DEFAULT_EXCLUDE_PATTERNS = [
    # 上下文超限：不是临时错误，重试无意义
    "context length", "context window", "maximum context", "context_length_exceeded",
    "token limit", "too many tokens", "compaction", "compact",
    # 认证/配额/余额：重试无意义
    "401", "403", "404", "unauthorized", "forbidden", "not found",
    "invalid api key", "invalid_api_key", "authentication", "permission denied",
    "quota", "余额不足", "欠费", "配额",
    # 用户主动中止
    "abort", "cancelled", "canceled", "interrupt",
]

FENCE_RE = re.compile(r"^\s*```", re.MULTILINE)


def load_config():
    cfg = {
        "enabled": True,
        "includePatterns": DEFAULT_INCLUDE_PATTERNS,
        "excludePatterns": DEFAULT_EXCLUDE_PATTERNS,
        "lengthGuard": 2000,
        "backoffSeconds": 3,
    }
    data_dir = os.environ.get("ZCODE_PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir:
        return cfg
    path = os.path.join(data_dir, "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        if isinstance(user_cfg, dict):
            for key in ("enabled", "includePatterns", "excludePatterns", "lengthGuard", "backoffSeconds"):
                if key in user_cfg:
                    cfg[key] = user_cfg[key]
    except Exception:
        pass  # 配置读取失败时用默认值
    return cfg


def block(reason):
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(0)


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        return  # 输入异常，放行

    if not isinstance(payload, dict):
        return
    if payload.get("hookEventName") not in (None, "Stop"):
        return

    cfg = load_config()
    if cfg.get("enabled") is False:
        return

    message = payload.get("last_assistant_message")
    if message is None:
        message = payload.get("responseText")
    if message is None:
        message = payload.get("responsePreview")
    if not isinstance(message, str):
        message = ""
    text = message.strip()
    lowered = text.lower()
    stop_hook_active = bool(payload.get("stop_hook_active"))

    # 1) 排除清单：非临时错误，直接放行
    for pattern in cfg["excludePatterns"]:
        if pattern.lower() in lowered:
            return

    # 2) 繁忙/临时错误：短消息才匹配，避免长回答里出现 "503" 之类的误报
    if len(text) < int(cfg["lengthGuard"]):
        for pattern in cfg["includePatterns"]:
            if pattern.lower() in lowered:
                backoff = max(0, int(cfg["backoffSeconds"]))
                if backoff:
                    time.sleep(backoff)
                block(
                    "检测到模型服务临时错误（{}）。请从中断处继续完成原任务，"
                    "不要重复已完成的步骤。".format(pattern.strip())
                )
                return

    # 3) 空响应重试：只重试一次，防止空转循环
    if not text and not stop_hook_active:
        block("上一条响应为空。请继续完成原任务。")
        return

    # 4) 截断恢复：代码围栏数为奇数说明在代码块中途被切断；只重试一次
    if not stop_hook_active and len(FENCE_RE.findall(message)) % 2 == 1:
        block("上一条响应在代码块中途被截断。请从截断处继续输出，先补完未完成的代码块。")
        return

    # 正常停止，放行（空输出 + exit 0）


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # 失效开放：任何异常都不阻塞会话
    sys.exit(0)
