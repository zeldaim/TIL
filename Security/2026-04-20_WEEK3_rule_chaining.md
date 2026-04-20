# 2026-04-20 Week 3 — Rule Chaining (탐지 고도화)

> Wazuh SIEM 기반 Home SOC Lab  
> 단일 이벤트 탐지 → 행동 패턴 탐지로 레벨업

---

## 개요

| 항목 | 내용 |
|------|------|
| 목표 | Rule Chaining으로 공격 패턴 탐지 구현 |
| 환경 | VMware / Rocky Linux 9 / Kali Linux / Wazuh 4.9.0 / ELK Stack |
| 완료 룰 | 100001 (SSH BF chaining) / 100006 (SQLi chaining) |
| MITRE | T1110 (Brute Force) / T1190 (Exploit Public-Facing Application) |

---

## Rule Chaining 개념

단일 탐지를 하면 이벤트 1건마다 알럿이 발생해 노이즈가 너무 많아진다.  
Rule Chaining은 여러 단순 이벤트를 묶어 하나의 의미있는 공격 패턴으로 판정하는 것이다.

```
단순 탐지  : SSH 로그인 실패 1회 → 알럿 (오탐 多)
패턴 탐지  : 같은 IP, 60초 내 5회 실패 → 알럿 (공격 패턴만 탐지)
```

### 룰 구조

```
참조 룰 (Wazuh 기본 내장) — 로그 파싱 후 발동  ← 감지기
      ↓ if_matched_sid로 참조
커스텀 룰 — 횟수/시간 조건 충족 시 알럿 발동  ← 판정기
```

| 태그 | 역할 |
|------|------|
| `if_sid` | 해당 룰이 발동됐을 때 단순 트리거 |
| `if_matched_sid` | 같은 조건(IP 등)으로 N회 반복됐을 때 트리거 |
| `frequency` | 발동 횟수 임계값 |
| `timeframe` | 카운팅 시간 범위 (초) |
| `same_source_ip` | 동일 출발지 IP만 카운팅 |

---

## 최종 local_rules.xml

```xml
<group name="local,syslog,sshd,">
  <rule id="100001" level="10" frequency="5" timeframe="60">
    <if_matched_sid>5760</if_matched_sid>
    <same_source_ip />
    <description>SSH Brute Force Attack Detected - MITRE T1110</description>
    <mitre>
      <id>T1110</id>
    </mitre>
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

<group name="web,sqli,">
  <rule id="100005" level="10">
    <if_sid>31103</if_sid>
    <url>union|select|insert|drop|delete|update|cast|exec|declare|--|%27|%3B</url>
    <description>SQL Injection attempt detected</description>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>
  <rule id="100006" level="12" frequency="5" timeframe="60">
    <if_matched_sid>100005</if_matched_sid>
    <same_source_ip />
    <description>SQL Injection Brute Attack - 5 attempts in 60s - MITRE T1190</description>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>
</group>
```

---

## 룰 현황

| 룰 ID | 참조 룰 | 탐지 내용 | MITRE | 유형 |
|-------|---------|----------|-------|------|
| 100001 | if_matched_sid: 5760 | SSH BF, 60초 내 5회 | T1110 | chaining |
| 100004 | if_sid: 4100 | Nmap 포트스캔 | T1046 | 단일 탐지 |
| 100005 | if_sid: 31103 | SQL Injection URL 패턴 | T1190 | 단일 탐지 |
| 100006 | if_matched_sid: 100005 | SQLi 60초 내 5회 | T1190 | chaining |

---

## 탐지 흐름

### SSH 브루트포스 (T1110)

```
Kali → SSH 로그인 실패 반복
      ↓
5760  sshd: authentication failed (level 5) — 개별 실패마다 기록
      ↓ 같은 IP, 60초 내 5회 누적
100001 SSH Brute Force Attack Detected (level 10) ✓
```

### SQL Injection 패턴 (T1190)

```
Kali → curl로 SQLi 페이로드 전송
      ↓
31103 Apache 웹 요청 로그 감지
      ↓
100005 URL에 union|select 등 키워드 매칭 (level 10)
      ↓ 같은 IP, 60초 내 5회 누적
100006 SQL Injection Brute Attack (level 12) ✓
```

---

## 공격 시뮬레이션

### SSH 브루트포스 (Kali)

```bash
hydra -l root -P /usr/share/wordlists/rockyou.txt ssh://192.168.190.128
```

### SQL Injection (Kali)

```bash
for i in {1..10}; do
  curl "http://192.168.190.128/index.php?id=1%27%20union%20select%201,2,3--"
  sleep 2
done
```

### Kibana 대시보드(Wazuh Threat Hunting) 검증

```
rule.id: 100001   → SSH BF chaining 알럿 확인
rule.id: 100006   → SQLi chaining 알럿 확인
rule.level: 12    → 고위험 알럿 필터
```

---

## 결과 확인

| 룰 ID | 레벨 | 상태 | Kibana 확인 |
|-------|------|------|------------|
| 100001 | 10 | ✅ 정상 발동 | rule.id: 100001 알럿 확인 |
| 100006 | 12 | ✅ 정상 발동 | Level 12 알럿 2건 확인 |
