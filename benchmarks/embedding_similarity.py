"""한국어 문장쌍으로 임베딩 모델의 변별력을 측정한다.

좋은 임베딩의 조건은 "유사도가 높다"가 아니라 **무관한 쌍과 관련 있는 쌍 사이의
간격이 벌어진다**는 것이다. 무관쌍의 유사도가 0.98 이면 어떤 임계값을 잡아도
필터링이 되지 않는다.

사용법:
    pip install -r requirements.txt
    export GOOGLE_CLOUD_PROJECT=your-project-id
    python embedding_similarity.py

    # 특정 모델만
    python embedding_similarity.py --models text-multilingual-embedding-002

주의: `GOOGLE_CLOUD_LOCATION` 은 `global` 로 둔다. 리전 엔드포인트에서 일부 모델이
404 로 떨어지는 경우가 있다.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

from google import genai
from google.genai import types

DEFAULT_MODELS = [
    "text-embedding-004",
    "text-multilingual-embedding-002",
    "gemini-embedding-001",
]

#: (분류, 문장 A, 문장 B)
#:
#: UNRELATED   — 주제가 완전히 다르다. 유사도가 **낮아야** 정상이다.
#: SAME_DOMAIN — 같은 분야이되 내용이 다르다. 무관쌍보다 높되 1.0 과는 떨어져야 한다.
PAIRS: list[tuple[str, str, str]] = [
    (
        "UNRELATED",
        "강아지가 공원에서 뛰어놀고 있다",
        "양자역학의 파동함수는 확률진폭을 나타낸다",
    ),
    (
        "UNRELATED",
        "오늘 점심으로 김치찌개를 먹었다",
        "분산 시스템에서 합의 알고리즘은 노드 간 상태를 일치시킨다",
    ),
    (
        "UNRELATED",
        "지하철 2호선은 순환선이다",
        "비타민 D는 칼슘 흡수를 돕는다",
    ),
    (
        "SAME_DOMAIN",
        "비타민 D는 칼슘 흡수를 돕는다",
        "마그네슘은 근육 이완에 관여하는 무기질이다",
    ),
    (
        "SAME_DOMAIN",
        "유산소 운동은 심폐 지구력을 향상시킨다",
        "근력 운동은 기초대사량을 높이는 데 도움이 된다",
    ),
    (
        "SAME_DOMAIN",
        "식이섬유는 장 운동을 촉진한다",
        "발효식품은 장내 미생물 균형에 기여한다",
    ),
]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def embed(client: genai.Client, model: str, text: str) -> list[float]:
    """한 번에 한 문장만 보낸다 — 모델마다 배치 상한이 달라 비교 조건을 맞추기 위해서다.

    `output_dimensionality` 는 지정하지 않는다. 차원을 강제로 맞추면 잘라내기가 개입해
    모델의 네이티브 성능이 아니라 축소 후 성능을 재게 된다.
    """
    response = client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    embeddings = response.embeddings or []
    if not embeddings:
        raise RuntimeError(f"{model}: 임베딩이 비어 있다")
    return list(embeddings[0].values or [])


def run(client: genai.Client, model: str) -> dict[str, object]:
    cache: dict[str, list[float]] = {}

    def vec(text: str) -> list[float]:
        if text not in cache:
            cache[text] = embed(client, model, text)
        return cache[text]

    scores: dict[str, list[float]] = {"UNRELATED": [], "SAME_DOMAIN": []}
    dimensions = 0

    for kind, left, right in PAIRS:
        a, b = vec(left), vec(right)
        dimensions = len(a)
        scores[kind].append(cosine(a, b))

    unrelated = sum(scores["UNRELATED"]) / len(scores["UNRELATED"])
    same_domain = sum(scores["SAME_DOMAIN"]) / len(scores["SAME_DOMAIN"])

    return {
        "model": model,
        "dimensions": dimensions,
        "unrelated": unrelated,
        "same_domain": same_domain,
        "margin": same_domain - unrelated,
        "detail": scores,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument(
        "--location", default=os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    )
    parser.add_argument("--verbose", action="store_true", help="쌍별 유사도를 모두 출력")
    args = parser.parse_args()

    if not args.project:
        print(
            "GOOGLE_CLOUD_PROJECT 가 필요하다 (환경변수 또는 --project)", file=sys.stderr
        )
        return 2

    client = genai.Client(vertexai=True, project=args.project, location=args.location)

    results = []
    for model in args.models:
        try:
            results.append(run(client, model))
        except Exception as exc:  # 한 모델이 죽어도 나머지는 계속 잰다
            print(f"  ! {model}: {exc}", file=sys.stderr)

    if not results:
        return 1

    header = f"{'모델':<38} {'차원':>6} {'무관쌍':>9} {'도메인쌍':>10} {'마진':>9}"
    print()
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['model']:<38} {r['dimensions']:>6} "
            f"{r['unrelated']:>9.4f} {r['same_domain']:>10.4f} {r['margin']:>9.4f}"
        )
    print()
    print("무관쌍은 낮을수록, 마진은 클수록 좋다.")
    print("무관쌍이 1.0 에 가까우면 그 모델은 해당 언어를 구분하지 못하고 있다.")

    if args.verbose:
        for r in results:
            print(f"\n[{r['model']}]")
            for kind, values in r["detail"].items():
                pairs_of_kind = [p for p in PAIRS if p[0] == kind]
                for (_, left, right), score in zip(pairs_of_kind, values):
                    print(f"  {kind:<12} {score:.4f}  {left[:20]} ↔ {right[:20]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
