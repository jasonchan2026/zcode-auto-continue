#!/bin/bash
# auto-continue Stop 钩子冒烟测试
HOOK="/Users/jason/Code/zcode-plugin/plugins/auto-continue/hooks/stop_continue.py"
PASS=0; FAIL=0

check() {
  local name="$1" payload="$2" expect="$3"   # expect: "block" | "pass"
  local out
  out=$(printf '%s' "$payload" | python3 "$HOOK" 2>/dev/null)
  local rc=$?
  if [ "$expect" = "block" ]; then
    if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q '"decision": *"block"'; then
      echo "PASS | $name"; PASS=$((PASS+1))
    else
      echo "FAIL | $name (期望 block, 实际: rc=$rc out=$out)"; FAIL=$((FAIL+1))
    fi
  else
    if [ $rc -eq 0 ] && [ -z "$out" ]; then
      echo "PASS | $name"; PASS=$((PASS+1))
    else
      echo "FAIL | $name (期望空输出放行, 实际: rc=$rc out=$out)"; FAIL=$((FAIL+1))
    fi
  fi
}

# 1. 中文繁忙错误 → block
check "中文系统繁忙" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"系统繁忙，请稍后再试"}' block
# 2. 英文 overloaded → block
check "英文overloaded" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"Failure: 529 overloaded_error: The server is overloaded"}' block
# 3. 网络错误 → block
check "网络连接重置" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"fetch failed: connection reset by peer"}' block
# 4. stop_hook_active=true 且繁忙持续 → 仍 block（连重至上限）
check "繁忙持续重试" '{"hookEventName":"Stop","stop_hook_active":true,"last_assistant_message":"系统繁忙，请稍后再试"}' block
# 5. 正常完整回答 → 放行
check "正常回答" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"任务已完成：已将配置写入 config.json 并通过测试。"}' pass
# 6. 正常回答含偶数围栏 → 放行
check "完整代码块回答" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"代码如下：\n```python\nprint(1)\n```\n完成。"}' pass
# 7. 空响应 stop_hook_active=false → block
check "空响应重试" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":""}' block
# 8. 空响应 stop_hook_active=true → 放行（防循环）
check "空响应只重试一次" '{"hookEventName":"Stop","stop_hook_active":true,"last_assistant_message":""}' pass
# 9. 奇数围栏（截断）→ block
check "代码块截断" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"实现如下：\n```python\ndef foo():\n    return"}' block
# 10. 截断 + stop_hook_active=true → 放行
check "截断只重试一次" '{"hookEventName":"Stop","stop_hook_active":true,"last_assistant_message":"实现如下：\n```python\ndef foo():"}' pass
# 11. 排除：上下文超限 → 放行
check "上下文超限不重试" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"Error: context length exceeded, please compact"}' pass
# 12. 排除：认证错误 → 放行
check "认证错误不重试" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"Failure: 401 unauthorized, invalid api key"}' pass
# 13. 长度护栏：长文本含 503 → 放行
LONG=$(python3 -c "print('关于 HTTP 状态码的说明：' + '503 表示服务不可用。'*100)")
check "长文本不误报" "{\"hookEventName\":\"Stop\",\"stop_hook_active\":false,\"last_assistant_message\":\"$LONG\"}" pass
# 14. 非法 JSON 输入 → 放行
check "非法输入失效开放" 'not-json-at-all' pass
# 15. 空输入 → 放行
check "空输入" '' pass
# 16. 响应只有空白 → block（空响应）
check "纯空白响应" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"   \n  "}' block
# 17. unicode 转义形式的繁忙错误 → block
check "unicode转义输入" '{"hookEventName":"Stop","stop_hook_active":false,"last_assistant_message":"\u7cfb\u7edf\u7e41\u5fd9\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5"}' block
# 18. userConfig 停用路径占位：非 Stop 事件 → 放行
check "非Stop事件忽略" '{"hookEventName":"PreToolUse","last_assistant_message":"系统繁忙"}' pass

echo "-----"
echo "PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
