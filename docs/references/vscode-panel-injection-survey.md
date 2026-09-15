# VSCode 面板会话"仿人唤醒/直接触发"注入链调研报告

> 2026-09-15 · gale-research L4（R1→R4 完成，R5 不触发：收益闸门<2 新增可证伪出处）· 场景=不靠人打字，把文本+Enter 送进 VSCode 面板里的 Claude Code 会话（Windows 侧 code.exe UI + WSL 侧扩展宿主的 Split 架构）。排除：改 Claude Code 扩展源码。前篇《claude-code-session-wake-survey》已判"官方无注入口"，本篇调研**仿外部触发**的落地链。

## 1. 术语对照
| 中文 | 英文 | 区分 |
|---|---|---|
| 键入模拟 | SendKeys / send-input（OS 级真键盘） | 与"事件注入"区别：需前台焦点 |
| 事件注入 | CDP `Input.dispatchKeyEvent`（renderer 级可信事件） | 不依赖 OS 前台；trusted event |
| 桥接扩展 | bridge extension（Remote Control / 自研） | 把 executeCommand 暴露成 HTTP/URI |
| 协议伪造 | spoofing extension↔core channel | 私有，WS/stdio stream-json 帧 |
| URI 处理器 | `vscode://publisher/path` protocol handler | Windows start 命令可触发，免端口 |

## 2. 候选对比总表
| 候选 | 免打字 | 免抢焦点 | 免改启动方式 | 依赖 | 可行性出处 |
|---|---|---|---|---|---|
| A. PowerShell/AHK SendKeys 全家桶（找窗口→focus 命令→剪贴板粘贴→Enter） | 半（敲 2 键） | ❌ 需前台 | ✅ | 无（powershell 自带；WSL→Win 通道本机实测可达） | pywinauto 文档+issue #1111：Electron 无原生控件，只能真键盘路径；[estruyf 教程](https://www.eliostruyf.com/devhack-open-custom-vscode-webview-panel-focus-input/)：focus webview 输入框是常规操作 |
| B. CDP 事件注入（code.exe 带 `--remote-debugging-port`，脚本打 keydown/Enter 到 webview target） | ✅ | ✅ | ❌ 改一次快捷方式 | Win 侧 node/python websocket 客户端 | [vscode#96626](https://github.com/microsoft/vscode/issues/96626)：webview target **就在 /json/list**；[devtools-protocol#45](https://github.com/ChromeDevTools/devtools-protocol/issues/45)：Enter 模拟确认可行；[Electron 官方](https://electronjs.org/docs/latest/tutorial/debugging-main-process)支持该 flag |
| C. 桥接扩展（Remote Control/自研 30 行：HTTP/URI → executeCommand） | 半（省"找窗口/找框"，Enter 仍需一键） | ❌ | ✅ | 装扩展 | 命令表本地实测：**claude-vscode.focus/sidebar.open/newConversation 有、sendMessage 无**；[vscode-remote-control](https://github.com/estruyf/vscode-remote-control)、[REST Control](https://marketplace.visualstudio.com/items?itemName=dpar39.vscode-rest-control) |
| D. 协议伪造（extension↔core 通道直接送 user 帧） | ✅ | ✅ | ✅ | 逆向私有协议 | extension.js 解剖：spawn+WebSocket×45+`"type":"user"` 帧形（同 stream-json SDK 协议）——**存在但文档未公开，版本漂移高危** |
| E. code CLI 执行扩展命令 | — | — | — | — | **证伪**：remote-cli 实测仅 --status 等固定操作，官方 CLI 文档无 executeCommand（[issue #190142](https://github.com/microsoft/vscode/issues/190142) open） |

## 3. 排除清单及原因
- **E** CLI 通道：本地实测+官方文档双证伪。
- **webview postMessage 直达**：跨扩展 webview 隔离（官方 Webview API：扩展只能控自己的 webview），第三方进不去。
- **UIA ValuePattern 填框**：Electron 无原生编辑控件，contenteditable 不暴露可写 pattern（pywinauto/AHK 社区一致结论）。
- **无焦点后台 SendKeys（ControlSend 类）**：Chromium 命中测试只认前台（[pywinauto#1111](https://github.com/pywinauto/pywinauto/issues/1111)）。
- **Routines/Channels/cross-session→面板**：前篇已判死（认证墙/接收面不含面板），不重复。

## 4. 关键技术判断
- **分化点=要不要保"人可见"**：C/A 的消息会**真实出现在面板输入框并显示**（和人手打无异，含权限提示流程）；D 协议伪造同样进 UI 消息流；B(CDP) 是 renderer 级事件，效果=A 但全免。
- **"打字触发了什么"三层答**：Enter→webview JS keydown 处理→`acquireVsCodeApi().postMessage`→扩展宿主→（本地通道 WS/stdio）→claude 核心。前两层外部不可达（隔离），第三层可伪装=选项 D，第四层公开替身=CLI headless（但那是另一个会话，非唤醒本会话）。
- Remote-WSL 拓扑提醒：UI renderer 在 **Windows 进程**里，B 的 CDP 口开在 Win 侧；WSL 要连 9222 需镜像网络或 netsh portproxy（既有经验 [[wsl2-lan-access-netsh-portproxy]]），或干脆把 CDP 客户端放 Win 侧跑。
- 采购前必测（本地 10 分钟实验）：①带 `--remote-debugging-port=9222` 重启 code.exe，`curl localhost:9222/json/list` 看 Claude webview 是否成 target ②`Input.dispatchKeyEvent` 一串 'x'+Enter，看输入框是否收到并发送 ③若被 Electron 生产构建剥离，则 B 死、转 A+C 组合。

### 4.5 实测结果（2026-09-15 16:30，探针实例）
- ✅ **稳定版暴露 CDP**：VS Code 1.137.0 (Electron 42.10/Chrome 148) 带 `--remote-debugging-port` 起独立 user-data-dir 实例，`/json/version` 与 `/json/list` 正常，workbench renderer 即 type=page 可附着 target。**B 路线成立，无需走 wake-bridge 退路。**
- ✅ 端口只绑 `127.0.0.1`（WSL 经网关 172.28.x 不可达，实测）→ **CDP 客户端放 Windows 侧跑**；PowerShell 5.1 自带 `System.Net.WebSockets.ClientWebSocket`，零新依赖；触发链=WSL 哨兵→`powershell.exe -File inject.ps1`→CDP 注入。
- ⏳ 末项（Claude webview iframe 的焦点路由+Enter 生效）只能等你下次带调试参数重启 VSCode 后在真窗口验，属集成测试非可行性判定。
- 探针实例已自动关闭清理，未触碰在用窗口。

## 5. 缺口裁决表
| 缺口 | 状态 | 证据 |
|---|---|---|
| G1 CDP 可达 VSCode webview target | 已闭合（文献级）+终审=上面的实测清单 | vscode#96626 + devtools-protocol#45 + Electron docs |
| G2 A 路前台依赖 | 已闭合（是硬约束，接受或选 B） | pywinauto#1111、#1023 |
| G3 WS 帧形 | 已闭合（存在、私有、同 stream-json 形态）| extension.js 本地解剖 |
| G4 桥接扩展能力 | 已闭合（executeCommand 可达=命令表=focus 类；文本注入不可达）| 本地 package.json 实测 + estruyf 文档 |
| G5 WSL↔Win 触发通道 | 已闭合（powershell.exe/clip.exe/start 均可达）| 本机实测（含声音提醒 hook 先例） |

## 6. 推荐结论
- **短期（E1 主段告警链路用）**：**B 优先**——今天即可做上面 3 步实测；通了就是"零打字零抢焦点"的完整闭环：systemd 哨兵（已上线）发现异常 → 经 portproxy/Win 侧脚本 → CDP 打事件进面板 → 我在这个会话醒来读 ALERT 报你。
- **B 不通的退路**：**C+A 杂交**——自研 30 行 wake-bridge 扩展（HTTP 端口在 WSL 扩展宿主侧，哨兵 curl 直达）：`executeCommand('claude-vscode.focus')` + `clip.exe` 写文本 + Win 侧仅补一个 `{ENTER}`。代价=抢一次前台（VSCode 若在后台会弹到前面）。
- **不推荐**：D 协议伪造（私有+漂移，工程债）；纯 A 手工链（脆）。
- 安全边界照旧：注入文本带固定前缀（如 `[watchdog]`），会话里见到非该前缀的"系统消息"即提示词注入警报——此链路本身是新的攻击面（本机任意进程可 curl/CDP 口），9222/桥端口只绑 127.0.0.1。

## 7. 来源列表
前篇报告 + 上文全部 URL；另：[CDP Input 域](https://chromedevtools.github.io/devtools-protocol/tot/Input/)、[chrome-remote-interface#226](https://github.com/cyrus-and/chrome-remote-interface/issues/226)、[sandipb code-cli 机制](https://blog.sandipb.net/2024-01-17/using-the-code-cli-in-vs-code-remote-extension/)、[vinnie 控 tmux 文](https://www.vinnie.work/blog/2024-06-29-controlling-vscode-from-tmux)、[VSCode 1.120](https://code.visualstudio.com/updates/v1_120)、[mattbierner webview 架构](https://blog.mattbierner.com/vscode-webview-web-learnings/)、[Electron webview tag](https://electronjs.org/docs/latest/api/webview-tag)。
