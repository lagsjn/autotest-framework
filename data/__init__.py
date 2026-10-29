"""
测试数据加载器：yaml -> Python 数据 -> pytest 参数化
这是"数据驱动"的最后一公里：数据躺在文件里，代码只负责读和替换
"""
import os

import yaml

from config import USERNAME, PASSWORD, WRONG_PASSWORD, NOT_EXIST_USER

_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "login.yaml")

# 占位符 -> 真实值（全部来源于 config.py，换账号只改 config）
_REPLACEMENTS = {
    "{user}": USERNAME,
    "{pwd}": PASSWORD,
    "{wrong_pwd}": WRONG_PASSWORD,
    "{not_exist}": NOT_EXIST_USER,
    # 实测：账号中间空格不会被 trim、登录失败，专门用来造这种数据
    "{mid_user}": f"{USERNAME[:2]} {USERNAME[2:]}",
}


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


def load_data(section):
    """读 login.yaml 的指定段（如 front_validate），返回 list[dict]"""
    with open(_DATA_FILE, encoding="utf-8") as f:
        all_data = yaml.safe_load(f)
    return _fill(all_data[section])