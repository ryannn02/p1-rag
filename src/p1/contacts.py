"""归口部门 → 官网：从 meta/documents.csv 的 dept / source_url 推出来。

拒答时要告诉用户「去哪儿问」。部门名不能让模型编，电话号码更是编不得——
所以只回填**有据可查**的部分：部门名 + 该部门制度所在的官网域名。
库里没有电话/邮箱的数据源，有人补就加一列，别猜。

    >>> from p1.contacts import contact_for
    >>> contact_for("图书馆")
    '图书馆（https://library.sspu.edu.cn）'
"""

import csv
from pathlib import Path
from urllib.parse import urlparse

META = Path("meta/documents.csv")


def dept_sites(path=META):
    """{部门: 官网根地址}。人工整理件没有来源站点，不进表。"""
    sites = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["status"] != "effective":
                continue
            host = urlparse(r["source_url"]).netloc
            if host:
                sites.setdefault(r["dept"], f"https://{host}")
    return sites


def contact_for(dept, path=META):
    """部门名 → 给用户看的咨询渠道；查不到就原样返回部门名。"""
    if not dept:
        return None
    site = dept_sites(path).get(dept)
    return f"{dept}（{site}）" if site else dept
