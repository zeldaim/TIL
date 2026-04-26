# Wazuh + Sysmon EventID 13 탐지 구현 트러블슈팅 TIL

> **날짜**: 2026-04-24  
> **목표**: Sysmon EventID 13 (레지스트리 Run 키 변조)을 Wazuh로 탐지해 T1547 알럿 발생  
> **환경**: VMware Workstation / Rocky Linux 9 (Wazuh Docker) / Windows 10 (Sysmon + Wazuh agent)

---

## 최종 상태

| 항목 | 결과 |
|---|---|
| Sysmon config 적용 | ✅ EventID 12/13 감시 활성화 |
| Windows → Rocky 네트워크 | ✅ 1514/tcp 연결 확인 |
| Wazuh agent Active | ✅ DESKTOP-5408CBA |
| Sysmon EventID 13 감지 | ✅ Windows 이벤트 뷰어 확인 |
| EventID 13 Wazuh 수신 | 🔄 진행 중 (Rule overwrite 적용) |

---

## 발견한 핵심 문제들

### 문제 1 — HKU vs HKCU 경로 불일치

**현상**: Wazuh 규칙 정규식이 `HKCU\SOFTWARE\...`를 매칭하도록 작성했는데 알럿 미발생

**원인**: PowerShell로 레지스트리를 변경하면 Sysmon이 실제로 기록하는 경로는 `HKCU`가 아니라 **`HKU\S-1-5-21-숫자\SOFTWARE\...`** 형태

```
# 예상했던 경로
HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run\SOCLabTest

# 실제 Sysmon이 기록한 경로
HKU\S-1-5-21-3385978295-689239366-777767380-1001\SOFTWARE\Microsoft\Windows\CurrentVersion\Run\SOCLabTest
```

**교훈**: 레지스트리 경로는 항상 실제 이벤트를 먼저 확인한 뒤 정규식을 작성해야 함. `HKCU`는 Windows API 추상화 경로이고 실제 로그에는 SID가 포함된 `HKU` 형태로 기록됨

**해결**: 정규식에 `.*` 추가해 경로 앞부분 무시

```xml
<!-- 수정 전 -->
(?i)\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run

<!-- 수정 후 -->
(?i).*SOFTWARE.*Microsoft.*Windows.*CurrentVersion.*Run
```

---

### 문제 2 — Wazuh 규칙 파일 권한 오류

**현상**: `docker cp`로 규칙 파일 복사 후 manager가 시작 안 됨

**에러**:
```
wazuh-analysisd: WARNING: Could not open file 'etc/rules/local_rules.xml' due to [(13)-(Permission denied)]
```

**원인**: `docker cp`로 복사한 파일의 소유자가 `root`로 설정됨. Wazuh는 `wazuh` 유저로 실행되므로 읽기 불가

**해결**:
```bash
docker exec single-node-wazuh.manager-1 chown wazuh:wazuh /var/ossec/etc/rules/local_rules.xml
docker exec single-node-wazuh.manager-1 chmod 660 /var/ossec/etc/rules/local_rules.xml
```

---

### 문제 3 — XML 문법 오류로 analysisd 시작 실패

**현상**: 여러 번 Python으로 규칙 파일 수정하다가 XML이 깨짐

**에러**:
```
wazuh-testrule: ERROR: (1226): Error reading XML file 'etc/rules/local_rules.xml': 
XMLERR: Attribute 'id' not followed by a " or '. (line 2).
```

**원인**: Python `str.replace()`로 XML을 직접 수정하는 과정에서 따옴표, 이스케이프 문자 등이 꼬임

**해결**: 파일을 깔끔하게 처음부터 다시 작성
```bash
docker exec single-node-wazuh.manager-1 bash -c 'cat > /var/ossec/etc/rules/local_rules.xml << '"'"'EOF'"'"'
<group name="sysmon,windows,">
  <rule id="100220" level="12">
    ...
  </rule>
</group>
EOF'
```

**교훈**: 규칙 파일을 수정할 때는 항상 배포 전 문법 검증 필수
```bash
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest -V
```

---

### 문제 4 — Level 0 규칙이 child rule 체이닝 차단

**현상**: `if_sid>61615`나 `if_sid>185011`로 부모 규칙을 지정해도 커스텀 규칙이 발동 안 됨

**원인**: Wazuh에서 **`level="0"` 규칙은 suppress(억제) 규칙**으로 동작. 이벤트를 흡수하고 child rule 체이닝을 막음

```xml
<!-- Wazuh 기본 규칙 — level 0 이라서 child rule이 발동 안 됨 -->
<rule id="185011" level="0">
    <match>Microsoft-Windows-Sysmon/Operational: INFORMATION(13)</match>
    <group>sysmon_event_13,</group>
</rule>
```

**해결**: `overwrite="yes"`로 해당 규칙을 덮어써서 level을 올림
```xml
<rule id="185011" level="3" overwrite="yes">
    <if_sid>18101</if_sid>
    <match>Microsoft-Windows-Sysmon/Operational: INFORMATION(13)</match>
    <description>Sysmon - Event 13</description>
    <group>sysmon_event_13,</group>
</rule>
```

**교훈**: Wazuh 커스텀 규칙 작성 시 부모 규칙의 level을 반드시 확인. level 0 부모는 child rule을 차단함

---

### 문제 5 — Wazuh Docker 환경에서 규칙 파일 위치

**현상**: Rocky Linux 호스트의 `/var/ossec/etc/rules/`에 파일을 복사하려 했으나 실패

**원인**: Wazuh manager가 Docker 컨테이너 안에서 실행 중. 호스트의 `/var/ossec/`는 agent 경로

**해결**: `docker cp`로 컨테이너 안에 직접 복사
```bash
docker cp local_rules.xml single-node-wazuh.manager-1:/var/ossec/etc/rules/local_rules.xml
```

---

## 오늘 배운 Wazuh 규칙 구조

```
이벤트 수신
    ↓
부모 규칙 매칭 (예: 61600 — Sysmon 기본)
    ↓
EventID별 분류 규칙 (예: 61615 — EventID 13, level 0)
    ↓ ← level 0이면 여기서 체이닝 차단!
커스텀 child 규칙 (예: 100220 — Run 키 탐지)
    ↓
알럿 발생
```

---

## 현재 적용된 local_rules.xml

```xml
<group name="sysmon,windows,">
  <!-- EventID 13 suppress 해제 — level 0 → level 3 overwrite -->
  <rule id="185011" level="3" overwrite="yes">
    <if_sid>18101</if_sid>
    <match>Microsoft-Windows-Sysmon/Operational: INFORMATION(13)</match>
    <description>Sysmon - Event 13</description>
    <group>sysmon_event_13,</group>
  </rule>

  <!-- T1547 Run 키 변조 탐지 -->
  <rule id="100220" level="12">
    <if_sid>185011</if_sid>
    <field name="win.eventdata.targetObject" type="pcre2">(?i)CurrentVersion.Run</field>
    <description>T1547 - Run key modified by $(win.eventdata.image)</description>
    <mitre><id>T1547.001</id></mitre>
    <group>persistence,registry,autorun,</group>
  </rule>
</group>
```

---

## 다음 단계

- [ ] EventID 13 알럿 최종 확인 (overwrite 규칙 적용 후)
- [ ] Windows 서비스 등록 탐지 (EventID 7045, T1543) 추가
- [ ] False Positive 제거 — 정상 프로세스 whitelist 추가
- [ ] Active Response 연동 — 탐지 시 자동 레지스트리 키 삭제

---

## 트러블슈팅 핵심 명령어 모음

```bash
# Wazuh manager 상태 확인
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-control status

# 규칙 문법 검증
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest -V

# 실시간 알럿 모니터링
docker exec single-node-wazuh.manager-1 tail -f /var/ossec/logs/alerts/alerts.json

# 특정 규칙 알럿 필터링
docker exec single-node-wazuh.manager-1 grep -a "100220" /var/ossec/logs/alerts/alerts.json

# agent 연결 상태 확인
docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l

# 규칙 파일 권한 수정
docker exec single-node-wazuh.manager-1 chown wazuh:wazuh /var/ossec/etc/rules/local_rules.xml
docker exec single-node-wazuh.manager-1 chmod 660 /var/ossec/etc/rules/local_rules.xml
```
