from django.conf import settings
import os
import json
from openai import OpenAI
from sentence_transformers import SentenceTransformer

# 전역 클라이언트 사용 (settings의 키 사용)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Django 실행 환경이 아닐 때도 .env를 로드하기 위한 처리 (테스트용)
if not settings.configured:
    import dotenv
    dotenv.load_dotenv()

_local_embedding_model = None

def get_local_model():
    """
    싱글톤 패턴: 모델이 메모리에 없으면 로드하고, 있으면 반환합니다.
    """
    global _local_embedding_model
    if _local_embedding_model is None:
        print("🏗️ PyTorch 로컬 모델 로딩 중... (최초 1회만 실행)")
        # 이미 받아둔 캐시가 있다면 빠르게 로드됩니다.
        _local_embedding_model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
        print("✅ 모델 로딩 완료!")
    return _local_embedding_model

def classify_news(text, region='KR'):
    """
    [Upgrade] 뉴스 본문을 읽고
    1. 주제 카테고리 (Category: Politics, Tech...)
    2. 기사 성격 (Type: FACT, INSIGHT, OPINION...)
    
    두 가지를 동시에 분류하여 JSON으로 반환합니다.
    """
    try:
        short_text = text[:1500] # 분석 정확도를 위해 텍스트 길이 약간 늘림

        if region == 'AU':
            # [AU] 호주 모드 (영어)
            categories = [
                "Politics/Election", "Policy/Admin", 
                "Economy/Finance", "Real Estate", "Stock/Investment", "Business",
                "Society/Crime", "Law/Rights", "Education",
                "International/Diplomacy",
                "Health/Life", "Travel/Leisure", "Food/Dining",
                "IT/Tech", "AI/Robot", "Mobile/Telecom", "Gaming", "Science/Space",
                "Sports", "Football", "Baseball", "Golf",
                "Entertainment", "Movie/Music", "Culture/Art"
            ]
            types = ["FACT", "INSIGHT", "OPINION", "TUTORIAL"]
            
            system_instruction = (
                f"You are a news classification expert. Analyze the article below and return a JSON object.\n"
                f"1. category: Choose ONE from [{', '.join(categories)}].\n"
                f"2. type: Choose ONE from [{', '.join(types)}].\n"
                f"   - FACT: Simple news report, breaking news.\n"
                f"   - INSIGHT: In-depth analysis, future trends, why it happened.\n"
                f"   - OPINION: Editorials, personal views, columns.\n"
                f"   - TUTORIAL: How-to guides, tips.\n"
                f"Output Format: JSON only. Example: {{\"category\": \"IT/Tech\", \"type\": \"FACT\"}}"
            )
        else:
            # [KR] 한국 모드 (한글)
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
            types = ["FACT", "INSIGHT", "OPINION", "TUTORIAL"]

            system_instruction = (
                f"당신은 뉴스 분류 전문가입니다. 기사를 분석하여 JSON 객체를 반환하세요.\n"
                f"1. category: 다음 목록 중 하나 선택 [{', '.join(categories)}].\n"
                f"2. type: 다음 목록 중 하나 선택 [{', '.join(types)}].\n"
                f"   - FACT: 단순 사실 보도, 속보.\n"
                f"   - INSIGHT: 심층 분석, 원인 및 전망, 해설.\n"
                f"   - OPINION: 사설, 칼럼, 주관적 견해.\n"
                f"   - TUTORIAL: 가이드, 팁, 방법론.\n"
                f"출력 형식: 오직 JSON만. 예시: {{\"category\": \"IT/테크\", \"type\": \"FACT\"}}"
            )

        # JSON 응답을 강제하기 위해 response_format 사용 (GPT-4o/3.5-turbo 지원)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": short_text}
            ],
            temperature=0.1,
            response_format={"type": "json_object"} # ★ JSON 강제 모드
        )
        
        # 결과 파싱
        result_json = json.loads(completion.choices[0].message.content)
        
        # 안전장치 (Key가 없을 경우 대비)
        category = result_json.get("category", "General" if region == 'AU' else "일반")
        article_type = result_json.get("type", "FACT")

        return {"category": category, "type": article_type}

    except Exception as e:
        print(f"카테고리/타입 분류 실패: {e}")
        # 실패 시 기본값 반환
        return {
            "category": "General" if region == 'AU' else "일반",
            "type": "FACT"
        }

def summarize_stream(text, region='KR'):
    """
    뉴스 본문을 받아 OpenAI로 3줄 요약하고, 결과를 실시간으로 스트리밍합니다.
    region에 따라 언어와 어조를 변경합니다.
    """
    # 전역 client 사용 권장 (함수 내 재선언 불필요)
    
    # [프롬프트 분기]
    if region == 'AU':
        # 🇦🇺 호주 모드 (영어)
        system_prompt = (
            "You are a professional news assistant. "
            "Summarize the article into **exactly 3 bullet points**. "
            "Requirements:\n"
            "1. Quantity: Exactly 3 bullet points.\n"
            "2. Language: English only.\n"
            "3. Length: Keep it very short (under 30 words per point).\n" # ★ 길이 제한 추가
            "4. Style: Use a dry 'Headline style'. Remove unnecessary adjectives and adverbs.\n" # ★ 스타일 지정
            "5. Format: Plain text, separate each point with a newline."
        )
    else:
        # 🇰🇷 한국 모드 (한국어)
        system_prompt = (
            "당신은 뉴스 요약 전문가입니다. "
            "다음 뉴스 기사를 읽고 핵심 내용을 3줄로 요약해주세요. "
            "말투는 '~함'체로 간결하게 작성하고, 각 줄은 줄바꿈으로 구분하세요."
        )

    try:
        # OpenAI API 호출 (스트리밍 모드)
        stream = client.chat.completions.create(
            model="gpt-4o-mini", 
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
        error_msg = f"Error generating summary: {str(e)}" if region == 'AU' else f"AI 요약 중 오류가 발생했습니다: {str(e)}"
        yield error_msg


def get_embedding(text, use_openai=True, use_pytorch=True):
    """
    [핵심 변경]
    텍스트를 받아 PyTorch(로컬)와 OpenAI(API) 임베딩을 동시에 생성합니다.
    나중에 성능 비교를 위해 두 가지 버전을 모두 반환합니다.
    
    Returns:
        dict: {'pytorch': [...], 'openai': [...]}
    """
    result = {
        'pytorch': None,
        'openai': None
    }
    
    try:
        if not text: return result
        clean_text = text.replace("\n", " ")

        # 1. PyTorch 임베딩 (Local - 768차원)
        if use_pytorch:
            try:
                model = get_local_model() # 싱글톤 모델 호출
                # tolist()를 해야 DB(pgvector)에 JSON 호환 리스트로 들어갑니다.
                vector_pt = model.encode(clean_text).tolist()
                result['pytorch'] = vector_pt
            except Exception as e:
                print(f"⚠️ PyTorch 임베딩 실패: {e}")

        # 2. OpenAI 임베딩 (API - 1536차원) - 비교 및 백업용
        if use_openai:
            try:
                response = client.embeddings.create(
                    input=[clean_text],
                    model="text-embedding-3-small"
                )
                # 주의: response.data[0].embedding_openai가 아니라 .embedding 입니다.
                vector_oa = response.data[0].embedding
                result['openai'] = vector_oa
            except Exception as e:
                print(f"⚠️ OpenAI 임베딩 실패: {e}")

        return result
    
    except Exception as e:
        print(f"임베딩 생성 전체 실패: {e}")
        return result
    
def get_completion(prompt, system_role=None, temperature=0.7):
    """
    프롬프트를 받아 GPT-4o-mini의 답변을 반환합니다. (RAG 및 일반 대화용)
    system_role을 인자로 받으므로, 호출하는 쪽(rag_views)에서 region에 맞게 메시지를 넣어주면 됩니다.
    """
    # 기본값 설정 (호출 시 None이면 한국어로 설정)
    if system_role is None:
        system_role = "당신은 유능한 지식 비서입니다."

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature, 
        )
        
        return completion.choices[0].message.content.strip()

    except Exception as e:
        print(f"GPT 응답 생성 실패: {e}")
        return "답변을 생성하지 못했습니다."