"""
测试数据加载器：yaml -> Python 数据 -> pytest 参数化
这是"数据驱动"的最后一公里：数据躺在文件里，代码只负责读和替换
"""
import os

import yaml

from config import (USERNAME, PASSWORD, WRONG_PASSWORD, NOT_EXIST_USER,
                    RED_USERNAME, RED_PASSWORD)

# 占位符 -> 真实值（全部来源于 config.py，换账号只改 config）
_REPLACEMENTS = {
    "{user}": USERNAME,
    "{pwd}": PASSWORD,
    "{wrong_pwd}": WRONG_PASSWORD,
    "{not_exist}": NOT_EXIST_USER,
    # 实测：账号中间空格不会被 trim、登录失败，专门用来造这种数据
    "{mid_user}": f"{USERNAME[:2]} {USERNAME[2:]}",
}

# red 系占位符（negative 用例专用，失败记在废弃账号头上）：配了才登记。
# 为什么不直接写死映射？没配 .env 时 RED_USERNAME=None，
# 替换结果会变成字符串 "None"——报错时查一个不存在的"None"账号，莫名其妙。
# 没配时 negative 用例已被 skipif 跳过，这些占位符永远轮不到被消费，安全。
if RED_USERNAME and RED_PASSWORD:
    _REPLACEMENTS.update({
        "{red_user}": RED_USERNAME,
        "{red_pwd}": RED_PASSWORD,
        "{red_mid_user}": f"{RED_USERNAME[:2]} {RED_USERNAME[2:]}",
    })


def _fill(value):
    """递归地把字符串里的占位符换掉，列表/字典都能穿透"""
    if isinstance(value, str):
        for k, v in _REPLACEMENTS.items():
            value = value.replace(k, v)
        return value
    if isinstance(value, list):
        return [_fill(i) for i in value]
    if isinstance(value, dict):
        return {k: _fill(v) for k, v in value.items()}
    return value


def load_data(section, filename="login.yaml"):
    """读指定 yaml 文件的指定段（如 front_validate），返回 list[dict]
    filename 默认 login.yaml：UI 层旧调用 load_data(section) 一字不用改；
    接口层传 load_data(section, "api_login.yaml") 就能复用同一套占位符替换逻辑
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    with open(path, encoding="utf-8") as f:
        all_data = yaml.safe_load(f)
    return _fill(all_data[section])