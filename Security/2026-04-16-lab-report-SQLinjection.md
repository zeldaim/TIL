# Home SOC Lab — 2026-04-16 작업 리포트

**환경**: VMware Workstation Pro (Rocky Linux 9 + Kali Linux + Wazuh 4.9.0)

\---

## 오늘 완료한 작업

### 1\. Wazuh 커스텀 룰 재적용

`local\_rules.xml` 재적용 (docker cp 방식).

|Rule ID|설명|Level|MITRE|
|-|-|-|-|
|100001|SSH 인증 실패 (1.1.1.1)|5|-|
|100004|Nmap 포트스캔 탐지|10|T1046|
|100005|SQL 인젝션 탐지|10|T1190|

### 2\. Wazuh 에이전트 ossec.conf 수정

`/var/log/secure` 수집 설정에 `log\_format` 누락 문제 수정.

```xml
<localfile>
  <log\_format>syslog</log\_format>
  <location>/var/log/secure</location>
</localfile>
```

### 3\. Nmap 탐지 실제 검증 (Wazuh 대시보드)

Kali에서 Nmap SYN 스캔 → Wazuh 대시보드에서 Rule 100004 알럿 확인.

```
Rule 100004 - Nmap port scan detected via iptables
MITRE T1046 - Discovery / Network Service Discovery
Level 10 / Agent: localhost.localdomain (ID: 003)
```

### 4\. Apache 설치 및 SQLi 탐지 룰 구성

```bash
sudo dnf install httpd -y
sudo systemctl enable --now httpd
```

Apache 로그 수집 설정 추가:

```xml
<localfile>
  <log\_format>apache</log\_format>
  <location>/var/log/httpd/access\_log</location>
</localfile>
```

Rule 100005 작성 후 Manager 컨테이너에 배포:

```xml
<group name="web,sqli,">
  <rule id="100005" level="10">
    <if\_sid>31103</if\_sid>
    <url>union|select|insert|drop|delete|update|cast|exec|declare|--|%27|%3B</url>
    <description>SQL Injection attempt detected</description>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>
</group>
```

### 5\. SQL 인젝션 공격 시뮬레이션 및 탐지 검증

Kali에서 URL 인코딩 적용 후 공격 시뮬레이션:

```bash
curl "http://192.168.190.128/?id=1%27%20union%20select%201%2C2%2C3--"
curl "http://192.168.190.128/?id=1%27%20or%20%271%27%3D%271"
curl "http://192.168.190.128/?search=admin%27%20drop%20table%20users--"
```

탐지 결과:

```
\*\* Alert 1776308290.515188: - web,sqli,
Rule: 100005 (level 10) -> 'SQL Injection attempt detected'
MITRE T1190 - Initial Access / Exploit Public-Facing Application
```

Kibana Threat Hunting 대시보드에서 rule.id 100005, T1190 확인 완료.

\---

## 탐지 파이프라인 흐름

```
Kali curl (SQLi payload, URL encoded)
        ↓
Rocky Linux Apache access\_log
        ↓
Wazuh Agent logcollector
        ↓
Manager Rule 100005 매칭
        ↓
alerts.log + Kibana Dashboard
```

\---

## 탐지 룰 현황

|Rule ID|탐지 대상|Level|MITRE|상태|
|-|-|-|-|-|
|100001|SSH 인증 실패|5|-|✅|
|100004|Nmap 포트스캔|10|T1046|✅ 검증 완료|
|100005|SQL 인젝션|10|T1190|✅ 검증 완료|



