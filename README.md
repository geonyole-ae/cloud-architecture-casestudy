# Cloud Architecture Case Study

디지털 헬스케어 플랫폼의 AWS 인프라를 설계·구축하고 RAG 파이프라인을 개발하면서 내린
기술적 판단과 그 근거를 정리한 케이스 스터디입니다.

> **이 저장소에 대하여**
> 재직 중 담당한 업무 가운데 **회사 고유 정보를 제외한 기술적 판단 과정만** 재구성했습니다.
> 회사의 소스 코드·데이터·서비스 식별 정보는 포함되어 있지 않으며, 문서에 등장하는 도메인과
> 리소스 이름은 모두 예시로 치환했습니다. 공개된 AWS 요금과 공개 모델의 측정값만 다룹니다.

---

## 목차

| 문서 | 내용 |
|---|---|
| [01. 아키텍처](docs/01-architecture.md) | 단일 EC2 박스에서 ECS 기반 구성으로 가는 경로, VPC·Security Group 설계 |
| [02. 비용 설계](docs/02-cost.md) | Fargate 완전관리형 / EC2 절감형 / MVP 최소비용 3개 안의 서울 리전 비용 비교 |
| [03. TLS와 CI/CD](docs/03-tls-cicd.md) | Let's Encrypt 자동 갱신, GitHub Actions → ECR → ECS 파이프라인, 자격증명 관리 |
| [04. 임베딩 모델 선정](docs/04-embedding.md) | 한국어 RAG에서 임베딩 모델을 실측으로 교체한 과정 |
| [benchmarks/](benchmarks/) | 04번 문서의 측정을 재현할 수 있는 스크립트 |

---

## 하이라이트

### 임베딩 모델을 이름이 아니라 측정으로 골랐다

RAG 챗봇에 처음 적용한 `text-embedding-004`가 **한국어에서 무관한 문장쌍의 코사인 유사도
0.988**을 기록했습니다. 아무 관련 없는 두 문장이 0.988이면 어떤 질의를 넣어도 순위가 뒤집히지
않습니다. 실제로 특정 문서 하나가 모든 질의에서 1위를 차지하는 현상이 나타났습니다.

원인을 영어 최적화 모델의 한국어 변별력 부재로 특정하고 3개 모델을 직접 측정한 뒤,
분리도와 스키마 정합성과 단가를 함께 고려해 `text-multilingual-embedding-002`로 교체했습니다.

| 모델 | 무관쌍 | 같은 도메인쌍 | 네이티브 차원 | 상대 단가 |
|---|---|---|---|---|
| `text-embedding-004` | **0.9880** | 0.9937 | 768 | 1x |
| `text-multilingual-embedding-002` | **0.4904** | 0.5718 | 768 | 1x |
| `gemini-embedding-001` | **0.1861** | 0.2141 | 3072 | 6x |

분리도만 보면 `gemini-embedding-001`이 가장 좋지만, 네이티브 3072차원이라 `vector(768)`
스키마에 맞추려면 잘라내야 하고 단가가 6배입니다. 채택하지 않은 이유까지가 판단입니다.

→ [자세한 과정](docs/04-embedding.md) · [재현 스크립트](benchmarks/)

### 비용의 25%가 NAT Gateway였다

완전관리형 구성의 월 비용을 항목별로 산정하니 NAT Gateway가 $45로 전체 $179의 25%를
차지했습니다. 애플리케이션을 한 줄도 고치지 않고 S3·ECR에 VPC Endpoint를 붙이는 것만으로
줄일 수 있는 비용이었습니다.

→ [3개 안 비교](docs/02-cost.md)

### 인증서 자동 갱신이 조용히 실패하는 지점

HTTP 요청을 전부 HTTPS로 넘기는 리다이렉트가 ACME 챌린지 경로까지 함께 넘겨버리면,
인증서 갱신이 **에러 없이** 실패하고 90일 뒤 서비스가 죽습니다. Nginx `location` 우선순위로
챌린지 경로를 리다이렉트보다 앞세워 막았습니다.

→ [TLS 운영](docs/03-tls-cicd.md)

---

## 사용 기술

**인프라** AWS (EC2, ECS, ECR, S3, IAM, CloudWatch) · Docker · Nginx · GitHub Actions · Let's Encrypt
**백엔드** Python 3.13 · FastAPI · PostgreSQL 16 (pgvector) · Redis · Celery
**AI** Vertex AI (Gemini) · GraphRAG + Vector RAG 하이브리드 검색
