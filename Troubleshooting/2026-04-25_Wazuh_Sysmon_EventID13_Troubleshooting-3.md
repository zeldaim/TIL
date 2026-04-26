# TIL: Wazuh + Sysmon EventID 13 파이프라인 디버깅 (2026-04-25)

## 작업 목표
Sysmon EventID 13 (Registry SetValue) → Wazuh Agent → Manager → Rule 100220 발동 파이프라인 구축

---

## 오늘 한 것

### 1. Wazuh Agent 4.9.0 → 4.9.2 업그레이드
**배경**: 4.9.0에서 `syscollector.dll_unloaded` 크래시 버그 발생. Agent가 주기적으로 죽으면서 이벤트 전송 누락.

**절차**:
```powershell
# MSI 다운로드
New-Item -ItemType Directory -Path "C:\temp" -Force
Invoke-WebRequest -Uri "https://packages.wazuh.com/4.x/windows/wazuh-agent-4.9.2-1.msi" -OutFile "C:\temp\wazuh-agent.msi"

# 설치 (로그 포함)
msiexec /i "C:\temp\wazuh-agent.msi" `
  WAZUH_MANAGER="192.168.190.128" `
  WAZUH_REGISTRATION_SERVER="192.168.190.128" `
  WAZUH_AGENT_NAME="windows-victim" `
  /qn /l*v "C:\temp\wazuh-install.log"

# 버전 확인
Get-WmiObject -Class Win32_Product | Where-Object {$_.Name -like "*wazuh*"} | Select-Object Name, Version
```

**결과**: 4.9.2 설치 확인. 로그 마지막 `returning 0` = 성공.

**교훈**: `/qn` silent 모드는 성공/실패 출력이 없으므로 `/l*v` 로그 옵션 항상 같이 쓸 것.

---

### 2. ossec.conf Sysmon 채널 설정 확인 및 수정

**발견**: Windows agent `ossec.conf`에 `localfile` eventchannel 설정이 누락되거나 중복된 상태.

**올바른 설정** (`</ossec_config>` 바로 위에 위치해야 함):
```xml
<localfile>
  <location>Microsoft-Windows-Sysmon/Operational</location>
  <log_format>eventchannel</log_format>
</localfile>
```

**확인 방법**:
```powershell
# Sysmon 채널 설정 여부 확인
Select-String "Sysmon" "C:\Program Files (x86)\ossec-agent\ossec.conf"

# XML 유효성 확인
[xml](Get-Content "C:\Program Files (x86)\ossec-agent\ossec.conf" -Raw)
echo "XML valid"

# conf 마지막 구조 확인
Get-Content "C:\Program Files (x86)\ossec-agent\ossec.conf" | Select-Object -Last 8
```

**주의**: PowerShell로 파일 편집 시 라인 수 계산 오류로 `</ossec_config>` 누락 가능. 편집 후 반드시 마지막 구조 확인.

---

### 3. Wazuh Rule 100220 필드명 오류 수정

**문제**: `local_rules.xml`에서 필드명을 `win.eventdata.image`로 작성했으나 실제 decoder 출력 필드명은 `image`, `targetObject`.

**archives.json에서 실제 필드 구조 확인**:
```bash
docker exec single-node-wazuh.manager-1 grep -a "EvilToday3" /var/ossec/logs/archives/archives.json | tail -1 | python3 -m json.tool 2>/dev/null | grep -E "image|targetObject|rule|decoder"
```

**실제 decoder 출력**:
```json
"decoder": {
  "ruleName": "T1547_Run_Key_Create",
  "image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
  "targetObject": "HKU\\S-1-5-21-...\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run\\EvilToday3"
}
```

**수정된 룰 (`0860-sysmon_id_13.xml` 내 92302 블록 앞에 삽입)**:
```xml
<rule id="100220" level="12">
  <if_sid>92300</if_sid>
  <field name="image" type="pcre2">(?i)powershell</field>
  <field name="targetObject" type="pcre2">(?i)CurrentVersion\\Run</field>
  <description>T1547 - Run key modified via PowerShell</description>
  <mitre><id>T1547.001</id></mitre>
  <group>persistence,registry,autorun,</group>
</rule>
```

**파일 수정 절차** (docker cp 방식):
```bash
# 컨테이너에서 꺼내기
docker cp single-node-wazuh.manager-1:/var/ossec/ruleset/rules/0860-sysmon_id_13.xml ~/0860-sysmon_id_13.xml

# vi로 수정 후 다시 넣기
docker cp ~/0860-sysmon_id_13.xml single-node-wazuh.manager-1:/var/ossec/ruleset/rules/0860-sysmon_id_13.xml
docker restart single-node-wazuh.manager-1 && sleep 40
```

---

### 4. 파이프라인 각 단계 디버깅 방법 정리

```
PowerShell → Registry SetValue → Sysmon EventID 13 → Wazuh Agent → Manager → Rule 발동
```

**각 단계 확인 명령**:

| 단계 | 확인 명령 |
|------|-----------|
| Sysmon 캡처 여부 | `Get-WinEvent -LogName "Microsoft-Windows-Sysmon/Operational" -MaxEvents 5 \| Where-Object {$_.Id -eq 13}` |
| Agent 연결 상태 | `Get-Content "C:\Program Files (x86)\ossec-agent\ossec.log" \| Select-Object -Last 10` |
| Manager 수신 여부 | `docker exec single-node-wazuh.manager-1 grep -a "키워드" /var/ossec/logs/archives/archives.json \| wc -l` |
| Rule 발동 여부 | `docker exec single-node-wazuh.manager-1 grep -a "키워드\|룰ID" /var/ossec/logs/alerts/alerts.json \| tail -5` |
| Agent 목록 확인 | `docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l` |

**logall 활성화** (archives 전체 수집, 디버깅 시):
```bash
docker exec single-node-wazuh.manager-1 sed -i 's/<logall>no<\/logall>/<logall>yes<\/logall>/' /var/ossec/etc/ossec.conf
docker exec single-node-wazuh.manager-1 sed -i 's/<logall_json>no<\/logall_json>/<logall_json>yes<\/logall_json>/' /var/ossec/etc/ossec.conf
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-control restart
```

---

### 5. Sysmon 설정 관련 발견사항

- **Sysmon 서비스는 일반 `Restart-Service`로 재시작 불가** (커널 드라이버). Config 재적용은 `-c` 옵션 사용:
  ```powershell
  C:\Windows\sysmon64.exe -c "C:\Users\yhc\Desktop\sysmon_persistence.xml"
  ```
- EventID 13 (SetValue)은 **이미 존재하는 키에 동일 값 재설정 시 발생하지 않음**. 테스트 전 기존 키 삭제 필요.
- Sysmon config 재적용 후 EventID 13 캡처 동작 확인됨.

---

## 미해결 사항 (내일 계속)

- **Sysmon EventID 13 → Wazuh Agent 전송 간헐적 실패**: archives에 EventID 12는 오는데 13은 안 오는 현상. Agent online 상태임에도 eventchannel 구독이 불안정.
- **가설**: Sysmon 드라이버 버퍼 문제 또는 agent eventchannel reader 타이밍 이슈.
- **다음 시도**: Windows 재부팅 후 Sysmon + Wazuh agent 순서대로 시작하여 재테스트.

---

## 완료된 것

- [x] Wazuh Agent 4.9.2 업그레이드 (4.9.0 크래시 버그 해결)
- [x] ossec.conf Sysmon eventchannel 설정 확인
- [x] Rule 100220 필드명 오류 수정 (`win.eventdata.image` → `image`)
- [x] 파이프라인 각 단계 디버깅 방법론 확립
- [x] logall로 archives 전송 확인 방법 습득
- [ ] Rule 100220 실제 발동 확인
