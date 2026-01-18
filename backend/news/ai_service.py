from openai import OpenAI
from django.conf import settings
import os

# Django 실행 환경이 아닐 때도 .env를 로드하기 위한 처리 (테스트용)
if not settings.configured:
    import dotenv
    dotenv.load_dotenv()

def summarize_stream(text):
    """
    뉴스 본문을 받아 OpenAI로 3줄 요약하고, 결과를 실시간으로 스트리밍합니다.
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # 프롬프트 설계: 명확한 지시가 중요합니다.
    system_prompt = (
        "당신은 뉴스 요약 전문가입니다. "
        "다음 뉴스 기사를 읽고 핵심 내용을 3줄로 요약해주세요. "
        "말투는 '~함'체로 간결하게 작성하고, 각 줄은 줄바꿈으로 구분하세요."
    )

    try:
        # OpenAI API 호출 (스트리밍 모드)
        stream = client.chat.completions.create(
            model="gpt-4o-mini",  # 가성비 최고 모델 (또는 gpt-3.5-turbo)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            stream=True,  # ★ 핵심: 한 번에 안 받고 줄줄이 받음
        )

        # 조각(chunk)이 들어올 때마다 즉시 반환 (Generator)
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    except Exception as e:
        yield f"AI 요약 중 오류가 발생했습니다: {str(e)}"

# ---- 테스트 코드 ----
if __name__ == "__main__":
    # 긴 텍스트 예시 (애국가 1~4절)
    dummy_text = """
    동해물과 백두산이 마르고 닳도록 하느님이 보우하사 우리나라 만세.
    남산 위에 저 소나무 철갑을 두른 듯 바람 서리 불변함은 우리 기상일세.
    가을 하늘 공활한데 높고 구름 없이 밝은 달은 우리 가슴 일편단심일세.
    이 기상과 이 맘으로 충성을 다하여 괴로우나 즐거우나 나라 사랑하세.
    """
    
    print("--- 스트리밍 요약 시작 ---")
    
    # 한 글자씩 받아오는지 눈으로 확인
    for token in summarize_stream(dummy_text):
        print(token, end="", flush=True) # 줄바꿈 없이 옆으로 계속 찍기
        
    print("\n\n--- 종료 ---")