import spacy
import logging

logger = logging.getLogger(__name__)

# =========================================================
# [메모리 최적화] 전역 로드 & 파이프라인 다이어트
# parser, tagger 등을 끄면 메모리 사용량이 절반 이하로 줍니다.
# =========================================================
try:
    # 한국어 모델 로드
    nlp_ko = spacy.load(
        "ko_core_news_sm", 
        disable=["parser", "tagger", "attribute_ruler", "lemmatizer"]
    )
    
    # 영어 모델 로드
    nlp_en = spacy.load(
        "en_core_web_sm", 
        disable=["parser", "tagger", "attribute_ruler", "lemmatizer"]
    )
    logger.info("✅ spaCy models loaded (Lightweight mode).")

except Exception as e:
    logger.error(f"❌ Failed to load spaCy models: {e}")
    nlp_ko = None
    nlp_en = None


def extract_entities(text, region='KR'):
    """
    텍스트에서 주요 키워드(인물, 조직, 장소)를 추출하여 딕셔너리로 반환.
    User Tower와 DB 간의 연결고리(Bridge) 역할을 함.
    """
    # 1. 예외 처리
    if not text: 
        return {}
    
    # 모델 선택
    nlp = nlp_en if region == 'AU' else nlp_ko
    if not nlp:
        return {}

    # 2. [안전장치] 텍스트 길이 제한
    # 2GB 서버에서 너무 긴 텍스트(논문 등)를 처리하면 OOM 발생 가능
    # 뉴스 기사는 앞부분 3000자에 핵심 내용이 다 있으므로 자름.
    doc = nlp(text[:3000])

    entities = {}
    
    # 우리가 연결고리로 쓸 핵심 라벨만 추출
    # PERSON: 사람 (민희진, 일론 머스크)
    # ORG: 조직/기업 (하이브, 테슬라, OpenAI)
    # GPE: 국가/도시 (한국, 미국, 시드니) - *필요 없으면 제거 가능*
    target_labels = ['PERSON', 'ORG', 'GPE'] 

    for ent in doc.ents:
        if ent.label_ in target_labels:
            clean_text = ent.text.strip()
            
            # [노이즈 제거 필터]
            # 1. 1글자짜리 제외 (예: '나', '그', '저')
            # 2. 특수문자가 포함되지 않은 순수 텍스트만
            # 3. 숫자로만 된 것 제외
            if (len(clean_text) > 1 and 
                clean_text.replace(' ', '').isalnum() and 
                not clean_text.isdigit()):
                
                # 딕셔너리 초기화
                if ent.label_ not in entities:
                    entities[ent.label_] = []
                
                # 중복 저장 방지
                if clean_text not in entities[ent.label_]:
                    entities[ent.label_].append(clean_text)
    
    return entities