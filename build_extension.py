import os
import shutil
import sys

# 1. 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'extension_src')
BUILD_DIR = os.path.join(BASE_DIR, 'extension_build')

def build(env):
    target_dir = os.path.join(BUILD_DIR, env)
    
    # 2. 기존 빌드 폴더 삭제 (Clean Build)
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir)

    print(f"🔨 [{env.upper()}] 빌드를 시작합니다...")

    # 3. 소스 파일 전체 복사
    try:
        shutil.copytree(
            SRC_DIR, 
            target_dir, 
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                'manifest_*.json', 
                'config_*.js',  # .js 파일 무시 확인
                '__pycache__', 
                '.DS_Store'
            )
        )
    except Exception as e:
        print(f"❌ 소스 복사 중 오류 발생: {e}")
        return

    # 4. 환경에 맞는 설정 파일 복사
    try:
        # (1) Manifest 처리 (.json -> .json)
        src_manifest = os.path.join(SRC_DIR, f'manifest_{env}.json')
        dst_manifest = os.path.join(target_dir, 'manifest.json')
        
        if os.path.exists(src_manifest):
            shutil.copy(src_manifest, dst_manifest)
            print(f"   ✅ Manifest 적용: manifest_{env}.json -> manifest.json")
        else:
            print(f"   ❌ 오류: {src_manifest} 파일이 없습니다!")
            return

        # (2) Config 처리 (.js -> .js) ★ 여기가 수정되었습니다!
        src_config = os.path.join(SRC_DIR, f'config_{env}.js') # .json이 아니라 .js 입니다
        dst_config = os.path.join(target_dir, 'config.js')
        
        if os.path.exists(src_config):
            shutil.copy(src_config, dst_config)
            print(f"   ✅ Config 적용: config_{env}.js -> config.js")
        else:
            print(f"   ❌ 오류: {src_config} 파일이 없습니다!")
            return
            
        print("-" * 40)
        print(f"🎉 빌드 성공! 크롬에서 아래 폴더를 로드하세요:")
        print(f"📂 {target_dir}")
        print("-" * 40)

    except Exception as e:
        print(f"❌ 설정 파일 처리 중 오류 발생: {e}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    if mode not in ['dev', 'prod']:
        print("사용법: python build_extension.py [dev|prod]")
    else:
        build(mode)