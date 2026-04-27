# 2026-04-27 Wazuh EventID 13 파이프라인 디버깅 TIL

> **날짜**: 2026-04-27
> **환경**: VMware Workstation / Rocky Linux 9 (Wazuh Docker) / Windows 10 (Sysmon + Wazuh agent 4.9.2)
> **목표**: Sysmon EventID 13 (Run 키 변조) → Wazuh alert 발동 (rule 100250)

---

## 최종 상태

| 단계 | 상태 | 비고 |
|------|------|------|
| Sysmon EventID 13 캡처 | ✅ | |
| Agent → Manager archives 전송 | ✅ | |
| decoder: windows_eventchannel | ✅ | |
| Rule 발동 | ❌ | 미해결 |

---

## 오늘 발견한 문제들

### 문제 1 — Agent Disconnected

**현상**: archives에 이벤트가 안 옴

**원인**: Windows VM이 꺼져 있었음. agent_control -l 에서 003 Disconnected 상태.

**해결**: Windows VM 켜고 WazuhSvc 시작

---

### 문제 2 — 0595 룰파일 버그 (^INFORMATIONS$)

**현상**: 61600 룰이 한 번도 발동 안 함

**원인**: `0595-win-sysmon_rules.xml`의 61600 룰에 오탈자
```xml
<!-- 버그 -->
<field name="win.system.severityValue">^INFORMATIONS$</field>

<!-- 수정 -->
<field name="win.system.severityValue">^INFORMATION$</field>
```

**해결**:
```bash
docker cp single-node-wazuh.manager-1:/var/ossec/ruleset/rules/0595-win-sysmon_rules.xml ~/0595-win-sysmon_rules.xml
sed -i 's/\^INFORMATIONS\$/^INFORMATION$/' ~/0595-win-sysmon_rules.xml
docker cp ~/0595-win-sysmon_rules.xml single-node-wazuh.manager-1:/var/ossec/ruleset/rules/0595-win-sysmon_rules.xml
docker exec single-node-wazuh.manager-1 chown wazuh:wazuh /var/ossec/ruleset/rules/0595-win-sysmon_rules.xml
docker exec single-node-wazuh.manager-1 chmod 660 /var/ossec/ruleset/rules/0595-win-sysmon_rules.xml
docker restart single-node-wazuh.manager-1
```

**결과**: 수정됐지만 alert 여전히 미발동 → 다른 원인 존재

---

### 문제 3 — local_rules.xml 로드 안 됨 (핵심)

**현상**: local_rules.xml에 룰 추가해도 `Total rules enabled: '6999'` 고정

**원인 1**: ossec.conf에 local_rules.xml include 없음
```bash
# 호스트 볼륨 소스 파일에 추가
sed -i 's|<!-- User-defined ruleset -->|<!-- User-defined ruleset -->\n    <rule_include>etc/rules/local_rules.xml</rule_include>|' \
  /home/yhc/wazuh-docker/single-node/config/wazuh_cluster/wazuh_manager.conf
```
→ `rule_include` 태그가 Wazuh에서 지원 안 됨. 효과 없음.

**원인 2**: `/var/ossec/etc/rules/` 디렉토리 소유자 문제
```
drwxrwx---. 2 systemd-coredump systemd-coredump  ← 문제
drwxrwx---. 2 wazuh wazuh  ← 정상
```

**핵심 발견**: Rocky Linux 호스트에서 UID 999 = `systemd-coredump`. 컨테이너 안 wazuh도 UID 999. 즉 **같은 UID라서 실제 권한 문제는 없었음**.

**실제 원인**: `rule_dir>etc/rules`가 ossec.conf에 있는데도 로드 안 됨. 테스트로 룰 2개 넣으니 7000이 됐다가 1개로 줄이니 6999로 돌아옴 → **6999가 이미 local_rules.xml 포함한 숫자**일 가능성.

---

### 문제 4 — decoded_as 직접 매칭도 실패

**시도**:
```xml
<rule id="100250" level="12">
  <decoded_as>windows_eventchannel</decoded_as>
  <field name="win.system.eventID" type="pcre2">^13$</field>
  <field name="win.eventdata.targetObject" type="pcre2">(?i)CurrentVersion\\Run</field>
  ...
</rule>
```

**결과**: archives 도달 확인, alerts 미발동. if_sid 체인 우회해도 동일.

---

## 오늘 확인한 룰 체인 구조

```
60000 (decoded_as: windows_eventchannel, providerName: ".+")
  └─ 60004 (channel: Microsoft-Windows-Sysmon/Operational)
       └─ 61600 (severityValue: ^INFORMATION$)  ← 오탈자 수정됨
            └─ 92300 (eventID: 13 + targetObject: Run)  ← 0860 파일
                 └─ 100220 (image: powershell)
```

**확인된 사실**:
- 60106 (Windows Logon Success)는 정상 발동 → 60103→60001 체인 정상
- Sysmon 체인(60000→60004→61600→92300)만 실패
- archives decoder 필드: `windows_eventchannel` ✅
- archives severityValue: `INFORMATION` ✅
- archives channel: `Microsoft-Windows-Sysmon/Operational` ✅
- 모든 조건이 맞는데 어느 룰도 매칭 안 됨

---

## 미해결 — 내일 확인할 것

```bash
# 1. analysisd 디버그 레벨 올려서 룰 매칭 과정 추적
# ossec.conf에 추가:
# <logging><log_level>2</log_level></logging>

# 2. 60004가 실제로 발동하는지 확인
# 60004 level을 1 이상으로 overwrite해서 alerts에 찍히게

# 3. wazuh-logtest에서 실제 agent 전송 방식으로 테스트
# (full_log가 아닌 실제 이벤트 포맷으로)
```

---

## Docker + Wazuh 파일 수정 교훈

```
Rocky Linux UID 999 = systemd-coredump = 컨테이너 wazuh
→ 호스트에서 ls -la 하면 systemd-coredump로 보이지만 실제로는 같은 UID

파일 수정 시 권한이 날아가는 이유:
- docker exec bash -c 'cat >' → root(0)로 생성
- sudo tee → root(0)로 생성
- sudo vi/sed → root(0)로 생성
→ 수정 후 항상 chown 999:999 필요 (단, 실제로는 같은 UID라 문제없을 수도)

영구 수정은 반드시 호스트 volume 소스 파일 직접 수정:
/var/lib/docker/volumes/single-node_wazuh_etc/_data/rules/local_rules.xml
```

---

## 핵심 명령어

```bash
# rules 로드 수 확인
docker exec single-node-wazuh.manager-1 grep -i "rules enabled" /var/ossec/logs/ossec.log | tail -3

# volume 실제 경로
/var/lib/docker/volumes/single-node_wazuh_etc/_data/rules/local_rules.xml

# archives에서 특정 이벤트 필드 확인
docker exec single-node-wazuh.manager-1 grep -a "키워드" /var/ossec/logs/archives/archives.json | \
  python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('decoder',{}))"

# agent 연결 상태
docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l
```

---

## 현재 가장 유력한 원인 가설

**60004가 실제로 발동 안 하고 있을 가능성**

archives.json에서 파이썬으로 뽑은 channel 값은 정상이지만, analysisd가 룰 매칭할 때 보는 raw 데이터는 다를 수 있음. archives.json은 이미 파싱된 결과고, 실제 매칭 시점의 필드값과 차이가 있을 수 있음.

---

## 내일 시도할 다른 방법들

### 방법 1 — analysisd 디버그 로그 (최우선)
ossec.conf에 추가:
```xml
<logging>
  <log_level>2</log_level>
</logging>
```
룰 매칭 과정 전체가 ossec.log에 찍힘. 어느 단계에서 끊기는지 정확히 확인 가능.

### 방법 2 — Wazuh API로 룰 테스트
logtest를 API로 호출하면 실제 analysisd가 처리하는 방식으로 테스트 가능. 파일 권한 문제 없음.
```bash
curl -k -X POST "https://localhost:55000/security/user/authenticate" \
  -H "Content-Type: application/json" \
  -d '{"username":"wazuh","password":"wazuh"}' 
# 토큰 발급 후 logtest API 호출
```

### 방법 3 — Wazuh 직접 설치 (Docker 제거)
Docker volume/권한 문제 근본 해결. 파일 수정이 깔끔하고 디버깅 훨씬 쉬움. 단, 재설치 비용 있음.
