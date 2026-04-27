# Terraform ELK 모듈화 (modules/elk 분리)

## 배경

기존 `elk.tf` 단일 파일로 관리하던 ELK Stack을 모듈 구조로 분리

## 변경 전 구조

```
terraform-soc/
├── main.tf
└── elk.tf
```

## 변경 후 구조

```
terraform-soc/
├── main.tf
└── modules/
    └── elk/
        ├── main.tf       ← ELK 리소스
        ├── variables.tf  ← 포트 변수
        └── outputs.tf    ← 컨테이너 이름 출력
```

## 핵심 코드

### modules/elk/variables.tf

```hcl
variable "es_port" {
  default = 9202
}

variable "kibana_port" {
  default = 5602
}
```

### modules/elk/main.tf

```hcl
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

resource "docker_container" "elasticsearch" {
  ports {
    internal = 9200
    external = var.es_port
  }
}

resource "docker_container" "kibana" {
  ports {
    internal = 5601
    external = var.kibana_port
  }
  depends_on = [docker_container.elasticsearch]
}
```

### 루트 main.tf

```hcl
module "elk" {
  source      = "./modules/elk"
  es_port     = 9202
  kibana_port = 5602
}
```

## 적용 결과

```
Apply complete! Resources: 4 added, 0 changed, 4 destroyed.
module.elk.docker_container.elasticsearch
module.elk.docker_container.kibana
```

## 배운 것

- 모듈 내부에도 `required_providers` 선언 필요 → 없으면 `hashicorp/docker` 탐색 에러 발생
- 하드코딩 포트 → `var.es_port` 변수화로 재사용 가능
- 모듈화 후 리소스 주소 변경: `docker_container.elasticsearch` → `module.elk.docker_container.elasticsearch`
- `4 to destroy` 는 루트 리소스 제거 + 모듈 하위 재생성이므로 정상
