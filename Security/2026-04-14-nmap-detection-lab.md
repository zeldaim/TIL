# Nmap Port Scan Detection via Wazuh + iptables

## 개요

Kali Linux에서 Nmap 포트스캔 시도 시 Wazuh가 실시간으로 탐지하여 알람을 발생시키는 SOC 탐지 파이프라인 구현

**MITRE ATT&CK:** T1046 - Network Service Discovery  
**탐지 레벨:** Level 10 (Critical)

---

## 환경

| 구성 요소 | 버전 / 상세 |
|---|---|
| Wazuh Manager | 4.9.0 (Docker, single-node) |
| Rocky Linux | 9 (Wazuh Agent 설치, 탐지 대상) |
| Kali Linux | 공격자 VM |
| ELK Stack | Elasticsearch 8.x (port 9201), Kibana (5601) |

---

## 아키텍처

```
Kali Linux
  └─ nmap -sS → Rocky Linux
                  └─ iptables LOG → /var/log/secure
                                      └─ Wazuh Agent
                                            └─ Wazuh Manager (Docker)
                                                  └─ Alert (Rule 100004, Level 10)
                                                        └─ Kibana Dashboard
```

---

## 구현 단계

### 1. iptables 포트스캔 감지 룰 추가

Nmap SYN 스캔은 `/var/log/secure`에 기본적으로 기록되지 않으므로 iptables에서 패킷 레벨 로깅을 설정한다.

```bash
# Rocky Linux에서 실행
sudo iptables -I INPUT -p tcp --tcp-flags SYN,ACK,FIN,RST RST \
  -m limit --limit 1/s \
  -j LOG --log-prefix "PORTSCAN: "
```

설정 후 `/var/log/messages`에 다음과 같은 로그가 생성된다:
```
Apr 14 14:25:20 localhost kernel: PORTSCAN: IN=ens160 SRC=192.168.190.130 DST=192.168.190.128 PROTO=TCP DPT=22
```

### 2. rsyslog 설정 — kern 로그를 /var/log/secure로 라우팅

```bash
# /etc/rsyslog.conf 수정
# imjournal → imklog 모듈로 변경
# kern.* 을 /var/log/secure에도 기록

sudo systemctl restart rsyslog
```

### 3. /var/log/secure 권한 변경

Wazuh Agent가 파일을 읽을 수 있도록 권한을 조정한다.

```bash
sudo chmod 644 /var/log/secure
```

### 4. Wazuh Agent ossec.conf 수정

`/var/ossec/etc/ossec.conf`에 localfile 블록을 추가한다.

```xml
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/secure</location>
</localfile>
```

```bash
sudo systemctl restart wazuh-agent
```

### 5. Wazuh Manager 커스텀 룰 추가

```bash
docker exec -it single-node-wazuh.manager-1 bash -c 'cat > /var/ossec/etc/rules/local_rules.xml << EOF
<group name="nmap,recon,">
  <rule id="100004" level="10">
    <if_sid>4100</if_sid>
    <match>PORTSCAN</match>
    <description>Nmap port scan detected via iptables</description>
    <mitre>
      <id>T1046</id>
    </mitre>
  </rule>
</group>
EOF'
```

룰 구조 설명:
- `if_sid 4100`: Firewall/kernel 로그 그룹(부모 룰)에 매칭된 후 실행
- `match PORTSCAN`: iptables log-prefix와 매칭
- `level 10`: Critical 수준 알람

### 6. Wazuh Manager 재시작

```bash
docker exec single-node-wazuh.manager-1 /var/ossec/bin/wazuh-control restart
```

---

## 검증

### logtest로 룰 매칭 확인

```bash
docker exec -it single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest
```

테스트 로그 입력:
```
Apr 14 12:00:00 localhost kernel: PORTSCAN: IN=eth0 OUT= SRC=192.168.x.x DST=192.168.x.x PROTO=TCP
```

기대 결과:
```
**Phase 3: Completed filtering (rules).
    id: '100004'
    level: '10'
    description: 'Nmap port scan detected via iptables'
    mitre.id: ['T1046']
    mitre.tactic: ['Discovery']
**Alert to be generated.
```

### 실제 공격 시뮬레이션

```bash
# Kali Linux에서 실행
sudo nmap -sS 192.168.190.128
```

### 알람 로그 실시간 확인

```bash
docker exec single-node-wazuh.manager-1 tail -f /var/ossec/logs/alerts/alerts.log \
  | grep -i "PORTSCAN\|100004"
```

실제 탐지 결과:
```
Rule: 100004 (level 10) -> 'Nmap port scan detected via iptables'
Apr 14 14:25:20 localhost kernel: PORTSCAN: IN=ens160 SRC=192.168.190.130 DST=192.168.190.128 PROTO=TCP DPT=22
```

---

## Kibana 확인

```
https://localhost:5601
→ Wazuh → Security Events
→ 필터: rule.id: 100004
```

---

## 탐지 룰 전체 (local_rules.xml)

```xml
<group name="local,syslog,sshd,">
  <rule id="100001" level="5">
    <if_sid>5716</if_sid>
    <srcip>1.1.1.1</srcip>
    <description>sshd: authentication failed from IP 1.1.1.1.</description>
    <group>authentication_failed,pci_dss_10.2.4,pci_dss_10.2.5,</group>
  </rule>
</group>

<group name="nmap,recon,">
  <rule id="100004" level="10">
    <if_sid>4100</if_sid>
    <match>PORTSCAN</match>
    <description>Nmap port scan detected via iptables</description>
    <mitre>
      <id>T1046</id>
    </mitre>
  </rule>
</group>
```
