# 임베딩 변별력 측정

[04. 임베딩 모델 선정](../docs/04-embedding.md)의 측정을 재현하는 스크립트입니다.

## 무엇을 재는가

한국어 문장쌍 두 종류의 코사인 유사도를 비교합니다.

- **무관쌍** — 주제가 완전히 다른 문장. 유사도가 낮아야 정상입니다.
- **같은 도메인쌍** — 같은 분야의 서로 다른 내용. 무관쌍보다는 높되 1.0과는 떨어져야 합니다.

핵심 지표는 유사도의 절대값이 아니라 **두 값의 간격(마진)** 입니다. 무관쌍이 0.98이면
어떤 임계값을 설정해도 검색 결과를 걸러낼 수 없습니다.

## 실행

```bash
pip install -r requirements.txt

export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=global
gcloud auth application-default login

python embedding_similarity.py
```

특정 모델만 재거나 쌍별 상세를 보려면:

```bash
python embedding_similarity.py --models text-multilingual-embedding-002 --verbose
```

## 출력 예시

```
모델                                       차원       무관쌍     도메인쌍        마진
------------------------------------------------------------------------------
text-embedding-004                        768     0.9880     0.9937    0.0057
text-multilingual-embedding-002           768     0.4904     0.5718    0.0814
gemini-embedding-001                     3072     0.1861     0.2141    0.0280
```

`text-embedding-004`의 마진 0.0057은 노이즈 수준입니다. 영어 최적화 모델이라 한국어
문장을 구분하지 못하며, 그 결과 어떤 질의를 넣어도 특정 문서가 상위에 고정됩니다.

## 측정 조건

- 모델별 **네이티브 차원**을 그대로 사용합니다. `output_dimensionality`로 차원을 맞추면
  잘라내기가 개입해 네이티브 성능이 아니라 축소 후 성능을 재게 됩니다.
- 문장을 한 번에 하나씩 보냅니다. 모델마다 배치 상한이 달라 조건을 맞추기 위해서입니다.
- `task_type`은 `RETRIEVAL_DOCUMENT`로 고정합니다.

## 주의

`GOOGLE_CLOUD_LOCATION`은 `global`로 둡니다. 리전 엔드포인트에서 일부 모델이 404로
떨어지는 경우가 있습니다.

문장쌍은 6개뿐이라 정밀한 벤치마크가 아닙니다. **"이 모델은 한국어를 구분하는가"라는
이분법적 질문에 답하기 위한 최소 측정**이며, 실제로 그 질문에 답하는 데는 충분했습니다.
모델 순위를 정밀하게 매기려면 도메인 문서와 실제 질의 로그로 검색 정확도를 측정해야
합니다.
