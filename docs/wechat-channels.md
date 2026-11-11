# 微信视频号：账号与评论工具

[文档导航](README.md) · [操作工作流](../skills/video-workflow/SKILL.md#视频号账号与评论采集) · [视频素材下载](usage.md#微信视频号)

`videocut wechat` 通过独立本地 `wx_channels_download` 服务查询账号、作品、评论和回复。该入口不发布内容、不登录、不读取 Cookie，不自动改系统代理或安装信任证书。原 `download --wechat-*` 继续用于视频素材导入。

## 本机可直接复用的服务

默认运行目录是仓库内忽略的 `upstream/wechat-channels/`，包含独立源码、二进制、构建摘要、配置和证书；不再引用聊天目录。2026-11-11 已在当前机器完成构建。证书有效期为 2 天，生成证书不等于已安装信任。

```bash
uv run videocut wechat doctor --runtime upstream/wechat-channels
# 若证书到期或剩余不足 5 分钟：先停服务，再换证书。
uv run videocut wechat service-renew-cert --runtime upstream/wechat-channels
# 前台运行，Ctrl-C 停止。证书及系统代理按工作流单独处理。
uv run videocut wechat service-run --runtime upstream/wechat-channels
```

`service-run` 校验构建摘要、兼容配置版本、证书有效期、证书与私钥配对、loopback 监听、端口可用，以及禁止自动信任/自动代理的配置。它不检查系统信任；`doctor` 会明确输出 `system_trust: not_checked`。服务在线但页面没连接时，`available: false` 不是“服务没启动”。

需要从另一台机器复现时，准备 Go（上游固定提交使用的工具链）、Node.js、OpenSSL、Git，以及包含下列提交的上游本地 checkout：

```bash
git clone https://github.com/ltaoo/wx_channels_download.git upstream/wx_channels_download
uv run videocut wechat service-prepare \
  --source upstream/wx_channels_download \
  --runtime upstream/wechat-channels
```

本机需要出站代理时可显式加 `--upstream-proxy http://127.0.0.1:7897`；这是当前机器的可选例子，不是通用默认值。Go 下载依赖使用其自身环境代理。不要把上游代理指向本服务的 2023 端口，否则会形成循环。

构建从固定提交 `124f044235bc706fe796c043a14ff442a150ae5d` 导出隔离副本，不修改调用者的工作区；补丁前校验两个目标文件 SHA-256，遇到未知版本直接拒绝。已存在的非空运行目录不会覆盖，升级请换目录。`config.yaml` 使用兼容 YAML 的 JSON 格式，便于无额外依赖地读写。

## 兼容修复的范围

当前配置名为 `comments-20261111-v1`，用于账号搜索、作品列表、评论和回复：

- 旧注入器用正则重写 `async` 方法体，在新版微信压缩代码中产生 `Unexpected token '}'`。本配置保留这些方法，只在单个可识别的本地 `export {...}` 前暴露已有实例。保留 `$` 标识符；不识别的导出布局原样返回，避免把页面改坏。
- 单个实例可能同时包含搜索、详情、关注列表等方法。去掉 API 识别中的提前返回，同时跳过 `null` 和基本类型，修复 `WXU.API2.finderSearch is not a function`。
- 不保留聊天目录写死路径、调试脚本落盘或任何账号数据。

**该配置移除了目标模块内的自动捕获事件钩子，不承诺原下载器的推荐流、翻页自动入库或直播功能。** 视频下载适配没有改成此配置；需要下载时仍按原下载入口核对实际捕获记录。不要把“评论查询成功”当成“所有下载功能已验收”。微信后续更新仍可能导致桥接不可用；先执行带关键词的 doctor，不盲目重试旧注入器。

上游许可为 MIT + Commons Clause，不是无条件 MIT。本仓库保存原创兼容转换逻辑，构建时才读取上游源码；上游源码与二进制保留在忽略目录并保留其 LICENSE，不随本仓库分发。

## 查询与采集

本地默认 API `127.0.0.1:2022`，捕获代理 `127.0.0.1:2023`。原生微信页面需要保持打开并通过代理加载。仅页面在线不证明全部 API 正常，使用搜索探针：

```bash
uv run videocut wechat doctor --runtime upstream/wechat-channels --keyword '目标账号'
uv run videocut wechat search '目标账号'
# 搜索返回 more=true 时传 --next-marker '返回的游标' 查询下一页。
# 核对昵称后使用返回的完整 username，不按“最新视频”或同名账号猜测。
uv run videocut wechat collect --username '完整的账号 username' \
  --output outputs/wechat-account-20261111
```

各命令可用 `--api http://127.0.0.1:2022` 指定 loopback HTTP origin。控制请求绕过环境/系统代理并拒绝重定向；不接受远端 API origin。

采集串行执行，默认请求间隔 0.15 秒、请求超时 40 秒，每个服务/API 失败最多尝试 3 次。分别验证外层 `code`、内层 `errCode` 和 `BaseResponse.Ret`。不会把错误响应的原文、签名 URL 或 Cookie 输出到日志。

作品、根评论和每个根评论的回复分别翻页。分页完成依据是明确的结束标志；缺失标志、游标不前进、超过页上限或请求失败均标记不完整。默认每条分页链最多 1,000 页，可以用 `--max-pages` 调整；达到上限不是成功。回复预览与展开页按评论 ID 去重，保留根父评论与 `reply_to` 字段。

## 文件合同与续跑

| 文件 | 内容 |
| --- | --- |
| `request.json` | schema、API origin、目标 username；防止换账号误用输出目录 |
| `pages/*.json` | 已成功校验的精简分页、内容摘要和采集时间；去除视频媒体 URL、解密密钥和无关 payload |
| `collection.json` | 完整状态、错误、作品、评论、回复关系、作者标识、计数及请求/缓存次数 |
| `.collection.lock` | 同一目录的采集互斥锁 |

`collection.json` 的 `complete` 必须与 `feed_list_complete` 及每条作品的 `root_complete/replies_complete` 一起读取。每条作品完成后原子保存报告；中断后重跑相同命令，成功页复用，失败页重新请求，损坏缓存按摘要识别并重取。退出码 **0** 表示返回数据分页完整，**2** 表示已有部分数据但不完整，**1** 表示配置或命令失败。

同目录续跑复用原快照，不代表刷新最新数据。要更新计数或评论，使用新的日期输出目录。分页中的增删、删除/隐藏评论及服务未返回的内容无法保证获取；“完整”只指本次可访问的分页已结束。

文件包含平台账号 ID、昵称、原话和 IP 地域，默认目录 0700、数据文件 0600；只保留在忽略的 `outputs/`，不要提交到 Git。IP 地域不能当常住地。采集器只标注与目标 username 相同的作者，不自动以昵称判断机器人或关联账号；分析时明确记录实际排除规则，再计算分母。

## 诊断

| 现象 | 判断与处理 |
| --- | --- |
| `WECHAT_SERVICE_UNAVAILABLE` | API 不可达；检查服务进程/端口，而不是反复点视频 |
| `available: false` | 服务可达但微信页面未连接；检查实际代理、证书信任，重新加载视频号窗口 |
| 证书过期/私钥不配对 | 停服务，`service-renew-cert`，根据新证书重新处理信任；旧证书文件保留供清理 |
| `Unexpected token '}'` | 可能仍在用旧版方法体注入；恢复原代理与页面，再切换隔离兼容服务 |
| `finderSearch is not a function` / `WECHAT_BRIDGE_ERROR` | 页面桥接不兼容；检查固定构建、刷新缓存，用带关键词 doctor 验证 |
| `PAGINATION_STALLED` / `PAGE_LIMIT_REACHED` | 保留部分数据，核对游标/上限；不得报告采集完整 |
| CUA 的 `noWindowsAvailable` | 原生窗口控制失败不等于 API 不可用；优先查本地服务，别反复坐标点击 |

信任证书、切代理、恢复原设置的会话步骤见[工作流](../skills/video-workflow/SKILL.md#视频号账号与评论采集)。工具不会把当前会话授权写成未来永久授权。
