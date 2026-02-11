import spacy
import logging

logger = logging.getLogger(__name__)

# =========================================================
# [메모리 최적화] 전역 로드 & 파이프라인 다이어트
# =========================================================
try:
    # [수정 1] 한국어는 형태소 분석(tagger)이 생명이므로 disable에서 제거!
    nlp_ko = spacy.load(
        "ko_core_news_sm", 
        disable=["parser", "attribute_ruler", "lemmatizer"]
    )
    
    # 영어는 tagger를 꺼도 잘 작동하므로 유지
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
    """
    if not text: 
        return {}
    
    nlp = nlp_en if region == 'AU' else nlp_ko
    if not nlp:
        return {}

    # 앞 3000자만 잘라서 OOM 방지
    doc = nlp(text[:3000])

    entities = {}
    
    # [수정 2] 언어별 NER 라벨 매핑 딕셔너리
    # 한국어 모델은 PS, OG, LC를 뱉어내므로, 이를 영어와 동일하게 맞춰줍니다.
    if region == 'KR':
        target_labels = ['PS', 'OG', 'LC'] 
        label_map = {'PS': 'PERSON', 'OG': 'ORG', 'LC': 'GPE'}
    else:
        target_labels = ['PERSON', 'ORG', 'GPE']
        label_map = {'PERSON': 'PERSON', 'ORG': 'ORG', 'GPE': 'GPE'}

    for ent in doc.ents:
        if ent.label_ in target_labels:
            # 형태소 분석기 특성상 붙어 나오는 불필요한 공백 제거
            clean_text = ent.text.strip()
            
            # [노이즈 제거 필터]
            if (len(clean_text) > 1 and 
                clean_text.replace(' ', '').isalnum() and 
                not clean_text.isdigit()):
                
                # DB 및 프론트엔드 호환을 위해 표준 라벨명(PERSON, ORG 등)으로 변환
                std_label = label_map[ent.label_]
                
                if std_label not in entities:
                    entities[std_label] = []
                
                if clean_text not in entities[std_label]:
                    entities[std_label].append(clean_text)
    
    return entities