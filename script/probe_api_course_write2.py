r"""
写接口实测侦察（第三轮 · 补卷）：规则边界与清理语义 —— 2026-11-11
上一卷（probe_api_course_write.py）已坐实四个接口的路径与字段，本卷补五个"写用例前必须知道"的规则：
  A 归档后拿同一邀请码再加入 → 该不该被拒（手册规则：已归档课程加入失败）
  B 分页参数边界 → page_size 上限到底是多少、超了回什么（上卷撞到 data=list 却没见过明细）
  C 列表支持不支持按 status 过滤 → 决定用例是"拉全量自己挑"还是"带参数精准查"
  D 建课字段校验：空名 / 超长 / 同名重复 → 为将来接口负向矩阵定预期，不靠猜
  E 同一学生重复加入同一门 active 课 → 幂等还是报错（关系到用例能不能重跑）
副作用纪律：新建的课一律进 created 清单，finally 无条件归档；绝不碰 /permanent；
  归档失败只打 warning（不然会盖掉主流程真实失败原因——L5 踩过的坑）
运行：& ".venv\Scripts\python.exe" "script\probe_api_course_write2.py"
"""
import os
import sys
import json
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, STUDENT_BASE_URL, USERNAME, PASSWORD,
                    STUDENT_USERNAME, STUDENT_PASSWORD, HAS_STUDENT)
from api.base_api import BaseApi
from api.login_api import LoginApi

C = "/courses"
ARCHIVED_COURSE = ("26", "C9Y946")   # 上一卷建的课，已归档，正好当 A 步现成素材

teacher = BaseApi(BASE_URL)
t_token = LoginApi(BASE_URL).login_and_get_token(USERNAME, PASSWORD)
stu = BaseApi(STUDENT_BASE_URL) if HAS_STUDENT else None
s_token = (LoginApi(STUDENT_BASE_URL).login_and_get_token(STUDENT_USERNAME, STUDENT_PASSWORD)
           if HAS_STUDENT else None)

created = []   # 本次新建课程 id，收尾全部归档


def brief(tag, resp, keep=600):
    """打一行 HTTP + 返回体（侦察用：结构要看得见）"""
    try:
        body = resp.json()
    except ValueError:
        body = {"_raw": resp.text[:200]}
    print(f"\n### {tag}\n    -> HTTP {resp.status_code}")
    print("    " + json.dumps(body, ensure_ascii=False)[:keep].replace("\n", "\n    "))
    return body


def create(name):
    """建一门课并登记进清理清单"""
    resp = teacher.post(C, token=t_token, json={"name": name})
    body = brief(f"建课 name={name!r}", resp, keep=300)
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    if data.get("id"):
        created.append(data["id"])
    return body, data


def items_of(body):
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return None          # data 不是 dict（校验错误 list / null）→ 让调用方看见异常形态
    return data.get("items") or []


def main():
    # ---------- A 归档课重复加入：拿现成的已归档码试 ----------
    if HAS_STUDENT:
        cid, icode = ARCHIVED_COURSE
        brief(f"A-1 学生用已归档课邀请码 {icode} 再加入（预期被拒）",
              stu.post(f"{C}/join", token=s_token, json={"invite_code": icode}))

    # ---------- B 分页边界：100 / 101 / 200 三档，看 data 形态什么时候变 list ----------
    for size in (100, 101, 200):
        body = brief(f"B page_size={size}", teacher.get(C, token=t_token,
                                                     params={"page": 1, "page_size": size}), keep=300)
        print(f"    -> data 类型={type(body.get('data')).__name__}  items={len(items_of(body) or [])}")

    # ---------- C status 过滤参数支持不支持 ----------
    for q in ({"status": "active"}, {"status": "archived"}, {}):
        body = brief(f"C GET /courses 带过滤 {q}", teacher.get(C, token=t_token,
                                                              params={"page": 1, "page_size": 100, **q}), keep=200)
        its = items_of(body)
        if its is None:
            print("    -> data 非 dict，参数触发校验错误")
        else:
            print(f"    -> 返回 {len(its)} 门，status 分布={sorted({c.get('status') for c in its})}")

    # ---------- D 建课字段校验 ----------
    print("\n===== D 建课字段校验 =====")
    brief("D-1 空课程名 name=''", teacher.post(C, token=t_token, json={"name": ""}))
    brief("D-2 缺 name 字段 body={}", teacher.post(C, token=t_token, json={}))
    brief(f"D-3 超长名 129 字符（UI 输入框 maxlength=128）",
          teacher.post(C, token=t_token, json={"name": "A" * 129}))
    body, data = create(f"AT-API2-{time.strftime('%m%d%H%M%S')}")
    if data.get("id"):
        print(f"    正常建课 id={data['id']} 码={data.get('invite_code')} status={data.get('status')}")
        # 同名再来一次：看是不是允许重名（允许的话清理清单会有两门同名）
        same_name = create(data.get("name"))
        print(f"    重复建同名课结果：code={same_name[0].get('code')} msg={same_name[0].get('message')!r}")
        if same_name[1].get("id"):
            print(f"    系统允许同名课程（同名也能建成功，id={same_name[1]['id']}）")

    # ---------- E 重复加入同一门 active 课：幂等 or 报错 ----------
    if HAS_STUDENT and data.get("id") and data.get("invite_code"):
        icode = data["invite_code"]
        brief(f"E-1 首次加入 {icode}（预期成功）",
              stu.post(f"{C}/join", token=s_token, json={"invite_code": icode}))
        brief(f"E-2 同一码重复加入 {icode}（看是幂等成功还是报错）",
              stu.post(f"{C}/join", token=s_token, json={"invite_code": icode}))
        mm = brief(f"E-3 成员表看 demo_student 会不会出现两条",
                   teacher.get(f"{C}/{data['id']}/members", token=t_token,
                               params={"page": 1, "page_size": 20}))
        its = (mm.get("data") or {}).get("items") or []
        print(f"    成员条数={len(its)}  明细={[ (m.get('student_no'), m.get('status')) for m in its ]}")

    # ---------- 清理交给 finally 统一做（见文件尾），中途异常也能收尾 ----------


def cleanup():
    """本次建的课全部归档。为什么放 finally：主流程中途挂了也不能给环境留垃圾课"""
    if not created:
        print("\n本次未新建课程，无需清理。")
        return
    print("\n===== 收尾归档 =====")
    for cid in created:
        try:
            r = teacher.delete(f"{C}/{cid}", token=t_token)
            print(f"    DELETE /courses/{cid} -> HTTP {r.status_code}")
        except Exception as e:
            # 清理失败只警告不上抛：否则 finally 的异常会盖掉主流程真正的第一步失败原因
            print(f"    [清理失败，需手动归档 id={cid}] {e}")


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
