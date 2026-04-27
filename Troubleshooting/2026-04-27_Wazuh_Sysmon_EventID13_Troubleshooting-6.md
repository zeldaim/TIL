# 2026-04-27 Wazuh EventID 13 파이프라인 디버깅 TIL

> **날짜**: 2026-04-27
> **환경**: Rocky Linux 9 (Wazuh 4.9.0 Docker) / Windows 10 (Sysmon v15.20 + Wazuh Agent 4.9.2)
> **목표**: Sysmon EventID 13 → Wazuh alert 발동

---

## 최종 상태

| 단계 | 상태 |
|------|------|
| Sysmon EventID 13 캡처 | ✅ |
| Agent → Manager archives 전송 | ✅ |
| decoder: windows_eventchannel | ✅ |
| Rule 발동 | ❌ 미해결 |

---

## 오늘 발견한 핵심 사실들

### 1. 채팅 인터페이스가 필드명을 마크다운 링크로 변환

`win.system.channel`이 채팅에서 `[win.system.channel](http://win.system.channel)`로 렌더링됨.
실제 파일은 정상이었는데 손상된 것으로 착각해서 수정 시도하는 삽질 발생.

**교훈**: 터미널 출력을 채팅에 복사하면 마크다운 변환이 일어남. `cat -v`로 실제 파일 내용 확인 필수.

---

### 2. 60000 rule의 category>ossec가 EventChannel 이벤트와 불일치 (핵심 가설)

**60000 원본**:
```xml
<rule id="60000" level="0">
  <category>ossec</category>
  <decoded_as>windows_eventchannel</decoded_as>
  <field name="win.system.providerName">\.+</field>
</rule>
```

`category>ossec`는 Wazuh agent가 직접 생성한 이벤트에만 매칭됨. Windows EventChannel 이벤트는 외부 로그 수집이라 category가 다를 수 있음.

Wazuh 커뮤니티에서 동일 증상 보고:
- archives 도달 확인
- decoder: windows_eventchannel 확인
- 어떤 rule도 매칭 안 됨
- 해결: 60000에서 `category>ossec` 제거

**시도 결과**: 제거 후에도 alert 미발동 → 다른 원인 존재 가능성

---

### 3. logtest는 실제 파이프라인과 다름

logtest에 raw JSON을 넣으면 `json` decoder로 처리됨.
실제 agent 이벤트는 `windows_eventchannel` decoder로 처리됨.
→ logtest Phase 3 없음 = 실제 파이프라인과 무관

---

### 4. rule 체인 구조 최종 확인

```
windows_eventchannel decoder
    ↓
60000 (category:ossec + decoded_as:windows_eventchannel)  ← 0575-win-base_rules.xml
    ↓
60004 (channel: ^Microsoft-Windows-Sysmon/Operational$)   ← 0575
    ↓
61600 (severityValue: ^INFORMATION$)                      ← 0595-win-sysmon_rules.xml
    ↓
92300 (targetObject: CurrentVersion\Run, level 3)         ← 0860-sysmon_id_13.xml
    ↓
100220 (image: powershell, level 12)                      ← 0860
```

Security 체인(60001→60103→60106)은 정상 발동.
Sysmon 체인(60004→61600→92300)은 전혀 발동 안 됨.

---

### 5. wazuh-analysisd -t 로 rule 로딩 검증

```bash
docker exec single-node-wazuh.manager-1 bash -c "/var/ossec/bin/wazuh-analysisd -t 2>&1 | tail -5"
```

에러 없이 통과하면 rule 파일 문법은 정상.
에러 발생 시: `Group 'group' without any rule` = 빈 group 태그 문제.

---

## 미해결 — 내일 할 것

### Wazuh 공식 포럼에 질문

포럼: https://groups.google.com/g/wazuh
Discord: https://wazuh.com/community/

**질문 내용**:
```
Environment: Wazuh 4.9.0 Docker single-node, Windows 10 agent 4.9.2, Sysmon v15.20

Problem: Sysmon EventID 13 events arrive in archives.json with decoder 
"windows_eventchannel" confirmed, but no alert is generated. 
Rule chain 60000→60004→61600→92300 never fires for Sysmon channel events.
Security channel events (60106) work fine.

Tried:
- Removed category>ossec from rule 60000
- Overwrite 60004/61600/92300 with higher level
- Independent rule with decoded_as>windows_eventchannel
- independent rule with if_sid>60004

All failed. Archives confirmed, alerts empty.

Question: What is different between Security channel and Sysmon channel 
event processing in Wazuh 4.9.0?
```

---

## 핵심 명령어

```bash
# rule 체인 구조 파악
docker exec single-node-wazuh.manager-1 grep -rn "sysmon_event_13" /var/ossec/ruleset/rules/

# analysisd 테스트 모드
docker exec single-node-wazuh.manager-1 bash -c "/var/ossec/bin/wazuh-analysisd -t 2>&1 | tail -5"

# archives decoder 확인
docker exec single-node-wazuh.manager-1 grep -a "EvilToday" /var/ossec/logs/archives/archives.json | tail -1 | python3 -m json.tool | grep -A3 '"decoder"'

# 60000 rule 확인
docker exec single-node-wazuh.manager-1 grep -A8 'id="60000"' /var/ossec/ruleset/rules/0575-win-base_rules.xml

# Security vs Sysmon 체인 비교
# Security: 60000→60001→60103→60106 (정상)
# Sysmon:   60000→60004→61600→92300 (미발동)
```
