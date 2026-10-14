"""归口部门映射：只回填有据可查的部分（部门名 + 官网域名）。"""

from p1.contacts import contact_for, dept_sites


def test_every_dept_with_a_url_maps_to_its_site():
    sites = dept_sites()
    assert sites["图书馆"] == "https://library.sspu.edu.cn"
    assert sites["学生处"] == "https://xsc.sspu.edu.cn"
    assert len(sites) >= 18  # 现行有效制度覆盖 19 个部门，人工整理件没有站点


def test_contact_line_and_fallback():
    assert contact_for("图书馆") == "图书馆（https://library.sspu.edu.cn）"
    # 人工整理件没有官网，退回部门名本身，绝不编一个网址出来
    assert contact_for("人工整理") == "人工整理"
    assert contact_for("不存在的部门") == "不存在的部门"
    assert contact_for(None) is None
