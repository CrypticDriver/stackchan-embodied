# capabilities/ — 大脑能力槽位

「脑体分离」架构的价值在于：**给机器人加新能力，只需在大脑侧插一个"关注点"，身体侧一行不用改。**

一个能力槽位就是一个小程序，它：
1. **关注**某个源（一个 API、一个日志、一个传感器、一个定时器……）
2. 发现值得告诉大哥的事时，**把事件交给 agent 用自己的话组织**
3. 通过 **body 端点**（`/goudan/say`）让机器人主动开口

这样机器人就从"你问才答"变成"有事主动找你"——而所有措辞、语气、判断轻重缓急，都由 agent 的
人格和记忆决定，槽位只负责"发现"。

## 通用模式

```python
while True:
    events = poll_my_source()              # 1. 关注: 拉你的数据源
    for e in new_and_worth_saying(events): # 2. 去重/判断值不值得打扰
        line = ask_agent_to_phrase(e)      # 3. 交 agent 措辞 (它有上下文)
        push_to_body(line)                 # 4. 借嘴说 (POST /goudan/say, X-Body-Token)
    sleep(interval)
```

`push_to_body` 就是往 body 端点发一句话，机器人会开口说（自带表情+口型）。
`ask_agent_to_phrase` 是把原始事件丢给 OpenClaw agent，让它用狗蛋的口吻重述。

## 示例：happy-watcher

[`happy-watcher/`](happy-watcher/) 是一个真实槽位——盯着一批 coding agent 的工作状态，
有任务卡在等审批时，让机器人转头喊你、完成时播报。它演示了完整模式：
轮询 + 状态机去重 + 交 agent 措辞 + body 推送 + 安静时段。**它只是一个示例**，
换成盯股价、盯天气、盯门铃、盯日历……都是同一套骨架。

## 加你自己的能力

1. 照 happy-watcher 写一个 poller（或更简单的定时器）
2. 环境变量给它 `BODY_TOKEN`、`PUSH_URL`（body 端点）、`OPENCLAW_TOKEN`+`AGENT_URL`（措辞用）
3. 装成 systemd 服务常驻
4. （可选）在 OpenClaw agent 侧给它配套加一个查询工具，这样你还能**主动问**它这个能力的状态

能力越多，狗蛋越像个真正关心你的伙伴，而不是一个音箱。
