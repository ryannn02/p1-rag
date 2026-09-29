# 语料登记表

## documents.csv

`documents.csv` 是语料库的唯一真源，进仓库；原始文件本身不进仓库，放共享位置。

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `doc_id` | 是 | 主键，`source_url` 的 sha1 前 12 位，可重算，别手编 |
| `dept` | 是 | 归口部门，用固定值：学生处 / 教务处 / 研究生院 / 财务处 / 后勤保卫 / 信息公开 |
| `title` | 是 | 文件标题，去掉「关于」这类前缀会让检索更难，保持原样 |
| `doc_no` | 否 | 文号，如 沪二工大〔2023〕15号；判版本和去重的关键，能拿到就填 |
| `year` | 是 | 发布年份，取不到填 `unknown` |
| `publish_date` | 否 | `YYYY-MM-DD`，能拿到就填 |
| `source_url` | 是 | 唯一键，去重靠它；有附件时是附件地址 |
| `page_url` | 否 | 附件所在的正文页地址，用来回溯发布日期与栏目 |
| `format` | 是 | `pdf` / `doc` / `docx` / `html` |
| `is_scanned` | 是 | `true` / `false`，决定阶段 2 走不走 OCR，也是「扫描件 ≤20%」的统计依据 |
| `pages` | 否 | 页数，非 PDF 留空 |
| `status` | 是 | `effective` 现行有效 / `archived` 已被修订替代（不进检索） |
| `local_path` | 是 | 相对共享位置的路径，仓库里不存原件 |
| `fetched_at` | 是 | 采集时间 `YYYY-MM-DD HH:MM:SS`，用于判断增量重采 |

**只能追加或改状态，不要覆盖重采**：制度被修订时把旧行改成 `archived`，新增一行新版本，这样历史追溯得到。

## tasks.csv

采集任务登记表，多人分工时用，按部门切分避免重复采。

| 字段 | 说明 |
| --- | --- |
| `dept` | 部门 |
| `scope_note` | 该部门收录范围的边界说明 |
| `owner` | 负责人 |
| `target_count` / `got_count` | 目标份数 / 已采份数 |
| `status` | `todo` / `doing` / `done` |
| `note` | 备注，比如某个页面打不开、某批文件要 OCR |

## 已探明的来源站点结构

2026-09-29 实测，供后续采集参考：

- 学校主站与院系站（如 `jwc.sspu.edu.cn`）是服务端渲染，制度条目形如
  `/2019/0621/c908a13000/page.htm`，正文页里挂 PDF/Word 附件。
  教务处栏目 `https://jwc.sspu.edu.cn/908/list.htm` 已验证可采（7 条）。
- 附件真实地址是 `/_upload/article/files/...`，URL 里不含日期，
  **年份必须从正文页路径 `/YYYY/MMDD/` 取**，否则会从 UUID 里解析出假年份。
- `https://xxgk.sspu.edu.cn/3145/list.htm`（信息公开规章制度）栏目里只有一篇正文，
  列表为空，不是批量来源；不要指望它凑够 200 份。

## 栏目清单 columns.csv

`columns.csv` 由 `python -m scripts.probe <站点首页> --dept X --discover --count` 生成，是可重算的
快照（按 `dept + column_id` 覆盖更新，不留历史）。`rule_count` 只统计列表**第一页**里标题含
「办法／规定／细则／规程／制度／手册／条例」的条目，是筛选参考值，不是该栏目的制度总数。

分页规律：`/<栏目>/list.htm` → `list2.htm` → `list3.htm`……采的时候记得带 `--pages`。

两个坑：

- 栏目里混着「申请表／审批表／下载表格」和真正的制度正文，按关键词过滤时别把表单收进来。
- 通知公告类栏目单个栏目能到 15+6 条，但绝大部分是通知而非制度，`rule_count` 会很低。

## 验收口径

- 「≥200 份」按 `documents.csv` 行数统计，`status=archived` 的也计入总量但单列。
- 扫描件占比 = `is_scanned=true` 的行数 / 总行数，必须 ≤20%。
