import os
import json
import shutil
import requests
import time
import sys

# ================= 配置区域 =================
# 1. Eagle API Token (在偏好设置 -> 开发者选项里复制)
EAGLE_API_TOKEN = "9f71f838-e10c-463d-9ca0-2648f3e409c8" 

# 2. Eagle 库的物理路径 (也就是你想掏空的那个库)
EAGLE_LIBRARY_PATH = r"K:\hentai\H_Video_1_1.library"

# 3. 导出目标路径 (强烈建议和库在同一个盘符，实现瞬间移动)
TARGET_EXPORT_PATH = r"K:\hentai\H_Video_1_1"

# Eagle API 默认地址
API_URL = "http://localhost:41595/api/folder/list"
# ===========================================

def get_folder_tree_from_api():
    """
    通过 Eagle API 获取完整的目录树结构
    """
    print(f"正在连接 Eagle API 获取目录结构...")
    try:
        params = {'token': EAGLE_API_TOKEN}
        response = requests.get(API_URL, params=params)
        
        if response.status_code != 200:
            print(f"❌ API 请求失败: {response.status_code}")
            return None
            
        data = response.json()
        if data.get('status') != 'success':
            print(f"❌ API 返回错误: {data.get('data')}")
            return None
            
        return data.get('data', [])
    except Exception as e:
        print(f"❌ 连接 Eagle 失败，请确保 Eagle 正在运行: {e}")
        return None

def build_folder_mapping(folder_list, parent_path=""):
    """
    递归解析 API 返回的 JSON，构建 {ID: 完整路径} 的字典
    """
    mapping = {}
    for folder in folder_list:
        # 清洗文件名，防止非法字符
        folder_name = folder['name']
        safe_name = "".join([c for c in folder_name if c not in r'\/:*?"<>|'])
        
        current_path = os.path.join(parent_path, safe_name)
        mapping[folder['id']] = current_path
        
        # 递归处理子文件夹
        children = folder.get('children', [])
        if children:
            mapping.update(build_folder_mapping(children, current_path))
            
    return mapping

def get_unique_path(base_dir, filename):
    """防止文件名冲突，自动重命名"""
    name, ext = os.path.splitext(filename)
    counter = 1
    new_name = filename
    full_path = os.path.join(base_dir, new_name)
    
    while os.path.exists(full_path):
        new_name = f"{name}_{counter}{ext}"
        full_path = os.path.join(base_dir, new_name)
        counter += 1
    return full_path

def main():
    # --- 阶段 1: 从 Eagle 活体进程中获取目录结构 ---
    folder_tree = get_folder_tree_from_api()
    if not folder_tree:
        print("⚠️ 无法获取目录结构。请检查 Eagle 是否打开且 Token 正确。")
        sys.exit(1)
        
    folder_mapping = build_folder_mapping(folder_tree)
    print(f"✅ 成功获取目录结构，包含 {len(folder_mapping)} 个文件夹。")
    
    # --- 阶段 2: 提示用户关闭 Eagle ---
    print("\n" + "="*50)
    print("🚨 【重要提示】 🚨")
    print("目录结构已保存到内存。")
    print("为了防止文件被占用导致移动失败，**请现在手动关闭 Eagle 软件**。")
    print("关闭后，请按回车键继续...")
    print("="*50)
    input(">> 确认 Eagle 已关闭后，按回车继续...")

    # --- 阶段 3: 扫描磁盘并移动文件 ---
    images_root = os.path.join(EAGLE_LIBRARY_PATH, "images")
    if not os.path.exists(images_root):
        print(f"❌ 错误：找不到 images 目录 -> {images_root}")
        return

    success_count = 0
    fail_count = 0
    
    print(f"\n🚀 开始扫描并移动文件...")
    
    # 遍历 .info 文件夹
    for entry in os.scandir(images_root):
        if entry.is_dir() and entry.name.endswith(".info"):
            folder_path = entry.path
            metadata_path = os.path.join(folder_path, "metadata.json")
            
            if not os.path.exists(metadata_path):
                continue
                
            try:
                # 读取 metadata.json 获取 ID 关联
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                original_name = meta.get('name', 'Unnamed')
                ext = meta.get('ext', '')
                folder_ids = meta.get('folders', [])
                
                # 确定目标文件夹路径
                target_sub_dir = "_Uncategorized" # 默认未分类
                if folder_ids:
                    # 优先取第一个分类 ID
                    fid = folder_ids[0]
                    if fid in folder_mapping:
                        target_sub_dir = folder_mapping[fid]
                
                # 在文件夹内寻找真实文件
                source_file = None
                
                # 扫描当前 .info 目录下的文件
                candidates = []
                for f_name in os.listdir(folder_path):
                    if f_name == "metadata.json": continue
                    if f_name.endswith("_thumbnail.png"): continue
                    
                    # 排除一些系统文件
                    if f_name in [".DS_Store", "desktop.ini"]: continue

                    f_full_path = os.path.join(folder_path, f_name)
                    if os.path.isfile(f_full_path):
                        candidates.append(f_name)
                
                # 尝试匹配后缀
                for cand in candidates:
                    if cand.lower().endswith(f".{ext}".lower()):
                        source_file = os.path.join(folder_path, cand)
                        break
                
                # 如果没匹配到但只有一个文件，那就是它
                if not source_file and len(candidates) == 1:
                    source_file = os.path.join(folder_path, candidates[0])
                    # 修正后缀
                    _, real_ext = os.path.splitext(candidates[0])
                    ext = real_ext.replace(".", "")

                if source_file:
                    # 构造目标全路径
                    dest_dir = os.path.join(TARGET_EXPORT_PATH, target_sub_dir)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                    
                    # 处理文件名非法字符
                    safe_filename = "".join([c for c in original_name if c not in r'\/:*?"<>|'])
                    # 确保后缀存在
                    if not safe_filename.lower().endswith(f".{ext}".lower()):
                        safe_filename = f"{safe_filename}.{ext}"
                        
                    final_path = get_unique_path(dest_dir, safe_filename)
                    
                    # === 物理移动 (剪切) ===
                    shutil.move(source_file, final_path)
                    print(f"📦 [Moved] {safe_filename} -> {target_sub_dir}")
                    success_count += 1
                
            except Exception as e:
                print(f"⚠️ 跳过 {entry.name}: {e}")
                fail_count += 1

    print("\n" + "="*50)
    print(f"🎉 任务完成！")
    print(f"✅ 成功移动: {success_count} 个文件")
    print(f"❌ 失败/跳过: {fail_count} 个文件")
    print(f"📂 文件位置: {TARGET_EXPORT_PATH}")
    print("="*50)

if __name__ == "__main__":
    main()