# 2026-04-26 Wazuh EventID 13 파이프라인 디버깅 TIL

> **날짜**: 2026-04-26
> **환경**: VMware Workstation / Rocky Linux 9 (Wazuh Docker) / Windows 10 (Sysmon + Wazuh agent 4.9.2)
> **목표**: Sysmon EventID 13 (Run 키 변조) → Wazuh alert 발동 (rule 100220/100221)

---

## 최종 상태

| 단계 | 상태 | 비고 |
|------|------|------|
| Sysmon EventID 13 캡처 | ✅ | 64비트 PowerShell로 실행해야 캡처됨 |
| Agent → Manager archives 전송 | ✅ | logall_json 활성화 후 정상 |
| decoder: windows_eventchannel | ✅ | archives에서 확인 |
| Rule 발동 | ❌ | 미해결 |

---

## 발견한 문제들

### 문제 1 — logall_json 휘발 문제

**현상**: archives.json이 Apr 24 이후 업데이트 안 됨. 오늘 이벤트가 archives에 없음.

**원인**: Docker volume 마운트 구조상 컨테이너 내부 ossec.conf 수정이 재시작 시 덮어씌워짐.

**해결**: 호스트 볼륨 소스 파일 직접 수정

```bash
# 마운트 경로 확인
docker inspect single-node-wazuh.manager-1 \
  --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' | grep ossec.conf
# → /home/yhc/wazuh-docker/single-node/config/wazuh_cluster/wazuh_manager.conf

# 영구 수정
sed -i 's/<logall>no<\/logall>/<logall>yes<\/logall>/' \
  /home/yhc/wazuh-docker/single-node/config/wazuh_cluster/wazuh_manager.conf
sed -i 's/<logall_json>no<\/logall_json>/<logall_json>yes<\/logall_json>/' \
  /home/yhc/wazuh-docker/single-node/config/wazuh_cluster/wazuh_manager.conf
```

---

### 문제 2 — 64비트 PowerShell 필요

**현상**: PowerShell에서 레지스트리 키 생성해도 Sysmon EventID 13 미캡처

**원인**: 32비트 PowerShell 실행 시 레지스트리 경로가 WOW6432Node로 리다이렉트됨

**확인**:
```powershell
[Environment]::Is64BitProcess  # True 여야 함
```

---

### 문제 3 — 기존 키 재설정 시 EventID 13 미발생

**현상**: 같은 키 이름으로 반복 테스트 시 Sysmon이 캡처 안 함

**원인**: 이미 존재하는 키에 동일 값 SetValue 시 Sysmon이 이벤트를 발생시키지 않음

**해결**: 반드시 삭제 후 새 이름으로 생성
```powershell
Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "EvilTodayN" -ErrorAction SilentlyContinue
New-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "EvilTodayN+1" -Value "calc.exe" -PropertyType String -Force
```

---

### 문제 4 — 0860 파일의 92300 regex 버그

**현상**: 92300 rule이 Run 키 이벤트를 매칭 못 함

**원인**: 원본 regex의 이스케이프 오류
```
# 원본 (버그 있음)
(?i)SOFTWARE\\\\(WOW6432NODE\\\\M|M)ICROSOFT\\\\WINDOW(S|S NT)\\\\CURRENTVERSION\\\\(RUN|...)
# SOFTWARE\Microsoft 경로를 실제로 못 잡음
```

**해결**:
```xml
<field name="win.eventdata.targetObject" type="pcre2">(?i)SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run</field>
```

---

### 문제 5 — docker cp 후 권한 문제 반복

**현상**: 0860 파일 수정 배포 후 manager가 rule 파일을 못 읽음

**원인**: docker cp 시 파일 소유자가 root로 설정됨

**해결**: cp 후 항상 chown 필수
```bash
docker cp ~/0860-sysmon_id_13.xml single-node-wazuh.manager-1:/var/ossec/ruleset/rules/0860-sysmon_id_13.xml
docker exec single-node-wazuh.manager-1 chown wazuh:wazuh /var/ossec/ruleset/rules/0860-sysmon_id_13.xml
docker exec single-node-wazuh.manager-1 chmod 660 /var/ossec/ruleset/rules/0860-sysmon_id_13.xml
```

---

### 문제 6 — vi swap 파일 충돌

**현상**: vi로 수정 후 cp했는데 이전 버전이 배포됨

**원인**: 백그라운드에 이전 vi 세션이 살아있어서 swap 파일이 남아있었음. 새 vi에서 E(편집)를 선택해도 swap 기반으로 열려서 저장이 꼬임

**해결**:
```bash
rm ~/.0860-sysmon_id_13.xml.swp
# 이후 sed로 수정하는 것이 더 안전
sed -i 's/패턴/교체/' ~/파일.xml
```

---

### 문제 7 — heredoc에서 `$()` bash 해석 문제

**현상**: `bash -c 'cat > file << EOF ... EOF'` 사용 시 `command not found` 에러

**원인**: description에 `$(win.eventdata.targetObject)` 쓰면 bash가 서브쉘로 해석

**해결**: `$` 이스케이프 또는 single-quote heredoc 사용
```bash
# 방법 1: single-quote heredoc
docker exec single-node-wazuh.manager-1 bash -c "cat > /path << 'XMLEOF'
...내용...
XMLEOF"

# 방법 2: description에서 변수 제거
<description>T1547.001 - Run key modified via registry</description>
```

---

### 문제 8 — overwrite="yes"로 if_group 변경 불가

**현상**: local_rules.xml에서 92300 overwrite 시도했지만 if_group 변경 안 됨

**에러**:
```
WARNING: (7605): It is not possible to overwrite 'if_group' value in rule '92300'. The original value is retained.
```

**교훈**: `if_group`은 overwrite 불가. 원본 파일 직접 수정 필요.

---

## 오늘 파악한 rule 체인 구조

```
windows_eventchannel decoder
    ↓
61600 (Sysmon 기본, level 0)  ← 0595-win-sysmon_rules.xml
    ↓
61615 (EventID 13 분류, level 0) → sysmon_event_13 그룹 부여  ← 0595
  또는
185011 (EventID 13 분류, level 0) → sysmon_event_13 그룹 부여  ← 0330
    ↓
92300 (Run 키 필터, level 3) ← if_group: sysmon_event_13  ← 0860-sysmon_id_13.xml
    ↓
100220 (PowerShell 탐지, level 12) ← if_sid: 92300
```

**문제**: 61615/185011이 sysmon_event_13 그룹을 부여하는지, 92300이 실제로 이벤트를 잡는지 확인 불가 (모두 level 0이라 alerts에 안 나옴)

---

## 미해결 사항

- rule 100221 (`decoded_as: windows_eventchannel` 독립 rule)도 alert 미발동
- archives 도달 확인됐는데 어느 rule도 매칭 안 됨
- logtest Phase 3 결과 없음 (rule 미매칭)

---

## 내일 확인할 것

```bash
# 1. rule 로드 확인
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest -V 2>&1 | grep "100221"

# 2. analysisd 에러 확인
docker exec single-node-wazuh.manager-1 grep -i "100221\|error\|warning" /var/ossec/logs/ossec.log | tail -20

# 3. logtest에서 decoded_as 동작 여부 확인
docker exec -it single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest
# archives의 full_log 붙여넣고 Phase 3 확인

# 4. analysisd 디버그 레벨 올려서 rule 매칭 과정 추적
# ossec.conf에 <logall>yes</logall> 확인 후
# <logging><log_level>2</log_level></logging> 추가 시도
```

---

## 핵심 명령어 모음

```bash
# archives 최신 이벤트 타임스탬프 확인
docker exec single-node-wazuh.manager-1 bash -c \
  'grep -a "003" /var/ossec/logs/archives/archives.json | tail -1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[\"timestamp\"])"'

# archives에서 특정 키워드 이벤트 필드 확인
docker exec single-node-wazuh.manager-1 grep -a "키워드" /var/ossec/logs/archives/archives.json \
  | tail -1 | python3 -m json.tool | grep -E '"image"|"targetObject"|"decoder"|"eventID"'

# alerts에서 agent 003 최근 rule 확인
docker exec single-node-wazuh.manager-1 grep -a '"id":"003"' /var/ossec/logs/alerts/alerts.json \
  | tail -1 | python3 -m json.tool | grep -E '"rule"|"id"|"level"|"description"'

# 파일 권한 수정 (docker cp 후 필수)
docker exec single-node-wazuh.manager-1 chown wazuh:wazuh /var/ossec/ruleset/rules/0860-sysmon_id_13.xml
docker exec single-node-wazuh.manager-1 chmod 660 /var/ossec/ruleset/rules/0860-sysmon_id_13.xml

# rule 파일 검증
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest -V

# logtest 인터랙티브
docker exec -it single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest
```
