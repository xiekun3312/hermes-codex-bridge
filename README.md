# HermesCodexBridge

在 Windows 上给 Codex 投递文件，拿到 TXT 或 Markdown 回复。Hermes 或其他智能体只需要能写入收件箱、读取回信箱。每份来信会新建一个独立的 Codex 会话，回复也会留在这个会话里。

## 启动

需要 Windows、Python 3.10 或更新版本，以及已登录的 Codex CLI。需要在桌面查看会话时，请安装 Codex 桌面应用。在已登录的 Windows 桌面打开 PowerShell，进入项目目录，执行一次以下命令。

```powershell
.\注册桌面启动入口.ps1
New-Item -ItemType Directory -Path .\inbox -Force
```

注册脚本创建一个按需启动的 Windows 任务，把收发进程启动在已登录用户的桌面会话。Hermes 发出启动请求后即可继续检查回信文件。

投递后双击 `启动收发桥.cmd`，或执行 `python -X utf8 -B .\bridge.py start`。启动请求会立即返回，处理记录写入 `data\bridge.log`。

安装 Codex 桌面应用后，收发桥会在来信开始处理时打开新会话，完成回信后再定位到同一个会话。会话保存在 Codex 历史中。`OUTBOX` 的回信目录里还有一个 `Codex 聊天.url`，可以双击打开对应会话。

同一个收发桥目录只允许运行一个收发进程。重复执行启动命令会立即退出，已有进程继续处理。请先投递文件再启动。空收件箱启动后会直接退出。处理期间空闲时每 3 秒检查一次收件箱，连续 30 秒没有新的来信或待处理文件就自动退出。未处理的投递会留在收件箱。

工具先查找 PATH 中的 Codex，再查找本机 Codex Desktop 安装目录。若需指定位置，复制 `config.example.json` 为 `config.json`，填写 `codex_executable` 的绝对路径。PDF 文字提取是可选功能，可以用 `python -m pip install -r requirements.txt` 安装依赖。

## 发件方必须执行的流程

1. 写好 TXT 或 Markdown 请求，连同需要的附件投递到 `inbox`。记下本次请求对应的 `outbox` 路径。用命令行投递时，返回的 `reply_path` 就是对应路径。
2. 每次投递后最多执行一次 `python -X utf8 -B .\bridge.py start`。已有收发进程时沿用该进程。启动请求返回后，在原来的智能体会话里主动等待，每 3 秒只检查本次请求对应的 `reply.md` 或 `reply.txt` 路径。找到后读取回复，并在原会话继续处理。错误回复也属于已收到回复，按文件中的原因处理。
3. 自投递并启动收发桥起，单次最多等 30 分钟。时间到时再查一次对应路径。若仍无回信，重新写一份请求，使用新的文件名或请求 ID，并在正文注明这是第几次投递和上一份请求的 ID。新请求投递完成后，如果收发桥已经退出，可以启动一次，再等待新请求的回信。
4. 初次投递加上重投，最多三次。第三次等满 30 分钟仍无回信时，执行下面的停止命令，停止扫描 `outbox`，汇报三次均未收到回复，并结束当前文件对话。

```powershell
python -X utf8 -B .\bridge.py stop
```

## 直接收发

把 `任务-001.md` 放进 `inbox`。回复会写入 `outbox\任务-001.md\reply.md`。投递 TXT 时回复是 `reply.txt`。直接放入 JSON、日志、源码或图片时，Codex 会根据文件内容作答，默认用 Markdown。每次投递使用新文件名。向收件箱复制时，可以先写 `.tmp` 文件，再改成最终文件名。

带附件时，可以准备这样的目录：

```text
inbox/
└── 任务-002/
    ├── request.md
    ├── workflow.json
    ├── attachments/
    │   └── error.log
    └── READY
```

在 `request.md` 写清要问什么。所有文件写完后，最后创建空的 `READY` 文件。回复位于 `outbox\任务-002\reply.md`。主请求改用 `request.txt` 时会收到 TXT 回复。

## 命令行投递

智能体也可以用这条命令一次提交正文和附件。命令打印请求 ID 和准确的回复文件绝对路径。

```powershell
python -X utf8 -B .\bridge.py submit .\问题.md --attach .\workflow.json --attach .\error.log --reply md
```

可重复传入 `--attach`，可用 `--reply txt` 指定纯文本。命令会把整批文件写完后一次性送入收件箱。已收到的请求会移入 `processing`，完成后原文件移到 `archive`。回复以原子方式落盘，读取方看到最终文件名后就可以打开。若进程中途关闭，重启后会处理尚无回复的请求。

## 附件

支持 TXT、Markdown、JSON、CSV、日志、常见源码与配置文件、PNG、JPEG、WebP、DOCX 正文，以及可提取文字的 PDF。一次最多 16 个附件，其中最多 4 张图片，单文件最大 12 MiB。请求正文最多 24000 字符，发送的文本总量最多 70000 字符，PDF 最多读取前 30 页。无法读取或被截取的附件会在回复里标明。

收件箱和回信箱都在本机。收发桥在临时目录整理所投递的请求文字和可读取的附件，再交给 Codex，由 OpenAI 服务生成回复。Codex 会话的工作目录是收发桥项目目录。

## 实机验收

2026 年 11 月 11 日在 Windows 上跑通了 Hermes 到 Codex 的 TXT 往返。Hermes 投递后，收发桥从已登录的桌面会话启动，Codex 在独立会话中完成回复，桥将 TXT 回信和聊天快捷方式写入 `outbox`。Hermes 确认收到了回复。收发桥空闲 30 秒后正常退出。
