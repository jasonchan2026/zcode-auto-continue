# auto-continue · ZCode 自动续接插件

[中文](#中文) · [English](#english)

## 中文

ZCode（Z.ai 桌面端）对话回合因「系统繁忙」「请求过于频繁」等模型服务临时错误中断时，自动退避并请求续接，让模型从中断处继续完成任务——不再需要手动点"继续"。

### 安装

1. 打开 ZCode → **插件市场** → **添加** → **添加插件市场**
2. 粘贴本仓库地址：`https://github.com/jasonchan2026/zcode-auto-continue`，点击添加
3. 进入 **个人** → **zcode-auto-continue** → **Auto Continue（自动续接）** → 点击 **安装**
4. 安装即生效，无需配置；在**新任务**中开始使用（已开启的旧会话不会加载新钩子）

也可用 ZCode 内置 CLI（如已安装）：

```bash
zcode plugins marketplace add https://github.com/jasonchan2026/zcode-auto-continue
zcode plugins install auto-continue@zcode-auto-continue
```

### 工作原理

插件注册一个 [ZCode Stop 钩子](auto-continue/README.md)，在每个回合结束时检查最后一条响应，命中以下任一情况时输出续接决策（`decision: block`），由平台自动继续：

| 策略 | 检测方式 | 行为 |
|---|---|---|
| 繁忙错误续接 | 命中「系统繁忙 / overloaded / rate limit / timed out / ECONNRESET / Failure:」等强特征词 | 退避 3 秒后请求续接 |
| 空响应重试 | 响应为空或纯空白 | 请求续接（只重试一次） |
| 截断恢复 | 代码围栏（\`\`\`）数量为奇数，即代码块中途被切断 | 要求从截断处补完（只重试一次） |

正常完成的回答不会命中任何检测，钩子静默放行，日常使用无感知。

### 安全机制

- **平台硬上限**：ZCode 对 Stop 续接最多 3 次，天然防死循环。
- **排除清单**：上下文超限、认证/配额/余额不足、用户主动中止等非临时错误不触发续接。
- **长度护栏**：超过 2000 字符的响应不做繁忙匹配，避免长文中出现 "503" 之类数字误报。
- **失效开放**：脚本异常、python3 缺失、输入解析失败时一律放行，绝不阻塞会话。

### 配置（可选）

在插件数据目录创建 `config.json` 可覆盖默认行为，详见[插件文档](auto-continue/README.md)：

```json
{
  "enabled": true,
  "includePatterns": ["系统繁忙", "overloaded"],
  "excludePatterns": ["context length", "quota"],
  "lengthGuard": 2000,
  "backoffSeconds": 3
}
```

### 环境要求

- macOS / Linux，且 `python3` 可用（一般开发机均满足）
- Windows 暂不支持（钩子经 shell 调用）
- 已知边界：请求级硬失败（如模型不存在、认证失败导致的 turn failed）不经过 Stop 事件，不在本插件覆盖范围内

### 本地开发与测试

```bash
git clone https://github.com/jasonchan2026/zcode-auto-continue.git
cd zcode-auto-continue
bash auto-continue/hooks/smoke_test.sh   # 18 项冒烟测试
```

### 卸载

**设置 → 插件管理 → auto-continue → 卸载**；或在插件市场移除本市场源。

### 许可证

[MIT](LICENSE)

---

## English

A ZCode (Z.ai desktop) plugin that automatically continues conversation turns interrupted by transient model/provider errors ("系统繁忙" / overloaded / rate limit / timeout), instead of requiring a manual "continue" click.

**Install**: ZCode → Plugin Marketplace → Add → paste `https://github.com/jasonchan2026/zcode-auto-continue` → install *Auto Continue* from the *Personal* tab. Takes effect in new tasks; no configuration needed.

It registers a single Stop hook with three detection strategies — transient-error patterns (with a 3s backoff), empty-response retry, and mid-code-block truncation recovery — each capped by the platform's built-in 3-continuation limit, with an exclusion list (context-length, auth/quota, user abort) and fail-open behavior. See the [plugin docs](auto-continue/README.md) for details and configuration.

Requires macOS/Linux with `python3`. Licensed under [MIT](LICENSE).
