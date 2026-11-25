#!/usr/bin/env python3
"""🖼️ 把 backgrounds/ 里的照片做成皮肤底图：每张照片在 Poweramp 皮肤列表里是一个「湖光 · 名字」。

文件名规则：  序号_名字@横向中心.jpg
  - 序号决定顺序，第 1 张是默认底图
  - 名字显示在 Poweramp 皮肤设置里（可以用中文）
  - @57 表示竖屏裁剪时以照片宽度 57% 处为中心（可省略，默认 50）
例：1_湖光@57.jpg、2_海边.jpg、3_雪山@40.png

每张照片生成：手机竖/横屏、平板竖/横屏 4 个尺寸，统一压暗方便看字。
最多用前 8 张（APK 别太大）。
"""
import os, re, glob, html
from PIL import Image, ImageEnhance, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "backgrounds")
RES = os.path.join(ROOT, "lakeside_skin", "src", "main", "res")
SIZES = {  # 资源目录: (宽, 高)
    "drawable-nodpi": (1080, 2340),
    "drawable-land-nodpi": (2340, 1080),
    "drawable-sw600dp-nodpi": (1600, 2560),
    "drawable-sw600dp-land-nodpi": (2560, 1600),
}
MAX = 8
NAVY = (8, 16, 28)


def shade(im):
    """从上到下压暗：顶部（状态栏、列表开头常是亮天空）和底部（播放控制）更暗。"""
    w, h = im.size
    g = Image.new("L", (1, h))
    for y in range(h):
        t = y / (h - 1)
        a = 0.56 - 0.10 * (t / 0.45) if t < 0.45 else 0.46 + 0.28 * ((t - 0.45) / 0.55)
        g.putpixel((0, y), int(255 * a))
    return Image.composite(Image.new("RGB", (w, h), NAVY), im, g.resize((w, h)))


def render(src, tw, th, cx):
    W, H = src.size
    ar = tw / th
    cw, ch = (int(H * ar), H) if W / H > ar else (W, int(W / ar))
    x0 = int(min(max(cx * W - cw / 2, 0), W - cw))
    y0 = (H - ch) // 2
    im = src.crop((x0, y0, x0 + cw, y0 + ch)).resize((tw, th), Image.LANCZOS)
    return shade(ImageEnhance.Color(im).enhance(1.08))


def main():
    files = sorted(f for f in glob.glob(os.path.join(SRC, "*"))
                   if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))[:MAX]
    if not files:
        raise SystemExit("backgrounds/ 里没有照片")
    for d in SIZES:  # 清掉旧的生成图
        for old in glob.glob(os.path.join(RES, d, "lake_bg_*.jpg")):
            os.remove(old)

    names = []
    for i, f in enumerate(files, 1):
        stem = os.path.splitext(os.path.basename(f))[0]
        m = re.match(r"^\d*[_\-\s]*(.*?)(?:@(\d{1,3}))?$", stem)
        label = (m.group(1) or "").strip() or f"底图 {i}"
        cx = int(m.group(2)) / 100 if m.group(2) else 0.5
        src = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        for d, (tw, th) in SIZES.items():
            os.makedirs(os.path.join(RES, d), exist_ok=True)
            render(src, tw, th, cx if th > tw else 0.5).save(
                os.path.join(RES, d, f"lake_bg_{i}.jpg"), quality=86, optimize=True)
        names.append(label)
        print(f"🖼️ {i}. {label}  (中心 {cx:.0%})  ← {os.path.basename(f)}")

    # 样式：每张底图一套 列表背景 + 均衡器背景
    st = ['<?xml version="1.0" encoding="utf-8"?>',
          '<!-- 由 tools/gen_backgrounds.py 生成，不要手改 -->',
          '<resources xmlns:android="http://schemas.android.com/apk/res/android" xmlns:tools="http://schemas.android.com/tools" tools:ignore="ResourceCycle, NewApi">']
    for i, label in enumerate(names, 1):
        st += [
            f'\t<string name="lake_bg_name_{i}">{html.escape(label)}</string>',
            f'\t<style name="LakeSkin_TopListWidget_{i}" parent="com.maxmpz.audioplayer:TopListWidget">',
            f'\t\t<item name="android:background">@drawable/lake_bg_{i}</item>',
            '\t\t<item name="com.maxmpz.audioplayer:listMilkMode">none</item>',
            '\t</style>',
            f'\t<style name="LakeSkin_TopEqLayout_{i}" parent="com.maxmpz.audioplayer:TopEqLayout">',
            f'\t\t<item name="android:background">@drawable/lake_bg_{i}</item>',
            '\t</style>',
            f'\t<string name="lake_skin_name_{i}">湖光 · {html.escape(label)}</string>',
            f'\t<style name="LakeSkin_{i}" parent="LakeSkin">',
            f'\t\t<item name="com.maxmpz.audioplayer:TopListWidget">@style/LakeSkin_TopListWidget_{i}</item>',
            f'\t\t<item name="com.maxmpz.audioplayer:TopEqLayout">@style/LakeSkin_TopEqLayout_{i}</item>',
            '\t</style>',
            f'\t<style name="LakeSkin_Bg_{i}">',
            f'\t\t<item name="com.maxmpz.audioplayer:TopListWidget">@style/LakeSkin_TopListWidget_{i}</item>',
            f'\t\t<item name="com.maxmpz.audioplayer:TopEqLayout">@style/LakeSkin_TopEqLayout_{i}</item>',
            '\t</style>',
        ]
    st.append('</resources>\n')
    open(os.path.join(RES, "values", "lake_bg_gen.xml"), "w", encoding="utf-8").write("\n".join(st))

    # skins.xml：每张照片一个皮肤（未认证皮肤在 Poweramp 里没有设置页，所以不用选项，直接在皮肤列表里选）
    sk = []
    for i in range(1, len(names) + 1):
        sk += [f'\t<skin name="@string/lake_skin_name_{i}" author="@string/lake_skin_author"',
               f'\t\tdescription="@string/lake_skin_desc" style="@style/LakeSkin_{i}" allowNewPadding="true"/>']
    p = os.path.join(RES, "xml", "skins.xml")
    s = open(p, encoding="utf-8").read()
    s = re.sub(r"(<!--BG_SKINS_START-->\n).*?(\t*<!--BG_SKINS_END-->)",
               lambda m: m.group(1) + "\n".join(sk) + "\n" + m.group(2), s, flags=re.S)
    open(p, "w", encoding="utf-8").write(s)
    print(f"✅ 共 {len(names)} 张底图")


if __name__ == "__main__":
    main()
