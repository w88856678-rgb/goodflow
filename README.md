# GoodFlow：公益视频导演 Skill

把公益项目介绍、人物故事或项目进展，整理成一条有脚本、有分镜、有配音与字幕的竖屏视频。GoodFlow 以导演 Skill 的形式，在支持 Skill 的 AI 工具中协助你完成从资料到成片的制作流程。

**[下载 Skill 安装包](https://github.com/w88856678-rgb/goodflow/releases/download/v2026.09.20/goodflow-skill.zip) · [查看完整使用指南](public-good-video-director/SKILL.md)**

## 适合谁

- **公益项目与机构传播人员**：把项目介绍、活动照片和进展材料整理成短视频。
- **公益内容创作者**：围绕人物故事和具体行动，制作适合竖屏传播的视频。
- **已有 AI 工具使用经验的制作人员**：希望复用脚本确认、素材组织、配音、预览与检查流程。

## 可以做什么

- **从项目资料组织脚本**：围绕来源材料形成脚本方案，保留关键事实，先确认旁白再制作。
- **把旁白拆成分镜**：为每段内容安排画面、字幕和视觉重点，优先使用已获授权的原始素材。
- **按内容选择配音**：根据实际可用的语音服务试听、选择音色，并对齐旁白与字幕。
- **制作竖屏动态图文视频**：结合图片、文字、纸片拼贴、镜头运动与转场，按流程生成预览及 MP4。
- **保留修改与检查依据**：记录脚本、分镜、时间轴、实际使用的服务和成片检查结果，便于后续修改。

这些能力需要宿主工具、模型服务和本地渲染环境配合，最终质量取决于输入素材、实际使用的服务与检查结果。

## 怎么开始

1. 下载并解压安装包，把 `public-good-video-director` 文件夹放入支持 Skill 的 AI 工具的技能目录。
2. 提供项目名称、项目介绍、已获授权的图片和期望时长，让工具使用该 Skill 制作视频；默认面向约 30 秒的 9:16 竖屏视频。
3. 按提示配置渲染依赖及所选模型服务，确认脚本、试听配音并查看预览。
4. 确认预览后生成成片，检查画面、字幕、音频及事实，再用于后续传播。

可以这样提出制作需求：

> 使用 public-good-video-director，把这份公益项目介绍和已授权图片制作成一条 30 秒竖屏视频。先给我脚本方案，确认后再继续配音和预览。

## 使用范围与素材要求

此安装包不包含模型额度，也不提供免安装的在线视频生成服务。需要支持 Skill 的宿主工具、可用的图片或语音能力，以及本地渲染依赖；具体服务按宿主实际能力和你的配置选择。

服务密钥只保存在本地环境。素材是否发送给外部服务，取决于实际选用的工具和供应商，请按素材授权及隐私要求选择。不得使用未授权素材或声音克隆，也不要把生成内容当作已经核实的项目事实。

脚本确认、素材授权、配音和成片检查流程见 [Skill 使用指南](public-good-video-director/SKILL.md)。自动检查需要结合人工审看，不承诺一次生成即可达到发布标准。

如果希望通过网页工作台直接编辑文案与创作参数，可查看另一项目 [Good-flow 视频创作工作台](https://github.com/w88856678-rgb/good-flow)。本仓库交付的是供 AI 工具调用的导演 Skill。

## 配置与进阶资料

本地渲染默认使用 HyperFrames，兼容回退到 Remotion。HyperFrames 需要 Node.js 22 或更新版本、pnpm、FFmpeg/ffprobe 及 Chromium 兼容浏览器等依赖，具体安装与调用方式见以下资料：

- [完整制作流程](public-good-video-director/references/workflow.md)
- [模型与语音服务选择](public-good-video-director/references/provider-routing.md)
- [本地配音与媒体流程](public-good-video-director/references/local-media-pipeline.md)
- [渲染、预览与输出检查](public-good-video-director/references/rendering.md)
- [已有视频的审看与修改](public-good-video-director/references/editorial-revisions.md)
