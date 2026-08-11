"""
自动播放下一个视频脚本
使用图像识别检测视频播放状态并自动点击下一个视频

使用前准备:
1. pip install pyautogui pillow opencv-python
2. 截取以下参考图片，保存到 images/ 文件夹:
   - video_ended.png: 视频播放结束时的标志（如重播按钮、进度条满等）
   - next_video.png:  播放列表中"未开始"视频的标志（如未播放的图标/缩略图边上的标记）
   - play_button.png: 视频播放器中央的播放按钮
   - video_end_list.png: 播放列表中"已完成"视频的标志（列表全部播完时用于定位并向下滚动）
3. 运行脚本: python auto_play_next.py
"""

import pyautogui
import time
import sys
import os
import win32gui
import win32con
from pathlib import Path
from datetime import datetime
from PIL import ImageGrab

# ============ 配置 ============
IMAGES_DIR = Path(__file__).parent / "images"

# 视频播放结束的标志图片（截取播放器上出现的结束标识，比如重播按钮）
VIDEO_ENDED_IMG = IMAGES_DIR / "video_ended.png"

# 播放列表中未播放视频的标志图片（支持两种样式，截取列表中未开始视频旁边的标识）
NEXT_VIDEO_IMGS = [
    IMAGES_DIR / "next_video.png",     # 样式1
    IMAGES_DIR / "next_video_2.png",   # 样式2
]

# 视频播放器中央的播放按钮图片
PLAY_BUTTON_IMG = IMAGES_DIR / "play_button.png"

# 播放列表中"已完成"视频的标志图片（无新未播放视频时，用于定位并向下滚动列表）
VIDEO_END_LIST_IMG = IMAGES_DIR / "video_end_list.png"

# 检测间隔（秒）
CHECK_INTERVAL = 600

# 图像匹配置信度（0-1，越高越严格，建议 0.8-0.9）
CONFIDENCE = 0.85

# 点击条目后等待页面加载的时间（秒），然后再找播放按钮
CLICK_WAIT = 3

# 等待播放按钮出现的最大时间（秒）
PLAY_BUTTON_TIMEOUT = 10

# 判定"同一位置"的像素容差（防止重复点击同一个条目）
POSITION_TOLERANCE = 20

# ==== 列表滚动（无新的未播放视频时，向下滚动查找更多）====
# 鼠标滚轮滚动量（负值=向下；Windows 下 dwData 120≈一格滚轮）
SCROLL_AMOUNT = -500
# 单轮检测中最多向下滚动的次数
SCROLL_MAX_ATTEMPTS = 5
# 悬停/滚动后的等待时间（秒）
SCROLL_WAIT = 1

# ==== 播放完毕后自动关机 ====
# 关机前的延迟（秒），留出取消时间；取消命令: shutdown /a
SHUTDOWN_DELAY = 60

# Debug: 保存分析时的截屏到 debug/ 文件夹
DEBUG_SCREENSHOT = True
DEBUG_DIR = Path(__file__).parent / "debug"

# pyautogui 安全设置
pyautogui.FAILSAFE = True  # 鼠标移到左上角可紧急中止
pyautogui.PAUSE = 0.5


def check_images_exist():
    """检查参考图片是否存在"""
    if not IMAGES_DIR.exists():
        IMAGES_DIR.mkdir(parents=True)
        print(f"[INFO] 已创建 images/ 文件夹: {IMAGES_DIR}")
        print(f"[INFO] 请将参考截图放入该文件夹:")
        print(f"       - {VIDEO_ENDED_IMG.name}: 视频结束时的标志截图")
        print(f"       - next_video.png: 未播放视频样式1截图")
        print(f"       - next_video_2.png: 未播放视频样式2截图（可选）")
        print(f"       - {PLAY_BUTTON_IMG.name}: 播放器中央播放按钮截图")
        print(f"\n截图提示:")
        print(f"  1. 用 Windows 截图工具 (Win+Shift+S) 截取")
        print(f"  2. 截取尽量小而独特的区域，避免含太多背景")
        print(f"  3. 确保截图时浏览器缩放为 100%")
        sys.exit(1)

    missing = []
    if not VIDEO_ENDED_IMG.exists():
        missing.append(str(VIDEO_ENDED_IMG))
    if not any(img.exists() for img in NEXT_VIDEO_IMGS):
        missing.append(str(NEXT_VIDEO_IMGS[0]) + " (至少需要一张)")
    if not PLAY_BUTTON_IMG.exists():
        missing.append(str(PLAY_BUTTON_IMG))

    if missing:
        print("[ERROR] 缺少以下参考图片:")
        for m in missing:
            print(f"  - {m}")
        print("\n请截取对应的UI元素图片并保存到上述路径")
        sys.exit(1)

    # 非必需：缺失时仅关闭"列表播完自动向下滚动"功能，不阻断运行
    if not VIDEO_END_LIST_IMG.exists():
        print(f"[WARN] 未找到 {VIDEO_END_LIST_IMG.name}，列表播完后的自动向下滚动功能将不可用")


def find_chrome_window():
    """查找Chrome窗口句柄"""
    result = []
    def enum_callback(hwnd, _):
        if win32gui.IsWindow(hwnd) and win32gui.GetWindowText(hwnd):
            if 'chrome' in win32gui.GetWindowText(hwnd).lower():
                result.append(hwnd)
    win32gui.EnumWindows(enum_callback, None)
    return result[0] if result else None


def show_chrome():
    """显示Chrome窗口并最大化（从最小化恢复并最大化）"""
    hwnd = find_chrome_window()
    if hwnd:
        # 先模拟Alt键释放，绕过Windows前台窗口限制
        import ctypes
        ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)  # Alt up
        # SW_MAXIMIZE 会同时从最小化恢复并最大化窗口，保证检测时UI位置一致
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # 备用方案：用BringWindowToTop
            win32gui.BringWindowToTop(hwnd)
        print("[CHROME] 已恢复并最大化Chrome窗口")
    else:
        print("[WARN] 未找到Chrome窗口")


def hide_chrome():
    """最小化Chrome窗口"""
    hwnd = find_chrome_window()
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        print("[CHROME] 已最小化Chrome窗口")
    else:
        print("[WARN] 未找到Chrome窗口")


def save_debug_screenshot(label="screen"):
    """保存当前屏幕截图用于调试"""
    if not DEBUG_SCREENSHOT:
        return
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S")
    # filename = DEBUG_DIR / f"{timestamp}_{label}.png"
    filename = DEBUG_DIR / f"debug.png"
    screenshot = ImageGrab.grab()
    screenshot.save(filename)
    print(f"[DEBUG] 截屏已保存: {filename}")


def find_on_screen(image_path, confidence=CONFIDENCE):
    """在屏幕上查找图片，返回中心坐标或None"""
    try:
        location = pyautogui.locateOnScreen(str(image_path), confidence=confidence)
        if location:
            return pyautogui.center(location)
    except pyautogui.ImageNotFoundException:
        pass
    except Exception as e:
        print(f"[WARN] 图像识别出错: {e}")
    return None


def find_all_on_screen(image_path, confidence=CONFIDENCE):
    """在屏幕上查找所有匹配的图片，返回中心坐标列表（按从上到下排序）"""
    results = []
    try:
        locations = pyautogui.locateAllOnScreen(str(image_path), confidence=confidence)
        for loc in locations:
            center = pyautogui.center(loc)
            results.append(center)
    except pyautogui.ImageNotFoundException:
        pass
    except Exception as e:
        print(f"[WARN] 图像识别出错: {e}")
    # 按 Y 坐标排序（从上到下），Y 相同时按 X 排序（从左到右）
    results.sort(key=lambda p: (p.y, p.x))
    return results


def is_same_position(pos1, pos2, tolerance=POSITION_TOLERANCE):
    """判断两个坐标是否是同一位置（在容差范围内）"""
    return abs(pos1.x - pos2.x) <= tolerance and abs(pos1.y - pos2.y) <= tolerance


def is_video_ended():
    """检测视频是否播放结束"""
    pos = find_on_screen(VIDEO_ENDED_IMG)
    return pos is not None


def find_next_video(clicked_positions):
    """
    查找播放列表中下一个未播放的视频，支持两种样式，跳过已点击过的位置。
    返回坐标或 None。
    """
    # 合并两种样式的检测结果
    all_positions = []
    for img in NEXT_VIDEO_IMGS:
        if img.exists():
            all_positions.extend(find_all_on_screen(img))
    if not all_positions:
        return None

    # 去重（两种样式可能匹配到同一个位置）
    unique_positions = []
    for pos in all_positions:
        if not any(is_same_position(pos, u) for u in unique_positions):
            unique_positions.append(pos)
    all_positions = sorted(unique_positions, key=lambda p: (p.y, p.x))

    print(f"[INFO] 找到 {len(all_positions)} 个未播放条目")

    # 跳过已经点击过的位置，找到第一个新位置
    for pos in all_positions:
        already_clicked = any(
            is_same_position(pos, clicked)
            for clicked in clicked_positions
        )
        if not already_clicked:
            return pos

    # 所有找到的位置都点过了，可能页面刷新后图标复位，重新从第一个开始
    print("[WARN] 所有检测到的条目均已点击过，尝试点击第一个")
    return all_positions[0]


def click_position(pos):
    """模拟点击指定位置"""
    print(f"[ACTION] 点击位置: ({pos.x}, {pos.y})")
    pyautogui.click(pos.x, pos.y)


def wait_for_play_button(timeout=PLAY_BUTTON_TIMEOUT):
    """等待播放按钮出现并返回其坐标，超时返回None"""
    elapsed = 0
    while elapsed < timeout:
        pos = find_on_screen(PLAY_BUTTON_IMG)
        if pos:
            return pos
        time.sleep(1)
        elapsed += 1
    return None


def hover_and_scroll_down():
    """
    悬停到最近（列表最下方）带有"已完成"图标的条目上，并向下滚动鼠标滚轮。
    用于列表中没有新的未播放视频时，滚动显示后续更多条目。
    返回 True 表示已执行滚动，False 表示未找到"已完成"条目。
    """
    positions = find_all_on_screen(VIDEO_END_LIST_IMG)
    if not positions:
        print("[SCROLL] 未找到\"已完成\"条目，无法定位滚动位置")
        return False

    # find_all_on_screen 已按从上到下排序，取最下方（最近）的一个作为悬停点
    target = positions[-1]
    print(f"[SCROLL] 找到 {len(positions)} 个\"已完成\"条目，"
          f"悬停到最近的一个 ({target.x}, {target.y}) 并向下滚动")
    # 先移动鼠标悬停，确保滚轮作用于播放列表区域
    pyautogui.moveTo(target.x, target.y)
    time.sleep(SCROLL_WAIT)
    pyautogui.scroll(SCROLL_AMOUNT)
    time.sleep(SCROLL_WAIT)
    return True


def ask_shutdown():
    """启动时询问：列表全部播完后是否自动关机"""
    while True:
        ans = input("[询问] 播放列表全部播完后是否自动关机? (y/N): ").strip().lower()
        if ans in ("y", "yes"):
            print("[INFO] 已选择：播完后自动关机")
            return True
        if ans in ("", "n", "no"):
            print("[INFO] 已选择：播完后不关机")
            return False
        print("请输入 y 或 n")


def shutdown_computer():
    """执行 Windows 关机（留出延迟以便取消）"""
    print(f"[SHUTDOWN] 列表已全部播完，将在 {SHUTDOWN_DELAY} 秒后关机")
    print("[SHUTDOWN] 如需取消，请在命令行执行: shutdown /a")
    os.system(f"shutdown /s /t {SHUTDOWN_DELAY}")


def main():
    print("=" * 50)
    print("  视频自动播放脚本")
    print("=" * 50)
    print(f"  检测间隔: {CHECK_INTERVAL}s")
    print(f"  匹配置信度: {CONFIDENCE}")
    print(f"  安全退出: 将鼠标快速移到屏幕左上角")
    print("=" * 50)

    check_images_exist()

    shutdown_when_done = ask_shutdown()

    print("\n[START] 开始监控... (Ctrl+C 退出)\n")

    videos_played = 0
    clicked_positions = []  # 记录已点击过的位置，防止重复

    try:
        while True:
            # 检测前：显示Chrome窗口
            show_chrome()
            time.sleep(1)

            save_debug_screenshot("check")
            if is_video_ended():
                print("[DETECT] 检测到视频播放结束!")

                # 查找下一个未播放的视频（跳过已点击的）
                next_pos = find_next_video(clicked_positions)
                if next_pos:
                    # 第1步：点击播放列表中的条目
                    print(f"[STEP 1] 点击播放列表条目...")
                    click_position(next_pos)
                    clicked_positions.append(next_pos)
                    time.sleep(CLICK_WAIT)

                    # 第2步：等待并点击播放器中央的播放按钮
                    print(f"[STEP 2] 等待播放按钮出现...")
                    play_btn = wait_for_play_button()
                    if play_btn:
                        click_position(play_btn)
                        print(f"[STEP 2] 已点击播放按钮")
                    else:
                        print(f"[WARN] 未找到播放按钮，可能视频已自动开始播放")

                    videos_played += 1
                    print(f"[INFO] 已自动播放第 {videos_played} 个视频")

                    # 等待"播放结束"标志消失，确认新视频正在播放
                    print(f"[WAIT] 等待视频开始播放（结束标志消失）...")
                    wait_elapsed = 0
                    while wait_elapsed < 30:
                        time.sleep(2)
                        wait_elapsed += 2
                        if not is_video_ended():
                            print(f"[OK] 新视频已开始播放，恢复监控")
                            break
                    else:
                        print(f"[WARN] 等待超时，结束标志仍在，继续监控")
                else:
                    print("[INFO] 播放列表中没有找到新的未播放视频，尝试向下滚动查找更多...")
                    found_after_scroll = False
                    for attempt in range(1, SCROLL_MAX_ATTEMPTS + 1):
                        print(f"[SCROLL] 第 {attempt}/{SCROLL_MAX_ATTEMPTS} 次向下滚动")
                        if not hover_and_scroll_down():
                            break  # 没有"已完成"条目可供定位，停止滚动
                        save_debug_screenshot("after_scroll")
                        if find_next_video(clicked_positions):
                            print("[INFO] 滚动后找到新的未播放视频，将在下一轮处理")
                            found_after_scroll = True
                            break

                    if not found_after_scroll:
                        print("[INFO] 滚动后仍未找到未播放视频，可能已全部播完")
                        hide_chrome()
                        if shutdown_when_done:
                            shutdown_computer()
                            break  # 已安排关机，退出监控循环
                        print("[INFO] 等待下一轮检测")
                        time.sleep(CHECK_INTERVAL)
                    continue
            else:
                # 正常轮询，不打印避免刷屏
                pass

            # 检测后：隐藏Chrome窗口
            hide_chrome()

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n[EXIT] 脚本已停止，本次共自动播放了 {videos_played} 个视频")
if __name__ == "__main__":
    main()
