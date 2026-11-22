"""清残:归档所有未归档的 AT-直播侦察-* 沙箱课。

来源:2026-11-22 侦察链路跑了 5 轮,其中 1 轮建课成功但建讲次失败,
那门课没讲次、也没人负责归档,会一直挂在课程列表里当垃圾。
判据:课名以 AT-直播侦察- 开头且未归档 → DELETE /courses/{id}(本系统=软删归档)。
绝不动别的课(AT-* 其他前缀是既有用例的沙箱,由各自用例负责)。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import urllib3
urllib3.disable_warnings()

from api.course_api import CourseApi
from api.login_api import LoginApi


def items_of(resp):
    data = (resp.json() or {}).get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or []
    return []


def live_items(resp):
    """只留未归档的项。⚠ 实测 GET /courses 把归档课也一并返回(靠 status 区分),
    '还在列表里'≠'未归档'——判残留必须看 status,不能看在不在列表(源码注释同一口径)"""
    return [c for c in items_of(resp) if c.get("status") != "archived"]


tok = LoginApi().login_and_get_token()
cs = CourseApi()
targets = [c for c in live_items(cs.list_courses(tok))
           if (c.get("name") or "").startswith("AT-直播侦察-")]
print("待归档:", [(c["id"], c["name"]) for c in targets] or "无残留")
for c in targets:
    r = cs.archive_course(tok, c["id"])
    print(f"archive {c['id']} {c['name']} -> HTTP {r.status_code}")
left = [c for c in live_items(cs.list_courses(tok))
        if (c.get("name") or "").startswith("AT-直播侦察-")]
print("归档后剩余未归档 AT-直播侦察 课:", len(left))
