"""开课前体检 + 沙箱准备:确认可开的讲次、查T老师名下有无 ongoing。

铁律(2026-11-22 体检当场抓到):
  讲次 id 会漂移!2026-11-04 建的"课40/讲次41"沙箱,现在 id=41 已变成
  课程6《第7周》的讲次——数据库被重建过。绝不按旧记忆里的 id 开课,
  每次都要【当场新建】沙箱课+讲次,用完归档,ids 只在这一条链路里有效。

流程:
  1) 登录拿 token
  2) 扫T老师名下全部未归档课程,找 status=ongoing 的讲次(有则 NO-GO)
  3) 新建 AT-沙箱课 + 新讲次,输出 lesson_id 供侦察脚本使用
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import datetime
import json

import urllib3
urllib3.disable_warnings()

import config
from api.course_api import CourseApi
from api.lesson_api import LessonApi
from api.login_api import LoginApi


def items_of(resp):
    """把返回的 data 统一成 list:实测有的接口给 list,有的给 {items,total} 信封"""
    data = (resp.json() or {}).get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or data.get("list") or []
    return []


lh = LessonApi()
cs = CourseApi()
tok = LoginApi().login_and_get_token()

# 1) 全局查重:T老师名下有没有别的 ongoing(有则 start 撞 409/40903)
ongoing = []
for c in items_of(cs.list_courses(tok)):
    for ls in items_of(lh.list_lessons(tok, c["id"])):
        if isinstance(ls, dict) and ls.get("status") == "ongoing":
            ongoing.append((c["id"], c.get("name"), ls.get("id")))
print("T老师名下 ongoing 讲次:", ongoing or "无")
if ongoing:
    print("\n结论: NO-GO——先下课再开,别硬 start")
    sys.exit(1)

# 2) 当场新建沙箱:AT- 前缀课 + 一个讲次
now = datetime.datetime.now().strftime("%m%d-%H%M%S")
course_name = f"AT-直播侦察-{now}"
cr = cs.create_course(tok, course_name)
print("建课:", cr.status_code, course_name)
cid = json.loads(cr.text)["data"]["id"]

# 建讲次必填 title/week_no/weekday/period;⚠ period 已改成受限枚举
# (Schemas/req/course.py LessonPeriod: 12/34/1234/56/78/5678/910,2026-11-22 读源码)
# 旧写法 "1-2节" 会被 40001 拒——字段规则会随开发变,报错先看 data 里逐字段错误
lr = lh.create_lesson(tok, cid, title="侦察讲", week_no=1, weekday=1, period="12")
print("建讲次:", lr.status_code)
if lr.status_code != 200:
    print("返回体:", lr.text[:400])
    sys.exit(2)
lid = json.loads(lr.text)["data"]["id"]
print("status:", json.loads(lr.text)["data"].get("status"))

print("\nSANDBOX_COURSE=%s" % cid)
print("SANDBOX_LESSON=%s" % lid)
print("\n结论: GO——用上面这对新 id 开课侦察,收尾必须 end + 归档")
