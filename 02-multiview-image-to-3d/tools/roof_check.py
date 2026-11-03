"""四视图屋顶朝向一致性闸门（2026-10-21，P1：圆胖玩具 × 黏土 的四视图正面画成山墙、左右也是山墙，3D 被凑成怪形状）。

每个视图看剪影顶部：山墙面（三角）顶上很窄，长边（屋檐面）顶上是一条宽屋脊。
指标 top = 剪影最高处往下 12% 高度那一行的宽度 / 剪影最大宽度；top < GABLE 判山墙，否则判长边。
（烟囱会把"最高处"抬上去，所以先去掉剪影里宽度 < 8% 的细高凸起再量。）
规则（四视图朝向约定：正面 = 带门的长墙，侧面 = 山墙）：
  侧面的 top 平均比正 / 背小 SIDE_GAP 以上（屋脊沿正面走向）；正 / 背的 top 差 ≤ PAIR，左 / 右的 top 差 ≤ PAIR
  （成对的两面屋顶形状要一样）。山墙 / 长边的分类（GABLE）只用来报告，不当闸门——窝棚单坡顶、沙漠平顶侧面不是三角。
  只按阈值判正面不够：正面中间有老虎窗的长边（0.39）和山墙朝前的正面（0.34）分不开，但后者的背面是 0.66，配不上对。
  不满足的整张四视图判不过，应重出（别交给 fix_sides 硬掰）。

    python roof_check.py <四视图目录>…      → 每个目录一行，退出码 = 不过的个数
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
GABLE = 0.32
PAIR = 0.2
SIDE_GAP = 0.15
WANT = {'front': 'eave', 'back': 'eave', 'right': 'gable', 'left': 'gable'}


def top_ratio(p: Path) -> float:
    m = np.asarray(Image.open(p).convert('RGBA'))[..., 3] > 0
    w = m.sum(1)
    rows = np.where(w > 0)[0]
    wmax = w.max()
    body = rows[w[rows] >= 0.08 * wmax]          # 跳过烟囱尖这种细凸起
    top, bottom = body[0], rows[-1]
    r = top + int(0.12 * (bottom - top))
    return float(w[r] / wmax)


def check(d: Path) -> dict:
    t = {v: round(top_ratio(d / f'{v}.png'), 3) for v in WANT}
    kind = {v: 'gable' if x < GABLE else 'eave' for v, x in t.items()}
    bad = []
    # 不强求山墙：窝棚的单坡顶、沙漠的平顶，侧面也不是三角。有屋脊时才要求侧面比正 / 背明显"尖"（屋脊沿正面走向）；
    # 四面顶部都差不多（水桶、水罐、平顶）= 没有屋脊，不查方向
    ridgeless = max(t.values()) - min(t.values()) <= PAIR
    if not ridgeless and (t['right'] + t['left']) / 2 > (t['front'] + t['back']) / 2 - SIDE_GAP:
        bad.append('侧面不比正背面尖（屋脊方向不对）')
    if abs(t['front'] - t['back']) > PAIR:
        bad.append('front/back 不成对')
    if abs(t['right'] - t['left']) > PAIR:
        bad.append('right/left 不成对')
    return {'top': t, 'kind': kind, 'ok': not bad, 'bad': bad}


def main():
    n_bad = 0
    for a in sys.argv[1:]:
        d = Path(a)
        r = check(d)
        (d / 'roof_check.json').write_text(json.dumps(r, ensure_ascii=False, indent=1))
        n_bad += not r['ok']
        zh = {'gable': '山墙', 'eave': '长边'}
        print(f"{d.name:<22} {'通过' if r['ok'] else '不过'}  " +
              '  '.join(f"{v} {zh[r['kind'][v]]}({r['top'][v]})" for v in WANT) +
              (f"   不对：{','.join(r['bad'])}" if r['bad'] else ''))
    return n_bad


if __name__ == '__main__':
    sys.exit(main())
