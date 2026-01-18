from django.db import migrations, models
import pgvector.django
from pgvector.django import VectorExtension # <--- 반드시 추가

class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        VectorExtension(), # <--- 1순위: DB에 벡터 기능을 활성화합니다.
        migrations.CreateModel(
            name='Article',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='기사 제목', max_length=500)),
                ('url', models.URLField(db_index=True, help_text='기사 원본 링크 (중복 방지)', unique=True)),
                ('content', models.TextField(blank=True, help_text='기사 본문 (RAG 검색용)', null=True)),
                ('summary', models.TextField(blank=True, help_text='AI 3줄 요약', null=True)),
                ('category', models.CharField(blank=True, help_text='AI가 분류한 카테고리 (IT, 경제 등)', max_length=50, null=True)),
                ('embedding', pgvector.django.VectorField(blank=True, dimensions=1536, help_text='임베딩 벡터 데이터', null=True)),
                ('thumbnail_url', models.URLField(blank=True, null=True)),
                ('status', models.CharField(choices=[('PENDING', '요약 생성 중'), ('SAVED', '저장 완료'), ('ARCHIVED', '나중에 읽기')], default='PENDING', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='최초 생성일 (잔디 심기 기준)')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['url'], name='news_articl_url_957495_idx'), 
                    models.Index(fields=['created_at'], name='news_articl_created_4ed0e6_idx')
                ],
            },
        ),
    ]