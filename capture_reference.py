"""
辅助工具：截取参考图片
运行后按快捷键截取屏幕区域，保存为参考图片

用法:
    python capture_reference.py video_ended
    python capture_reference.py next_video
"""

import sys
import time
from pathlib import Path

try:
    import pyautogui
    from PIL import ImageGrab
except ImportError:
    print("请先安装依赖: pip install pyautogui pillow")
    sys.exit(1)

IMAGES_DIR = Path(__file__).parent / "images"


def capture_region(name):
    """引导用户截取屏幕区域"""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = IMAGES_DIR / f"{name}.png"

    print(f"\n准备截取: {name}")
    print("-" * 40)
    print("操作步骤:")
    print("  1. 先把目标画面准备好（让要截取的元素可见）")
    print("  2. 按 Enter 键开始截取")
    print("  3. 用鼠标拖拽选择区域（左上角→右下角）")

    input("\n按 Enter 开始...")

    print("\n请在 5 秒内将鼠标移到要截取区域的【左上角】...")
    time.sleep(5)
    x1, y1 = pyautogui.position()
    print(f"  左上角: ({x1}, {y1})")

    print("请在 5 秒内将鼠标移到要截取区域的【右下角】...")
    time.sleep(5)
    x2, y2 = pyautogui.position()
    print(f"  右下角: ({x2}, {y2})")

    # 截取区域
    region = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    screenshot = ImageGrab.grab(bbox=region)
    screenshot.save(output_path)
    print(f"\n[OK] 已保存到: {output_path}")
    print(f"     尺寸: {screenshot.size[0]}x{screenshot.size[1]}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python capture_reference.py video_ended   # 截取视频结束标志")
        print("  python capture_reference.py next_video    # 截取未播放视频标志")
        print("  python capture_reference.py <自定义名称>")
        sys.exit(0)

    name = sys.argv[1]
    capture_region(name)


if __name__ == "__main__":
    main()
