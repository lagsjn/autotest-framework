"""
查沙箱残留：列出环境里所有 AT-* 课程，按 status 分组，重点看**没归档**的
为什么需要这个脚本：写型用例的铁律是"自己造的脏数据自己收"。
finally 里包了归档不等于一定收干净——归档请求本身可能失败（脚本只 warning 不上抛），
残留会污染下轮用例（比如按课程名匹配卡片时撞上历史同名课）。
所以每跑完一批写型用例，应该跑一次这个脚本核对，而不是相信"应该会清理吧"。
只读，零副作用。
"""
import requests
import urllib3

import config

urllib3.disable_warnings()  # 自签名证书，关校验（与 config.VERIFY_SSL 同一套口径）


def main():
    # 1) 登录拿 token：直接走接口层，不依赖 pytest fixture（脚本要能脱离用例独立跑）
    r = requests.post(
        config.BASE_URL + config.API_PREFIX + "/auth/login",
        json={"username": config.USERNAME, "password": config.PASSWORD},
        verify=config.VERIFY_SSL, timeout=20,
    )
    assert r.status_code == 200, f"登录失败 {r.status_code}: {r.text[:300]}"
    body = r.json()
    assert body.get("code") == 0, f"登录业务码非 0: {body}"
    token = body["data"]["access_token"]

    # 2) 翻页拉全量课程（page_size 上限 100，超 100 门课要循环取，不能只看第一页就下结论）
    items, page = [], 1
    while True:
        r = requests.get(
            config.BASE_URL + config.API_PREFIX + "/courses",
            params={"page": page, "page_size": 100},
            headers={"Authorization": f"Bearer {token}"},
            verify=config.VERIFY_SSL, timeout=20,
        )
        assert r.status_code == 200, f"查课程失败 {r.status_code}: {r.text[:300]}"
        data = (r.json() or {}).get("data") or {}
        chunk = data.get("items") or []
        items.extend(chunk)
        total = data.get("total") or 0
        if not chunk or len(items) >= total:
            break
        page += 1

    # 3) 只看 AT-* 沙箱课，按 status 归类
    sandboxes = [c for c in items if str(c.get("name", "")).startswith("AT-")]
    print(f"课程总数 {len(items)}（接口报 total={total}），其中 AT-* 沙箱课 {len(sandboxes)} 门")

    by_status = {}
    for c in sandboxes:
        by_status.setdefault(str(c.get("status")), []).append(c)
    for st, lst in sorted(by_status.items()):
        flag = "⚠ 需清理" if st != "archived" else "已归档"
        print(f"  status={st:<10} {len(lst):>3} 门  {flag}")
        if st != "archived":
            for c in lst[:15]:
                print(f"      id={c.get('id'):<6} name={c.get('name')}")

    leftover = [c for c in sandboxes if str(c.get("status")) != "archived"]
    print(f"\n结论：未归档残留 {len(leftover)} 门"
          + ("，干净" if not leftover else "，上面列出的是待手动归档清单"))


if __name__ == "__main__":
    main()
