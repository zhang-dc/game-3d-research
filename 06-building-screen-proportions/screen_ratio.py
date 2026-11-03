"""建筑屏幕比例计算器：引擎投影 sx = x，sy = y·F − z（竖直 1:1，进深 ×F）。

    python screen_ratio.py --depth 6 --storeys 1 --storey 128 --pitch 30 --eave 6 [--F 0.75] [--door 84]
    （进深单位：米 = 格，1 格 = 32 px；其余 px）

输出：墙露出、屋顶屏高、二者之比、墙 ÷ 角色、门 ÷ 角色，并按 README 的目标区间标注。
"""
import argparse
import math

H = 56          # 角色可见身高 px
GRID = 32
FASCIA = 8      # 封檐板厚 px


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--depth', type=float, required=True, help='进深（格/米）')
    ap.add_argument('--storeys', type=int, default=1)
    ap.add_argument('--storey', type=float, default=128, help='层高 px')
    ap.add_argument('--pitch', type=float, default=30, help='坡度 °')
    ap.add_argument('--eave', type=float, default=6, help='挑檐 px')
    ap.add_argument('--jetty', type=float, default=0, help='二层外挑 px')
    ap.add_argument('--F', type=float, default=0.75, help='flatten')
    ap.add_argument('--door', type=float, default=84, help='门高 px')
    a = ap.parse_args()
    D = a.depth * GRID + (a.jetty if a.storeys > 1 else 0)
    half = D / 2 + a.eave
    rise = half * math.tan(math.radians(a.pitch))
    roof = max(rise + half * a.F, (D + 2 * a.eave) * a.F)
    wall = a.storeys * a.storey - (a.eave * a.F + FASCIA)
    r = roof / wall

    def tag(v, lo, hi):
        return '✓' if lo <= v <= hi else ('偏低' if v < lo else '偏高')

    print(f'墙露出 {wall:.0f} px = {wall / H:.2f} H  {tag(wall / H, 1.3, 2.0)}')
    print(f'屋顶屏高 {roof:.0f} px（抬升 {rise:.0f}）  屋顶÷墙 {r:.2f}  {tag(r, 0.9, 1.3)}'
          + ('（后坡露出：坡度 < 俯角）' if math.radians(a.pitch) < math.atan(a.F) else ''))
    print(f'门 {a.door:.0f} px = {a.door / H:.2f} H  {tag(a.door / H, 1.0, 1.5)}')


if __name__ == '__main__':
    main()
