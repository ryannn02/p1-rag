"""版本校对：把已被新版替代的旧制度标成 archived，不再进检索。

    python -m scripts.audit_versions          # 只报告
    python -m scripts.audit_versions --apply  # 写回 meta/documents.csv

背景：校长办公室站 `xb.sspu.edu.cn/1541` 是学校的旧制度存档（多为 2011 年发布），
补采后带进来一批 2007 年前后的文件，其中一些早已被新版替代。逐份在线比对新旧正文
后，只把**有直接证据**的归档，靠名字像就归档会误伤——比如《“交流生”学籍管理办法》
与《赴外“交流生”学籍管理办法》是两个不同适用对象，不能合并。

`archived` 与 `excluded` 的区别：excluded 是误收/重复、压根不该在库里；archived 是
确实发布过、但现在已被替代，保留在册供追溯，不计入检索。按 meta/README 的验收口径，
archived 计入「≥200 份」总量但单列。
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, ".")
from scripts.probe import FIELDS, META  # noqa: E402

# (旧制度标题片段, 替代它的制度片段, 判定依据)
SUPERSEDED = [
    ("上海第二工业大学学生学籍管理条例",
     "全日制本专科学生学籍管理办法（2024年修订）",
     "第三章即「学籍管理」，含休学/退学/毕业条款；依据教育部 2005 年 21 号令，"
     "已由依据 2017 年令的新办法替代（新办法载明原 2019 版同时废止）"),
    ("考试作弊(违纪)行为的认定和处罚办法",
     "学生考试违规认定与处理办法",
     "同一事项；旧版正文出现「BP机」等 2000 年代表述、无章条结构，"
     "新版有总则与《国家教育考试违规处理办法》依据"),
    ("党委关于“三重一大”制度的实施办法(试行)",
     "落实“三重一大”制度实施办法",
     "同一事项；新版为沪二工大委〔2018〕68号，经党委常委会审议通过后印发"),
    ("学生创新实践学分认定和管理办法(修订)",
     "创新创业学分管理办法",
     "同一事项；新版为沪二工大教〔2018〕276号，规定自 2019 级起执行"),
    ("重点要害部位管理规定",
     "关于加强重点要害部位管理的规定",
     "两份正文开篇与第二、三条逐字相同，是同一制度在校长办公室站与保卫处站各发一次"),
    ("校园交通安全管理规定",
     "校园道路交通安全管理规定",
     "同一事项；新版 2019 年发布，有总则与《道路交通安全法》依据"),
    ("上海第二工业大学校内道路交通管理规定",
     "校园道路交通安全管理规定",
     "同一事项；旧版依据已废止的《道路交通管理条例实施办法》，新版依据《道路交通安全法》"),
    ("图书借阅规定",
     "图书馆图书外借管理办法（修订）",
     "同一事项（借阅权限与借还规则）；新版 2026 年修订，有章条结构"),
    ("读者损坏、遗失书刊赔偿规定",
     "图书馆读者违规处理和赔偿的管理办法（修订）",
     "同一事项；旧版罚则为「每册图书罚 1 角/天」等已过时的标准"),
    ("图书馆受赠文献管理细则",
     "图书文献捐赠管理办法",
     "同一事项（受赠/捐赠文献的入藏与管理）；新版 2026 年发布"),
]


def find(rows, key):
    return [r for r in rows if key in r["title"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(META.open(encoding="utf-8")))
    targets, problems = [], []
    for old_key, new_key, why in SUPERSEDED:
        old = [r for r in find(rows, old_key) if r["status"] != "excluded"]
        new = [r for r in find(rows, new_key) if r["status"] == "effective"]
        if len(old) != 1:
            problems.append(f"{old_key} -> 命中 {len(old)} 条，应为 1")
            continue
        if not new:
            problems.append(f"{old_key} -> 找不到替代件 {new_key}")
            continue
        targets.append((old[0], new[0], why))

    if problems:
        print("校对未通过，不动登记表：")
        for p in problems:
            print("  " + p)
        return 1

    print(f"确认 {len(targets)} 份旧制度已被新版替代：\n")
    for old, new, why in targets:
        print(f"  [{old['year']}] {old['title'][:44]}")
        print(f"      -> [{new['year']}] {new['dept']}《{new['title'][:40]}》")
        print(f"         {why}\n")

    if not args.apply:
        print("（预演，加 --apply 才会写入）")
        return 0

    for old, _, _ in targets:
        old["status"] = "archived"
    with META.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"已把 {len(targets)} 条标为 archived（保留在册、不进检索）")
    print("下一步：python -m scripts.build_corpus && python -m scripts.build_index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
