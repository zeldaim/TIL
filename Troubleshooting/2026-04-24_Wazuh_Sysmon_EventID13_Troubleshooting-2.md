# T1547.001 Run Key 탐지 룰 구현 트러블슈팅

> **날짜:** 2026-04-24  
> **환경:** Wazuh 4.9.0 (Docker single-node) + Windows 10 Agent + Sysmon v15.20  
> **목표:** PowerShell/reg.exe로 `CurrentVersion\Run` 키 수정 시 rule 100220 (level 12) 발동

---

## 📌 최종 구현 목표

```
Windows EventID 13 (Sysmon Registry)
  → Wazuh Agent 전송
  → Manager 룰 매칭
  → Rule 100220 (level 12) Alert 발생
```

---

## 🐛 문제 1: XML 파싱 오류 (스마트 쿼트)

### 증상
```
XMLERR: Attribute 'id' not followed by a " or '. (line 2)
Error loading the rules: 'etc/rules/local_rules.xml'
```

### 원인
heredoc(`<< 'EOF'`)으로 `local_rules.xml` 작성 시 터미널에서 스마트 쿼트(`"`)가 혼입되어 XML 파싱 실패.

### 해결
```bash
# python3으로 직접 파일 작성 (인코딩 문제 우회)
docker exec single-node-wazuh.manager-1 bash -c 'cat > /var/ossec/etc/rules/local_rules.xml << ENDOFFILE
<group name="sysmon,windows,">
  <rule id="100220" level="12">
    ...
  </rule>
</group>
ENDOFFILE'
```

### 교훈
> heredoc 사용 시 따옴표 인코딩 문제가 발생할 수 있음. 복잡한 XML은 `docker cp`로 호스트에서 편집 후 복사하는 것이 안전.

---

## 🐛 문제 2: 파일 권한 (Permission Denied)

### 증상
```
wazuh-analysisd: WARNING: (1103): Could not open file 'etc/rules/local_rules.xml' 
due to [(13)-(Permission denied)]
```

### 원인
`cat >` 명령으로 파일 생성 시 root 소유로 생성됨. wazuh-analysisd 프로세스가 읽기 거부.

### 해결
```bash
docker exec single-node-wazuh.manager-1 chown wazuh:wazuh /var/ossec/etc/rules/local_rules.xml
docker exec single-node-wazuh.manager-1 chmod 660 /var/ossec/etc/rules/local_rules.xml
```

### 확인
```bash
docker exec single-node-wazuh.manager-1 ls -la /var/ossec/etc/rules/local_rules.xml
# 기대값: -rw-rw----. 1 wazuh wazuh
```

---

## 🐛 문제 3: ossec.conf 휘발성 (Docker Volume)

### 증상
`logall`, `logall_json` 설정을 `yes`로 변경해도 `docker restart` 후 `no`로 리셋됨.

### 원인
Docker Compose 환경에서 호스트의 원본 ossec.conf가 컨테이너 내부로 마운트되어 재시작 시 덮어씌워짐.

### 해결 방향
- 호스트의 마운트 소스 파일을 직접 수정해야 함
- `docker inspect`로 마운트 경로 확인 후 호스트 파일 수정

```bash
docker inspect single-node-wazuh.manager-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

### 교훈
> Docker 환경에서는 컨테이너 내부 파일 수정이 재시작 시 휘발됨. 항상 호스트 볼륨 소스 파일을 수정해야 영구 적용됨.

---

## 🐛 문제 4: Wazuh 룰 체이닝 구조 (핵심)

### 증상
Rule 100220이 `if_sid`, `if_group`, `overwrite` 등 모든 방법으로도 발동하지 않음.

### 원인 분석

**Wazuh 룰 매칭 동작 방식:**
- 하나의 이벤트에 대해 **룰 하나만 최종 발동** (first match wins)
- 기본 룰셋(`ruleset/rules/`)이 사용자 룰(`etc/rules/`)보다 먼저 평가됨

**실제 룰 체인 구조 (`0860-sysmon_id_13.xml`):**
```
92300 (level 0) ← if_group: sysmon_event_13
  ├── 92301 (level 12) ← .lnk/.vbs 확장자
  └── 92302 (level 6)  ← reg.exe 사용 시
```

- `92300`이 이미 이벤트를 소비 → `100220` 평가 기회 없음
- `92302`는 `reg.exe`로 Run 키 수정 시 발동 (이미 T1547.001 탐지 중)

### 해결: 원본 룰셋 파일 직접 수정

```bash
# 1. 파일 호스트로 복사
docker cp single-node-wazuh.manager-1:/var/ossec/ruleset/rules/0860-sysmon_id_13.xml ~/0860-sysmon_id_13.xml

# 2. vi로 92302 블록 위에 100220 삽입
vi ~/0860-sysmon_id_13.xml
```

**삽입할 룰 (92302 블록 바로 위):**
```xml
<rule id="100220" level="12">
  <if_sid>92300</if_sid>
  <field name="win.eventdata.image" type="pcre2">(?i)powershell</field>
  <field name="win.eventdata.targetObject" type="pcre2">(?i)CurrentVersion\\Run</field>
  <description>T1547 - Run key modified via PowerShell</description>
  <mitre><id>T1547.001</id></mitre>
  <group>persistence,registry,autorun,</group>
</rule>
```

```bash
# 3. 컨테이너로 복사 후 재시작
docker cp ~/0860-sysmon_id_13.xml single-node-wazuh.manager-1:/var/ossec/ruleset/rules/0860-sysmon_id_13.xml
docker restart single-node-wazuh.manager-1
```

### 교훈
> `local_rules.xml`의 `overwrite="yes"`는 기본 룰셋 파일에 정의된 룰에 대해 제한적으로 작동함.  
> 기본 룰이 이미 이벤트를 소비하면 child 룰 체이닝이 불가능.  
> 근본적인 해결은 원본 룰셋 파일 직접 수정 + 백업 필수.

---

## 🐛 문제 5: Windows Agent 크래시 (Wazuh 4.9.0 버그)

### 증상
```
AppCrash_wazuh-agent.exe: syscollector.dll_unloaded
BEX exception → agent 주기적 크래시 후 재시작
```

Sysmon이 EventID 13을 캡처해도 agent 크래시 타이밍에 전송 실패.

### 원인
Wazuh 4.9.0의 알려진 `syscollector.dll` 버그.

### 해결: Agent 업그레이드

```powershell
# 임시 디렉토리 생성
New-Item -ItemType Directory -Path "C:\temp" -Force

# 4.9.2 다운로드
Invoke-WebRequest -Uri "https://packages.wazuh.com/4.x/windows/wazuh-agent-4.9.2-1.msi" -OutFile "C:\temp\wazuh-agent.msi"

# 설치 (기존 설정 유지)
msiexec /i "C:\temp\wazuh-agent.msi" /q WAZUH_MANAGER="192.168.190.128" WAZUH_REGISTRATION_SERVER="192.168.190.128"
```

---

## ✅ 전체 디버깅 플로우

```
이벤트 미탐지
  │
  ├─ Windows Sysmon 확인
  │    └─ Get-WinEvent -LogName "Microsoft-Windows-Sysmon/Operational"
  │         ├─ EventID 13 없음 → Sysmon config 확인 (sysmon64.exe -c)
  │         └─ EventID 13 있음 → Agent 전송 문제
  │
  ├─ Agent 연결 확인
  │    └─ Test-NetConnection -ComputerName <manager_ip> -Port 1514
  │         ├─ False → Rocky iptables/방화벽 확인
  │         └─ True → Agent 로그 확인
  │
  ├─ Manager 수신 확인
  │    └─ docker exec ... grep -a "eventID.*13" /var/ossec/logs/alerts/alerts.json
  │         ├─ 없음 → Agent 크래시/버그 확인
  │         └─ 있음 → 룰 매칭 문제
  │
  └─ 룰 매칭 확인
       └─ 원하는 rule id가 alerts에 없음
            └─ 기본 룰이 이벤트 선점 → 원본 룰셋 파일 수정
```

---

## 🔑 핵심 명령어 모음

```bash
# Manager 프로세스 상태
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-control status

# 룰 파일 검증
docker exec single-node-wazuh.manager-1 grep -n "100220" /var/ossec/ruleset/rules/0860-sysmon_id_13.xml

# 실시간 alerts 모니터링
docker exec single-node-wazuh.manager-1 bash -c 'tail -f /var/ossec/logs/alerts/alerts.json'

# 네트워크 패킷 확인 (연결 디버깅)
sudo tcpdump -i any -n port 1514 -c 10

# Agent 연결 테스트 (Windows)
Test-NetConnection -ComputerName 192.168.190.128 -Port 1514
```

---

## 📝 참고

- Wazuh 룰 우선순위: `ruleset/rules/` → `etc/rules/` 순서로 로드
- level 0 룰은 alerts를 생성하지 않지만 child 룰 트리거는 가능
- 같은 이벤트에 대해 Wazuh는 **단 하나의 최종 룰만 발동**
- Docker 환경에서 컨테이너 내부 수정은 재시작 시 휘발 → 볼륨 소스 파일 수정 필요
- Wazuh 4.9.0 `syscollector.dll` 크래시 버그 → 4.9.2 이상으로 업그레이드 권장
