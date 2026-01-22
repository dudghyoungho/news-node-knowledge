from django.conf import settings
import os
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Django 실행 환경이 아닐 때도 .env를 로드하기 위한 처리 (테스트용)
if not settings.configured:
    import dotenv
    dotenv.load_dotenv()


def classify_news(text):
    """
    뉴스 본문을 읽고 [정치, 경제, 사회, 생활/문화, 세계, IT/과학, 스포츠, 연예] 중 하나로 분류합니다.
    """
    try:
        # 텍스트가 너무 길면 앞부분 1500자만 읽어도 분류 가능 (토큰 절약)
        short_text = text[:1500]

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 뉴스 분류기입니다. 주어진 뉴스 기사를 읽고 다음 카테고리 중 가장 적절한 하나를 선택해 단어만 반환하세요.\n"
                        "카테고리 목록: [정치, 경제, 사회, 생활/문화, 세계, IT/과학, 스포츠, 연예]\n"
                        "부가적인 설명 없이 오직 카테고리 명사만 출력하세요."
                    )
                },
                {"role": "user", "content": short_text}
            ],
            temperature=0.3, # 창의성 낮춤 (정확한 분류 위해)
        )
        
        category = completion.choices[0].message.content.strip()
        return category

    except Exception as e:
        print(f"카테고리 분류 실패: {e}")
        return "기타"


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


def get_embedding(text):
    """
    텍스트를 벡터 리스트로 반환한다. 모델 : text-embedding-3-small
    """
    try:
        text = text.replace("\n"," ")
        response = client.embeddings.create(
            input=[text],
            model = "text-embedding-3-small"
        )

        vector = response.data[0].embedding
        return vector
    
    except Exception as e:
        print(f"임베딩 생성 실패 : {e}")
        return None