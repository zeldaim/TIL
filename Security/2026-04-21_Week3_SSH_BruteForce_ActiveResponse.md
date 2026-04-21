# TIL: Wazuh SSH Brute Force 탐지 + Active Response (Week 3)

**날짜:** 2026-04-21  
**환경:** VMware Workstation Pro / Rocky Linux 9 (Agent) / Kali Linux (Attacker) / Wazuh 4.9.0 (Docker)  
**MITRE ATT&CK:** T1110 (Brute Force)

---

## 구현 목표

Kali Linux에서 SSH Brute Force 공격 시 Wazuh가 자동으로 탐지하고, iptables로 공격자 IP를 차단하는 Active Response 파이프라인 구축.

---

## 최종 구성

```
Kali (공격자) → SSH Brute Force → Rocky Linux
                                      ↓
                              Wazuh Agent (001)
                                      ↓
                          Wazuh Manager (Docker)
                                      ↓
                        Rule 100002 트리거 (5회/60초)
                                      ↓
                     Active Response → firewall-drop
                                      ↓
                     iptables DROP (192.168.190.130)
```

---

## 핵심 설정

### 1. local_rules.xml (매니저 컨테이너)

```xml
<group name="local,syslog,sshd,">

  <rule id="100001" level="0">
    <description>Dummy rule to bypass empty group error</description>
  </rule>

  <rule id="100002" level="10" frequency="5" timeframe="60">
    <if_matched_sid>5760</if_matched_sid>
    <same_source_ip />
    <description>SSH Brute Force: 60초 내 동일 IP에서 5회 이상 실패 (T1110)</description>
    <mitre>
      <id>T1110</id>
    </mitre>
    <group>authentication_failures,attack,</group>
  </rule>

</group>
```

### 2. ossec.conf Active Response 설정 (매니저 컨테이너)

```xml
<active-response>
  <command>firewall-drop</command>
  <location>defined-agent</location>
  <agent_id>001</agent_id>
  <rules_id>100001,100002,100006</rules_id>
  <timeout>60</timeout>
</active-response>
```

> **주의:** `<agent_id>`는 Rocky Linux 에이전트 ID여야 함. `agent_control -l`로 확인.

### 3. firewall-drop 스크립트 (Rocky Linux 에이전트)

경로: `/var/ossec/active-response/bin/firewall-drop`

```bash
#!/bin/bash
read STDIN_DATA
SRCIP=$(echo "$STDIN_DATA" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d['parameters']['alert']['data']['srcip'])
" 2>/dev/null)

COMMAND=$(echo "$STDIN_DATA" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('command',''))
" 2>/dev/null)

if [ "$COMMAND" = "add" ] && [ -n "$SRCIP" ]; then
    iptables -I INPUT -s "$SRCIP" -j DROP
    echo "$(date) Blocked $SRCIP" >> /var/ossec/logs/active-responses.log
elif [ "$COMMAND" = "delete" ] && [ -n "$SRCIP" ]; then
    iptables -D INPUT -s "$SRCIP" -j DROP
    echo "$(date) Unblocked $SRCIP" >> /var/ossec/logs/active-responses.log
fi
```

```bash
sudo chmod 750 /var/ossec/active-response/bin/firewall-drop
sudo chown root:wazuh /var/ossec/active-response/bin/firewall-drop
```

---

## 트러블슈팅 기록 (삽질 모음)

### 문제 1: Rule 100001이 탐지를 안 함
- **원인:** 100001이 Dummy rule이었음 (match 조건 없음)
- **해결:** 실제 탐지 룰을 100002로 새로 작성, `same_source_ip` 추가

### 문제 2: firewall-drop 바이너리가 Rocky Linux에서 동작 안 함
- **원인:** 매니저 컨테이너용으로 컴파일된 바이너리라 에이전트 OS에서 실행 불가
- **해결:** bash 스크립트로 직접 작성하여 대체

### 문제 3: AR이 발동되지 않음 (whitelist)
- **원인:** ossec.conf의 `<white_list>^localhost.localdomain$</white_list>` 때문에 Rocky Linux 에이전트 발 alert이 AR에서 제외됨
- **해결:** whitelist에서 `localhost.localdomain` 항목 제거

### 문제 4: AR이 엉뚱한 에이전트로 전송됨
- **원인:** Agent 001 (Rocky Linux)과 Agent 002 (Kali Linux)가 모두 등록되어 있었고, ossec.conf에 잘못된 agent_id 설정
- **확인 방법:** `agent_control -l` 로 에이전트 목록 확인, `client.keys` 로 에이전트 자신의 ID 확인
- **해결:** ossec.conf `<agent_id>`를 Rocky Linux의 실제 ID(001)로 수정

### 문제 5: firewall-drop 스크립트가 IP를 파싱 못 함
- **원인:** Wazuh 4.x는 AR 스크립트에 인자(args)가 아닌 **stdin으로 JSON**을 전달함
- **JSON 구조:**
```json
{
  "command": "add",
  "parameters": {
    "alert": {
      "data": {
        "srcip": "192.168.190.130"
      }
    }
  }
}
```
- **해결:** `read STDIN_DATA` 후 python3으로 JSON 파싱하여 srcip 추출

---

## 검증 방법

```bash
# 1. Rule 100002 트리거 확인
docker exec single-node-wazuh.manager-1 \
  grep -c "100002" /var/ossec/logs/alerts/alerts.log

# 2. AR 로그 확인
sudo tail -f /var/ossec/logs/active-responses.log

# 3. iptables 차단 확인
sudo iptables -L INPUT -n | grep 192.168.190.130
```

---

## 포트폴리오 핵심 포인트

- Wazuh 4.x의 AR JSON 전달 방식을 직접 디버깅하여 파악
- `agent_control -b <IP> -f <AR명> -u <agent_id>` 로 수동 AR 테스트 가능
- firewall-drop은 에이전트에 직접 배포해야 하며, 매니저 바이너리와 다름
- Rocky Linux 선택 이유: RHEL 계열 실서버 환경과 동일한 구성
