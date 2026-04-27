# GitHub Actions Terraform CI 파이프라인

## 목적

`git push` 시 자동으로 `terraform validate` 실행되는 CI 파이프라인 구성

## 파일 위치

```
terraform-soc/
└── .github/
    └── workflows/
        └── terraform.yml
```

## terraform.yml

```yaml
name: Terraform CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  terraform:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init -backend=false

      - name: Terraform Validate
        run: terraform validate
```

## 트리거 조건

| 조건 | 동작 |
|------|------|
| `main` 브랜치에 push | 자동 실행 |
| `main` 브랜치로 PR | 자동 실행 |

## 실행 결과

```
✅ ci: GitHub Actions terraform validate 파이프라인 추가
Terraform CI #1 · 24s
```

## 트러블슈팅

| 에러 | 원인 | 해결 |
|------|------|------|
| `refusing to allow without workflow scope` | PAT에 workflow 권한 없음 | GitHub → Token → workflow 체크 추가 |

## 배운 것

- `.github/workflows/` 폴더에 yml 파일 추가하면 GitHub Actions 자동 인식
- `terraform init -backend=false` → 백엔드 설정 없이 초기화 가능
- `terraform validate` → 실제 배포 없이 코드 문법/구조 검증
- PAT 권한: 일반 push는 `repo`, workflow 파일 push는 `workflow` 추가 필요
- Actions 탭에서 실행 결과 및 로그 확인 가능
