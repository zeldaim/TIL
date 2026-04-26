# T1547 Persistence 탐지 — 구현 현황 (부분완성)

> **날짜**: 2026-04-24 ~ 2026-04-26
> **MITRE**: T1547.001 - Boot or Logon Autostart Execution: Registry Run Keys
> **환경**: Rocky Linux 9 (Wazuh 4.9.0 Docker) / Windows 10 (Sysmon v15.20 + Wazuh Agent 4.9.2)

---

## 구현 목표

```
공격자 PowerShell
    ↓ HKCU\...\CurrentVersion\Run 키 생성
Sysmon EventID 13 (Registry SetValue)
    ↓
Wazuh Agent 전송
    ↓
Wazuh Manager Rule 매칭
    ↓
Alert 발생 (level 12, T1547.001)
```

---

## 완료된 것

### ✅ 1. Sysmon 설정 — EventID 12/13 감시

`sysmon_persistence.xml` 적용. Run 키 변조 감시 활성화.

```xml
<RegistryEvent onmatch="include">
  <Compound Rule T1547_Run_Key_Create combine using Or>
    <TargetObject filter: contains value: 'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'>
  </Compound>
</RegistryEvent>
<RegistryEvent onmatch="exclude">
  <Compound Rule Exclude_System_Processes>
    <Image filter: is value: 'C:\Windows\System32\svchost.exe'>
    <Image filter: is value: 'C:\Windows\System32\services.exe'>
  </Compound>
</RegistryEvent>
```

**검증**:
```powershell
# 공격 시뮬레이션
New-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" `
  -Name "EvilTest" -Value "calc.exe" -PropertyType String -Force

# Sysmon 캡처 확인
Get-WinEvent -LogName "Microsoft-Windows-Sysmon/Operational" -MaxEvents 10 `
  | Where-Object {$_.Id -eq 13}
# → EventID 13 캡처 확인 ✅
```

---

### ✅ 2. Wazuh Agent 4.9.2 설치 및 연결

- 4.9.0 → 4.9.2 업그레이드 (syscollector.dll 크래시 버그 해결)
- Windows ossec.conf Sysmon eventchannel 설정

```xml
<localfile>
  <location>Microsoft-Windows-Sysmon/Operational</location>
  <log_format>eventchannel</log_format>
</localfile>
```

**검증**:
```bash
docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l
# ID: 003, Name: DESKTOP-5408CBA, Active ✅
```

---

### ✅ 3. EventID 13 → Manager archives 전송

EventID 13 이벤트가 Wazuh Manager까지 정상 전달됨.

**archives.json 수신 확인**:
```json
{
  "timestamp": "2026-04-26T09:43:46.191+0000",
  "agent": {"id": "003", "name": "DESKTOP-5408CBA"},
  "decoder": {"name": "windows_eventchannel"},
  "data": {
    "win": {
      "system": {"eventID": "13"},
      "eventdata": {
        "ruleName": "T1547_Run_Key_Create",
        "image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "targetObject": "HKU\\S-1-5-21-...\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run\\EvilTest"
      }
    }
  }
}
```

---

### ✅ 4. 파이프라인 디버깅 방법론 확립

각 단계별 확인 명령어:

| 단계 | 확인 명령 |
|------|-----------|
| Sysmon 캡처 | `Get-WinEvent -LogName "Microsoft-Windows-Sysmon/Operational" -MaxEvents 10 \| Where-Object {$_.Id -eq 13}` |
| Agent 연결 | `docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l` |
| Manager 수신 | `docker exec single-node-wazuh.manager-1 grep -a "키워드" /var/ossec/logs/archives/archives.json \| tail -1` |
| Rule 발동 | `docker exec single-node-wazuh.manager-1 grep -a "키워드" /var/ossec/logs/alerts/alerts.json \| tail -3` |
| Rule 테스트 | `docker exec -it single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest` |

---

## 미완료 — Rule Alert 발동

### 현재 rule 구조

```
windows_eventchannel decoder
    ↓
61600 (Sysmon 기본, level 0)
    ↓
61615 / 185011 (EventID 13 분류, level 0) → sysmon_event_13 그룹 부여
    ↓
92300 (Run 키 필터, level 3) ← 0860-sysmon_id_13.xml
    ↓ ← 여기서 매칭 실패
100220 (PowerShell 탐지, level 12)
```

### 시도한 것들

| 시도 | 결과 |
|------|------|
| local_rules.xml overwrite (level 0 → level 3) | if_group overwrite 불가 (WARNING 7605) |
| 0860 파일 92300 regex 수정 | archives 도달 확인, alert 미발동 |
| 0860 파일 92300 if_group → if_sid 변경 | alert 미발동 |
| local_rules.xml 독립 rule (decoded_as) | alert 미발동 |

### 현재 적용된 rule (0860-sysmon_id_13.xml)

```xml
<rule id="92300" level="3">
  <if_sid>61600</if_sid>
  <field name="win.system.eventID" type="pcre2">^13$</field>
  <field name="win.eventdata.targetObject" type="pcre2">(?i)SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run</field>
  <description>T1547.001 - Registry Run key modified</description>
  <mitre><id>T1547.001</id></mitre>
  <group>sysmon_event_13,</group>
</rule>

<rule id="100220" level="12">
  <if_sid>92300</if_sid>
  <field name="win.eventdata.image" type="pcre2">(?i)powershell</field>
  <field name="win.eventdata.targetObject" type="pcre2">(?i)CurrentVersion\\Run</field>
  <description>T1547 - Run key modified via PowerShell</description>
  <mitre><id>T1547.001</id></mitre>
  <group>persistence,registry,autorun,</group>
</rule>
```

### 다음 시도 (내일 30분)

```bash
# analysisd 디버그 로그로 rule 매칭 과정 직접 확인
# ossec.conf에 추가
<logging>
  <log_level>2</log_level>
</logging>

docker restart single-node-wazuh.manager-1 && sleep 40

# 테스트 후
docker exec single-node-wazuh.manager-1 grep -a "EvilTodayN" /var/ossec/logs/ossec.log | tail -30
# → 어느 rule이 이벤트를 처리하는지 직접 확인 가능
```

---

## 핵심 발견 및 교훈

| 발견 | 교훈 |
|------|------|
| HKCU vs HKU — PowerShell로 설정 시 실제 로그는 HKU\SID 형태 | regex는 실제 이벤트 확인 후 작성 |
| 기존 키 재설정 시 EventID 13 미발생 | 테스트 시 항상 새 키 이름 사용 |
| Docker cp 후 파일 소유자 root로 변경 | cp 후 항상 chown wazuh:wazuh |
| logall_json 설정이 재시작 시 휘발 | 호스트 볼륨 소스 파일 수정 필수 |
| if_group은 overwrite 불가 | 원본 파일 직접 수정 필요 |
| Wazuh 4.9.0 syscollector.dll 크래시 버그 | 4.9.2 이상 사용 |
