# terraform-soc GitHub 레포지토리 생성 및 push

## 순서

### 1. GitHub에서 레포 생성
- github.com → 우측 상단 `+` → `New repository`
- Repository name: `terraform-soc`
- Public, README 없이 생성

### 2. Rocky Linux에서 git 초기화 및 remote 연결

```bash
cd ~/terraform-soc
git init
git remote add origin https://github.com/zeldaim/terraform-soc.git
git branch -M main
```

### 3. .gitignore 추가 (필수)

```bash
cat > .gitignore << 'EOF'
.terraform/
terraform.tfstate
terraform.tfstate.backup
*.tfvars
EOF
```

> `.terraform/` 에는 provider 바이너리가 있어 용량이 수백 MB → GitHub 100MB 제한 초과

### 4. 첫 커밋 및 push 시도

```bash
git add .
git commit -m "feat: Terraform SOC 인프라 초기 커밋"
git push -u origin main
```

**에러 발생:** `.terraform/` 이 이미 히스토리에 커밋된 상태라 `.gitignore` 만으로 제거 불가

### 5. git 히스토리에서 .terraform/ 제거

```bash
git filter-branch --force --index-filter \
  'git rm -r --cached --ignore-unmatch .terraform/' \
  --prune-empty --tag-name-filter cat -- --all

git push -u origin main --force
```

> `filter-branch` → 전체 커밋 히스토리를 재작성해서 특정 파일을 완전히 제거

## 결과

```
* [new branch] main -> main
branch 'main' set up to track 'origin/main'.
```

## 배운 것

- `.gitignore` 는 앞으로 추가될 파일만 무시 → 이미 커밋된 파일은 효과 없음
- `.terraform/` 은 반드시 첫 커밋 전에 `.gitignore` 에 추가해야 함
- GitHub 파일 크기 제한: 단일 파일 100MB 초과 시 push 거부
- 히스토리에서 파일 제거: `git filter-branch` 또는 `git-filter-repo` 사용
- Personal Access Token 생성 시 `repo` 권한 체크 필수
