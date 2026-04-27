# Terraform AWS 이식 구조 설계 (LocalStack 검증)

## 배경

실제 AWS 계정 없이 LocalStack을 활용해 VPC + Subnet + Security Group + EC2 구조를 Terraform으로 코드화하고 검증

## LocalStack이란

AWS를 로컬에서 에뮬레이션하는 툴. Terraform 입장에서 실제 AWS와 동일하게 동작하며 과금 없음

```
실제 AWS:   코드 → 인터넷 → AWS 서버 → 실제 EC2 생성 → 과금
LocalStack: 코드 → 내 컴퓨터 → LocalStack → 가짜 EC2 생성 → 과금 없음
```

## LocalStack 실행

```bash
docker run -d \
  --name localstack \
  -p 4566:4566 \
  -e SERVICES=ec2,vpc \
  localstack/localstack:3.0.0
```

> 최신 버전은 라이선스 필요 → 3.0.0 사용

## 디렉토리 구조

```
terraform-soc/
├── main.tf
└── modules/
    ├── elk/
    └── aws/
        ├── main.tf       ← VPC + SG + EC2
        ├── variables.tf
        └── outputs.tf
```

## modules/aws/variables.tf

```hcl
variable "region" {
  default = "ap-northeast-2"
}

variable "instance_type" {
  default = "t3.micro"
}

variable "ami_id" {
  default = "ami-0c9c942bd7bf113a2"
}
```

## modules/aws/main.tf

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2 = "http://localhost:4566"
  }
}

resource "aws_vpc" "soc_vpc" {
  cidr_block = "10.0.0.0/16"
  tags = { Name = "soc-vpc" }
}

resource "aws_subnet" "soc_subnet" {
  vpc_id     = aws_vpc.soc_vpc.id
  cidr_block = "10.0.1.0/24"
  tags = { Name = "soc-subnet" }
}

resource "aws_security_group" "soc_sg" {
  name   = "soc-sg"
  vpc_id = aws_vpc.soc_vpc.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH"
  }

  ingress {
    from_port   = 9200
    to_port     = 9200
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
    description = "Elasticsearch"
  }

  ingress {
    from_port   = 5601
    to_port     = 5601
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
    description = "Kibana"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "soc_server" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.soc_subnet.id
  vpc_security_group_ids = [aws_security_group.soc_sg.id]
  tags = { Name = "soc-server" }
}
```

## modules/aws/outputs.tf

```hcl
output "vpc_id" {
  value = aws_vpc.soc_vpc.id
}

output "instance_id" {
  value = aws_instance.soc_server.id
}

output "security_group_id" {
  value = aws_security_group.soc_sg.id
}
```

## 검증 결과

```bash
$ terraform state list | grep aws
module.aws.aws_instance.soc_server
module.aws.aws_security_group.soc_sg
module.aws.aws_subnet.soc_subnet
module.aws.aws_vpc.soc_vpc
```

## 배운 것

- LocalStack 최신 버전은 유료 → `3.0.0` 구버전 사용
- `vpc`는 별도 endpoint 없음 → `endpoints { ec2 = ... }` 만으로 VPC 리소스도 처리
- LocalStack 연동 시 `skip_credentials_validation`, `skip_metadata_api_check`, `skip_requesting_account_id` 3개 필수
- `-target=module.aws` 로 특정 모듈만 plan/apply 가능
- 실제 AWS 전환 시 provider 블록에서 endpoints, skip 옵션만 제거하면 동일 코드로 배포 가능
