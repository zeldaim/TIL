# TIL — Docker + containerd 구조와 파일시스템

날짜: 2026-04-15

---

## 배운 것

### 1. Docker volume이 보이는데 실제 파일이 없는 이유

`docker volume ls`에 볼륨이 표시되어도 `/var/lib/docker/volumes/<name>/_data/`에 파일이 없을 수 있다.

현재 Docker는 **containerd**를 스토리지 백엔드로 사용하기 때문에 실제 데이터가 여기 있다:

```
/var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/snapshots/
```

볼륨 포인터(메타데이터)와 실제 데이터가 분리되어 있어서 `rm /var/lib/docker/volumes/*`만 해도 공간이 안 풀린다.

---

### 2. overlay 파일시스템이란?

컨테이너는 이미지 레이어를 **읽기 전용**으로 쌓고, 변경사항만 **쓰기 레이어(upperdir)**에 저장한다.

```
upperdir (변경사항)   ← 컨테이너가 파일 쓰는 곳
lowerdir (이미지)     ← 읽기 전용 레이어들
merged   (통합 뷰)    ← 컨테이너가 실제로 보는 파일시스템
```

볼륨 데이터가 수백 개 스냅샷 레이어에 분산되어 있어서 `du`로 찾기 어렵고 일반 `rm`으로는 공간이 안 풀린다.

---

### 3. `du`가 안 되고 `ls`가 되는 이유

디스크가 100% 꽉 찼을 때 `du` 명령어는 실행 중 임시 버퍼가 필요해서 실패한다. `ls`는 단순 디렉토리 읽기라 버퍼가 거의 필요 없어서 된다.

---

### 4. 삭제했는데 공간이 안 풀리는 이유

프로세스가 파일 핸들을 잡고 있으면 `rm`으로 삭제해도 공간이 반환되지 않는다. 해당 프로세스(Docker, containerd)를 완전히 중지해야 공간이 풀린다.

```bash
sudo systemctl stop docker docker.socket containerd
```

---

### 5. Docker와 containerd의 관계

```
사용자 → Docker CLI
              ↓
         Docker daemon (dockerd)
              ↓
         containerd  ← 실제 컨테이너/이미지 관리
              ↓
         runc  ← 실제 컨테이너 실행
```

Docker는 사용자 인터페이스이고 실제 작업은 containerd가 담당한다. 그래서 Docker 데이터를 완전히 지우려면 둘 다 초기화해야 한다.

---

### 6. Wazuh 에이전트 등록 2단계

```
1단계: agent-auth (등록)
   에이전트 → Manager에 "나 등록해줘" 요청
   Manager → 에이전트 이름, ID, 인증키 발급

2단계: 서비스 시작 (연결)
   에이전트가 인증키로 Manager에 접속
   Active 상태가 됨
```

`manage_agents -l` = 등록된 전체 목록  
`agent_control -l` = 현재 접속 중인 목록

---

### 7. XML vs YAML 들여쓰기

| | XML | YAML |
|---|---|---|
| 구조 결정 | `<태그>` 열고 닫기 | 들여쓰기 |
| 들여쓰기 역할 | 가독성만 | 구조 결정 |
| 틀려도 동작? | 동작함 | 오류 발생 |

---

### 8. self-signed certificate란?

외부 CA(인증기관)가 아닌 자체적으로 CA를 만들어 서명한 인증서.

Wazuh는 설치 시 자체 CA를 생성하고 Manager, Indexer, Dashboard 각각의 인증서를 발급한다. 이 인증서로 컴포넌트 간 TLS 통신을 암호화한다.

Docker 데이터를 초기화하면 인증서도 같이 삭제되므로 재설치 시 반드시 재생성해야 한다.

```bash
docker compose -f generate-indexer-certs.yml run --rm generator
```

---

## 느낀 점

디스크가 꽉 찼을 때 Docker 환경에서는 단순히 파일 삭제로 해결이 안 된다. containerd 레이어 구조를 이해하지 못하면 `du`는 29G를 가리키는데 `rm`해도 공간이 안 풀리는 상황을 이해하기 어렵다. 결국 서비스 레벨에서 완전히 멈추고 초기화하는 것이 가장 확실한 방법이다.
