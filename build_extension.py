import os
import shutil
import sys
import json

# ==============================================================================
# 1. 환경 설정 (CONFIGURATION)
# ==============================================================================

# 빌드 모드별 OAuth Client ID 설정
OAUTH_CLIENT_IDS = {
    "dev": "307150378715-6k7401oof17j9gvg9dd83cvduv7n79s4.apps.googleusercontent.com",
    "prod": "307150378715-msus9lvuupid4a7et5avbhlabbml3l4s.apps.googleusercontent.com", # Server Test용
    "store": "307150378715-ll2i127glnolsup1ds1tspbdp20qbb8f.apps.googleusercontent.com" # Web Store 배포용
}

# 소스 및 빌드 디렉토리 설정
SRC_DIR = "extension_src"
BUILD_ROOT = "extension_build"

# 복사할 파일 목록 (manifest.json은 로직에서 따로 처리하므로 리스트에 있어도 덮어씌워짐)
FILES_TO_COPY = [
    "popup.html",
    "popup.js",
    "content_script.js",
    "background.js",
    "config.js",
    "icons",
    "styles.css",
    "icon16.png",
    "icon48.png",
    "icon128.png"
]

# ==============================================================================
# 2. 빌드 로직 (BUILD LOGIC)
# ==============================================================================

def build(mode):
    if mode not in OAUTH_CLIENT_IDS:
        print(f"❌ Error: Invalid mode '{mode}'. Use 'dev', 'prod', or 'store'.")
        sys.exit(1)

    print(f"🚀 Building extension for [{mode.upper()}] environment...")
    
    # 1. 빌드 폴더 준비 (기존 폴더 삭제 후 재생성)
    dest_dir = os.path.join(BUILD_ROOT, mode)
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    # 2. 일반 파일 복사
    for item in FILES_TO_COPY:
        src_path = os.path.join(SRC_DIR, item)
        dest_path = os.path.join(dest_dir, item)
        
        if not os.path.exists(src_path):
            print(f"⚠️ Warning: Source file not found: {src_path}")
            continue

        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path)
        else:
            shutil.copy2(src_path, dest_path)

    # 3. [핵심] config.js 수정 (환경 변수 주입)
    config_src = os.path.join(SRC_DIR, "config.js")
    config_dest = os.path.join(dest_dir, "config.js")
    
    # prod나 store나 서버 주소는 실제 서버(Lightsail)를 바라봐야 함
    config_env = 'production' if mode in ['prod', 'store'] else 'development'
    
    with open(config_src, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # JS 파일 내부의 ENV 값을 문자열 치환
    # 예: ENV: 'development' -> ENV: 'production'
    new_content = content.replace("ENV: 'development'", f"ENV: '{config_env}'")
    
    with open(config_dest, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ config.js configured for {config_env}")

    # 4. [핵심] manifest.json 수정 (OAuth Client ID 주입)
    # 개발용과 배포용 manifest가 따로 있다면 여기서 분기 가능하지만,
    # 보통 manifest.json 하나를 두고 ID만 바꿔치기 하는 것이 깔끔합니다.
    manifest_src = os.path.join(SRC_DIR, "manifest.json")
    
    # 만약 dev용 manifest를 따로 쓰고 있었다면 그걸 base로 사용
    if not os.path.exists(manifest_src) and os.path.exists(os.path.join(SRC_DIR, "manifest_dev.json")):
        manifest_src = os.path.join(SRC_DIR, "manifest_dev.json")

    manifest_dest = os.path.join(dest_dir, "manifest.json")

    with open(manifest_src, 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)

    # OAuth ID 교체 로직
    target_client_id = OAUTH_CLIENT_IDS[mode]
    
    if "oauth2" not in manifest_data:
        manifest_data["oauth2"] = {}
    
    manifest_data["oauth2"]["client_id"] = target_client_id
    
    # [중요] Store 배포용이 아니면 'key' 필드 유지 (개발 편의성)
    # Store 배포용일 때는 'key' 필드를 제거하는 것이 좋을 수도 있음 (Store가 자동으로 부여하므로)
    if mode == 'store' and 'key' in manifest_data:
        del manifest_data['key']
        print("ℹ️ Removed 'key' field for Store build.")

    with open(manifest_dest, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f"✅ manifest.json updated with Client ID: {target_client_id[:15]}...")
    print(f"✨ Build Complete! Output directory: {dest_dir}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_extension.py [dev|prod|store]")
        sys.exit(1)
    
    build(sys.argv[1])