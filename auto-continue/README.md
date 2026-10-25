# auto-continue

对话回合因「系统繁忙」等模型服务临时错误中断时，自动请求续接，让模型从中断处继续完成任务。

## 工作原理

插件注册一个 **Stop 钩子**——它在每个回合结束时触发，检查最后一条响应，命中以下任一情况时输出 `{"decision":"block","reason":"..."}` 请求平台自动续接（reason 会作为继续指令注入给模型）：

| 策略 | 检测方式 | 说明 |
|---|---|---|
| 繁忙错误续接 | 响应文本命中繁忙/临时错误模式 | 如「系统繁忙」「请求过于频繁」「overloaded」「529」「timeout」「ECONNRESET」等，先退避 3 秒再续接 |
| 空响应重试 | 响应为空或纯空白 | 只重试一次 |
| 截断恢复 | 代码围栏（```）数量为奇数 | 响应在代码块中途被切断，要求从截断处补完；只重试一次 |

正常完成的回答三种检测都不命中，钩子静默放行，日常使用无感知。

## 防循环与安全

- **平台硬上限**：ZCode 对 Stop 续接最多 3 次，天然防死循环。
- **单次重试**：空响应与截断只在 `stop_hook_active=false` 时续接（即每类最多重试一次）；繁忙错误可持续续接至上限耗尽。
- **排除清单**：上下文超限（context length exceeded）、认证/配额/余额不足（401/403/quota/欠费）、用户主动中止等非临时错误不会触发续接——重试无意义。
- **长度护栏**：响应超过 2000 字符不做繁忙匹配，避免长回答正文中出现 "503" 之类的数字误报。
- **失效开放**：脚本异常、python3 缺失、输入解析失败时一律放行停止，绝不阻塞会话。

## 配置（可选）

默认行为无需配置。如需调整，在插件数据目录（ZCode 会在插件详情中展示）创建 `config.json`：

```json
{
  "enabled": true,
  "includePatterns": ["系统繁忙", "overloaded"],
  "excludePatterns": ["context length", "quota"],
  "lengthGuard": 2000,
  "backoffSeconds": 3
}
```

- `includePatterns` / `excludePatterns`：**整体覆盖**默认模式表（小写子串匹配，命中任一即生效）。
- `enabled: false`：临时停用，无需卸载插件（也可在 设置 → 插件管理 中直接禁用插件）。

## 手动自检

```bash
echo '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"系统繁忙，请稍后再试"}' \
  | python3 hooks/stop_continue.py
# 期望输出：{"decision": "block", "reason": "检测到模型服务临时错误（系统繁忙）..."}

echo '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"任务已完成。"}' \
  | python3 hooks/stop_continue.py
# 期望输出：空（放行）
```

## 环境要求与边界

- 依赖 `python3`（macOS/Linux 开发机通常自带）；当前钩子经 shell 调用，未适配 Windows。
- 若某类服务端错误走的是不触发 Stop 事件的路径，则该场景无法接住；钩子执行记录可在 ZCode 日志中查看（触发、通过、续接结果）。
