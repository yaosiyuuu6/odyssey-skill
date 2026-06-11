# 三类渠道原文采集方法

## B 站
- 从 BV URL 调用 `x/web-interface/view` 获取标题、UP 主、发布时间、时长、简介和 CID。
- 用 `x/player/v2` 读取官方字幕列表，优先保存字幕 JSON 和纯文本。
- 无官方字幕时使用 `yt-dlp` 下载最佳音频，再用本地 ASR。
- 内置字幕接口后会自动调用 `bccdl` 下载 B 站 CC 字幕；如果网页下载被 412 拦截，优先使用 playurl API 音频地址或浏览器登录态 cookies。
- 简介只作为元数据，不作为完整原文；只有字幕或完整音频转写才可标记为完整。

### B 站高质量转写
- 推荐命令：`--reuse-existing-media --asr-engine whisperx --asr-model large-v3`。
- WhisperX 负责 word-level timestamp、对齐和 pyannote 说话人分离，输出 `speaker_segments`、WhisperX JSON 和按说话人分段的 transcript。
- 需要本地 `ffmpeg`/`ffmpeg@7`、`whisperx`、`pyannote.audio`、`torchcodec`，并设置 `HF_TOKEN`，且在 Hugging Face 接受 pyannote diarization 模型授权；缺少 token 时脚本记录 `whisperx_unavailable:HF_TOKEN_missing`，并回退 `faster-whisper`，不会误标为 `diarized`。
- `config/hotwords_zh.txt` 注入平台词、人名、节目名；`config/corrections_zh.json` 做确定性错词修正并写入 `correction_log`。

## 小红书
- 先解析短链并抓公开页面，提取标题、正文和图片 URL。
- 公开页面不完整时，使用本机已登录页面做查看、展开、滚动、截图和保存图片。
- 正文文本和图片文字分开 OCR 后合并；只有正文和全部可见图片 OCR 都完成才标记为完整。
- Computer Use 不做点赞、评论、关注、发送或修改动作。

## Podcast
- 从 Apple Podcast URL 的 `i=` 参数提取 episode id。
- 调用 iTunes lookup 获取节目、单集标题、发布时间、时长和简介。
- 优先使用 lookup 返回的 `episodeUrl`，缺失时从 RSS enclosure 匹配音频源。
- 下载音频后用本地 ASR；简介只作为元数据，不作为完整原文。
- ASR 默认 `auto`：优先 MLX Whisper（Apple Silicon/Metal 可用时），当前沙箱无 Metal 时自动回退 `faster-whisper`。
- 高质量多人播客使用 `--asr-engine whisperx`，通过 WhisperX + pyannote 生成 speaker-aware transcript；无法判断主持人/嘉宾时保留 `SPEAKER_00/01`。

## GitHub 工具备选
- B 站字幕：`guomo233/bccdl`，用于下载 B 站 CC 字幕并转换字幕格式。
- B 站 API：`Nemo2011/bilibili-api`，用于替代手写接口调用，适合后续扩展元数据/字幕/视频信息。
- 播客/访谈转写：`m-bain/whisperX` 是当前高质量多人转写方案；`SYSTRAN/faster-whisper` 是 fallback。
- 自托管转写服务：`hwdsl2/docker-whisper` 提供 OpenAI-compatible API 和可选 speaker diarization，适合后续批量任务解耦。

## 中文规范化
- 中文元数据、正文、OCR、字幕和 ASR 转写统一输出简体。
- 非中文内容保留原语言，不主动翻译。
