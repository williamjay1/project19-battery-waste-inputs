# GitHub → Zenodo 发布交接

## 现在已经准备什么

这是一份独立的公开发布候选目录，不是已上传的仓库。仅包括经审查的代码、可再利用数据、来源/许可说明和复现工具。当前论文及旧私用 ZIP 不在其中；不要把整个项目目录或旧 ZIP 上传，以免连同许可受限材料和内部审稿记录一起公开。

公开包中 Basel 原文、源表和派生数值/图件保守地不再分发，提供原始获取链接、处理脚本和校验指纹。Comext 奥地利 CN8 数据保留商业再利用限制，不能把全部数据统一标 MIT/CC0。软件 MIT 不等于数据 MIT。公开前由真实权利人确认原始代码的授权；不冒写作者、机构或 DOI。

## 已确认的贡献者及尚未产生的信息

用户已明确真实贡献者只有 **junjiezhang**。CONTRIBUTORS.json、CITATION.md、.zenodo.json 和原始软件版权声明已统一使用这个完整署名；不拆分姓/名，不猜测机构或 ORCID，不添加 AI 为真人作者，也不把来源机构或第三方工具作者写成项目贡献者。该署名不自动等于 GitHub 账号名。

实际 GitHub 仓库 URL、正式发布日期及 Zenodo DOI 尚未产生，不填写假值。当前 .zenodo.json 可用于该候选包；公开前核对元数据。若需要在新的候选目录生成或更新元数据，可使用：

```text
python -m tools.prepare_metadata --creators CONTRIBUTORS.json
```

脚本保护既有元数据，不在已包含 .zenodo.json 的目录重复执行。需要修改时先制作有记录的新候选版本，不静默覆盖。实际仓库已建立后可以传入 `--repository-url`，真实 release 日期确定后可以传入 `--release-date`；均不得猜测。CONTRIBUTORS.json 目前仅一项 `{"name":"junjiezhang"}`。脚本保留未拆分个人署名，生成 .zenodo.json 并使用 CITATION.md；不将该个人伪装成 CFF 机构，也不推测个人姓名字段。如果本人以后明确提供 family_names/given_names，可生成相符的 CFF。脚本拒绝空作者、占位作者、重复身份和不合法 ORCID；不生成 DOI。

**Zenodo 可以单独采用 .zenodo.json；同时存在 CFF 时优先采用 .zenodo.json。** 本包没有猜测姓名的 CFF；GitHub 支持 CITATION.md 引用文件。record 定义为 software；MIT 仅指软件，描述中明确嵌入数据适用各自来源条件。不要在 Zenodo 中勾选所有数据都是 CC0 的声明。填写作者、编辑者、贡献者字段时不要额外添加 AI、代码源作者或来源机构。

## 发布步骤

1. 在你自己的 GitHub 建立一个空仓库，把本目录**里面的文件及文件夹**上传（不是上传一个 ZIP 代替源码）。不要加入 raw、.venv、临时计算、未授权材料或旧 Git 历史。执行 `python -m pytest -q` 及 offline audit；核对差异后提交。唯一贡献者 junjiezhang 已填入；核对实际仓库 URL 和匿名审稿时点。不需要分享密码或 token。
2. 由你登录 Zenodo，连接 GitHub；在 Zenodo 的 GitHub 页面 Sync now，找到这个仓库并启用开关。
3. 连接完成后，在 GitHub 发布一个与审核代码 commit 对应的**正式 tag/release**，例如 v1.0.0。仅推送代码不等于已生成 Zenodo DOI。不要在连接前反复创建 release 并假定历史 release 已归档。
4. 等 Zenodo 处理，打开 record，核对作者/机构、标题、版本、软件许可与数据例外、归档文件、源链接、公开性和 DOI。下载归档，再运行复现；是否完成以实际 record 为准。若失败查看 Errors，不重复制造同版本假归档。
5. 把 record URL 和对应的**版本 DOI**交给稿件更新流程；随后在论文数据/代码声明中补入真实 DOI。需要文章关联 DOI 时，只有论文真实 DOI 产生后才添加 `isSupplementTo` 关系。数据/代码 DOI 不能写成论文 DOI。
6. 后续科学修改用新 tag/release/new version，保存旧版本，不悄悄覆盖。论文引用与所用版本一致。

若仍处匿名审稿阶段，公开仓库/Zenodo 作者信息可能影响匿名性，先按目标期刊要求决定公开时点和审稿期匿名访问；这不改变来源许可。

## 官方说明

GitHub 对 CITATION.md 的支持、Zenodo .zenodo.json 单独使用与优先级于 2026-10-06 再核。其他发布流程沿用 2026-10-05 的来源核验记录，不声称本次重新核验全部政策。

- [Enable a repository](https://help.zenodo.org/docs/github/enable-repository/)
- [Archive a release](https://help.zenodo.org/docs/github/archive-software/github-upload/)
- [Zenodo JSON precedence](https://help.zenodo.org/docs/github/describe-software/zenodo-json/)
- [CITATION.cff](https://help.zenodo.org/docs/github/describe-software/citation-file/)
- [Zenodo DOI versioning](https://zenodo.org/help/versioning)
- [GitHub citation files](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)

当前交接不声称已上传、已获得 DOI、已满足未提供的伦理/资金/利益冲突声明，也不保证录用。个人责任及实际 AI 协助见 AUTHORSHIP.md、AI_USE.md；计算复现与科研规范检查不能替代数据物理真实性验证。
