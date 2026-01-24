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
    뉴스 본문을 읽고 세분화된 카테고리로 분류합니다.
    """
    try:
        short_text = text[:1000] # 앞부분만 읽어도 분류 충분

        # 카테고리 리스트 확장 (스포츠, 부동산, 주식, AI 등 구체화)
        categories = [
            "정치/선거", "행정/정책", 
            "경제/금융", "부동산", "주식/투자", "기업/비즈니스",
            "사회/사건사고", "법률/인권", "교육/학교",
            "국제/외교", "북한",
            "생활/건강", "여행/레저", "음식/맛집",
            "IT/테크", "AI/로봇", "모바일/통신", "게임", "과학/우주",
            "스포츠", "축구", "야구", "골프",
            "연예/방송", "영화/음악", "문화/예술"
        ]
        
        categories_str = ", ".join(categories)

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"당신은 뉴스 분류 전문가입니다. 다음 뉴스 기사를 읽고 아래 카테고리 목록 중 "
                        f"내용과 가장 연관성이 높은 **단 하나**를 선택해 반환하세요.\n"
                        f"목록: [{categories_str}]\n"
                        f"주의: '기타'라는 말은 쓰지 마세요. 무조건 위 목록 중 하나를 골라야 합니다."
                        f"오직 카테고리 명사만 출력하세요."
                    )
                },
                {"role": "user", "content": short_text}
            ],
            temperature=0.1, # 창의성 억제 (정확한 분류)
        )
        
        category = completion.choices[0].message.content.strip()
        
        # 혹시라도 AI가 이상한 말을 붙이면 정제
        if category not in categories:
            # 리스트에 없으면 그냥 냅두거나, 가장 유사한걸 찾게 할 수도 있음.
            # 일단은 그대로 저장 (AI가 새로운 카테고리를 만들 수도 있으므로 유연하게)
            pass
            
        return category

    except Exception as e:
        print(f"카테고리 분류 실패: {e}")
        return "일반"


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
    
def get_completion(prompt, system_role="당신은 유능한 지식 비서입니다."):
    """
    프롬프트를 받아 GPT-4o-mini의 답변을 반환합니다. (RAG 및 일반 대화용)
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7, # 약간의 창의성을 허용 (문구 생성 등)
        )
        
        return completion.choices[0].message.content.strip()

    except Exception as e:
        print(f"GPT 응답 생성 실패: {e}")
        return "답변을 생성하지 못했습니다."