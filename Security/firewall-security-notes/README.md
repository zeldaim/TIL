# 🔥 firewall-security-lab

> 방화벽 보안 실습 기반의 Suricata IPS 룰, ModSecurity WAF 룰, Wazuh 탐지 룰 컬렉션  
> OPNSense + Wazuh 홈 SOC 랩 연계 실습 결과물

---

## 📁 레포 구조

```
firewall-security-lab/
│
├── README.md
│
├── rules/
│   ├── suricata/
│   │   └── malicious.rules          # Suricata 악성패턴 탐지 룰
│   │
│   ├── modsecurity/
│   │   └── tortix_waf.conf          # ModSecurity WAF 커스텀 룰
│   │
│   └── wazuh/
│       └── opnsense_waf_rules.xml   # Wazuh OPNSense/WAF 탐지 룰
│
└── notes/
    └── README.md                    # 강좌 정리 노트 (학습 목적)
```

---

## 🛡️ 룰 파일 설명

### 1. Suricata IPS 룰 (`rules/suricata/malicious.rules`)

OPNSense의 Suricata IPS 플러그인에 적용하는 커스텀 룰셋.

| SID | 탐지 대상 | 모드 | MITRE ATT&CK |
|-----|----------|------|-------------|
| 1 | IE 브라우저 익스플로잇 (RIFF/ACON/anih) | alert | T1203 |
| 2 | 악성코드 패턴 MALSIG1 | alert | - |
| 3 | 악성코드 변종 MALSIG2 | **drop** | - |
| 4 | 웹 셸 업로드 시도 | alert | T1505.003 |
| 5 | SQL Injection 시도 | alert | T1190 |
| 6 | 디렉토리 트래버설 시도 | alert | T1083 |
| 7 | 민감 파일 접근 시도 (.env, .git 등) | alert | T1083 |

**적용 방법:**
```bash
# OPNSense에서 커스텀 룰 메타데이터 등록
# /usr/local/opnsense/scripts/suricata/metadata/rules/customrules.xml

# Desktop_Win10에서 HFS로 malicious.rules 공유 후
# Services → Intrusion Detection → Download → customrules/Malicious 체크
# → Download & Update Rules
```

---

### 2. ModSecurity WAF 룰 (`rules/modsecurity/tortix_waf.conf`)

Apache ModSecurity 모듈에 적용하는 커스텀 WAF 룰셋.

| Rule ID | 탐지 대상 | 변수 | 액션 |
|---------|----------|------|------|
| 1001 | 위험 HTTP 메서드 (PUT/DELETE/TRACE) | REQUEST_METHOD | deny 405 |
| 2001 | 셸코드 패턴 (`^shell.`) | ARGS | deny + redirect |
| 2002 | SQL Injection | ARGS | deny + redirect |
| 2003 | XSS | ARGS | deny + redirect |
| 3001 | URI 정규식 변형 패턴 (`patt+ern`) | REQUEST_URI | deny + redirect |
| 3002 | 어드민 페이지 접근 | REQUEST_URI | deny + redirect |
| 3003 | 민감 파일 접근 (.env, .git 등) | REQUEST_URI | deny + redirect |
| 3004 | 웹 셸 파일 접근 | REQUEST_URI | deny + redirect |
| 3005 | 디렉토리 트래버설 (`../`) | REQUEST_URI | deny + redirect |

**적용 방법:**
```bash
# CentOS5 환경
cp tortix_waf.conf /etc/httpd/modsecurity.d/
chmod 644 /etc/httpd/modsecurity.d/tortix_waf.conf
chown root:root /etc/httpd/modsecurity.d/tortix_waf.conf
service httpd restart

# 로그 확인
tail -f /var/log/httpd/modsec_audit.log
```

---

### 3. Wazuh 탐지 룰 (`rules/wazuh/opnsense_waf_rules.xml`)

OPNSense 방화벽 로그와 ModSecurity WAF 로그를 Wazuh SIEM에서 탐지하는 룰셋.

#### OPNSense 방화벽 룰 (Rule ID: 100001~100007)

| Rule ID | 탐지 대상 | Level | MITRE ATT&CK |
|---------|----------|-------|-------------|
| 100001 | 방화벽 패킷 차단 이벤트 | 6 | - |
| 100002 | 포트 스캔 의심 (60초 내 10회 차단) | 10 | T1046 |
| 100003 | SSH 브루트포스 의심 (30초 내 5회) | 12 | T1110 |
| 100004 | Suricata IPS Alert | 8 | - |
| 100005 | Suricata IPS 트래픽 차단 | 12 | T1071 |
| 100006 | 내부 IP 외부 노출 (NAT 미설정) | 9 | - |
| 100007 | 방화벽 설정 변경 감지 | 10 | T1562.004 |

#### ModSecurity WAF 룰 (Rule ID: 200001~200007)

| Rule ID | 탐지 대상 | Level | MITRE ATT&CK |
|---------|----------|-------|-------------|
| 200001 | WAF 이벤트 기본 탐지 | 6 | - |
| 200002 | SQL Injection | 10 | T1190 |
| 200003 | XSS | 10 | T1059.007 |
| 200004 | 셸코드 탐지 | 12 | T1059 |
| 200005 | 어드민 페이지 접근 차단 | 8 | T1078 |
| 200006 | 웹 셸 접근 차단 | 14 | T1505.003 |
| 200007 | 동일 IP 반복 공격 (60초 내 5회) | 14 | - |

**적용 방법:**
```bash
# Wazuh Manager에서
cp opnsense_waf_rules.xml /var/ossec/etc/rules/
chown wazuh:wazuh /var/ossec/etc/rules/opnsense_waf_rules.xml

# 룰 검증
/var/ossec/bin/wazuh-logtest

# Wazuh Manager 재시작
systemctl restart wazuh-manager
```

---

## 🏗️ 실습 환경

```
[WAN Network: 192.168.10.0/24]
  Attacker_Kali(10.10)  WAS01_CentOS5(10.20)  WAS02_CentOS4(10.30)  WAS03_Ubuntu10(10.40)
                                  │
                         OPNSense_FreeBSD
                         WAN: 192.168.10.1  ← Suricata IPS
                         LAN: 192.168.20.1
                                  │
[LAN Network: 192.168.20.0/24]
  Desktop_Win10(20.10)  WazuhSrv(20.x)
```

| VM | IP | 역할 |
|----|----|------|
| Attacker_Kali | 192.168.10.10 | 공격자 시스템 |
| WAS01_CentOS5 | 192.168.10.20 | 웹서버 + ModSecurity WAF |
| OPNSense_FreeBSD | 10.1 / 20.1 | 방화벽 + Suricata IPS |
| Desktop_Win10 | 192.168.20.10 | 관리용 단말 |

---

## 🔗 관련 프로젝트

| 프로젝트 | 설명 |
|---------|------|
| [wazuh-slack-alertbot](https://github.com/zeldaim/wazuh-slack-alertbot) | Wazuh 알람 Slack 연동 + SSH 브루트포스 엔트로피 탐지 |
| [lab-attack-runner](https://github.com/zeldaim/lab-attack-runner) | 공격 자동화 + OPNSense 로그 수집 + Flask 대시보드 |
| [home-soc-lab](https://github.com/zeldaim/home-soc-lab) | 홈 SOC 랩 전체 구성 문서 |

---

## 📚 참고

- [Suricata Rule Documentation](https://docs.suricata.io/en/latest/rules/)
- [ModSecurity Reference Manual](https://github.com/SpiderLabs/ModSecurity/wiki/Reference-Manual)
- [Wazuh Custom Rules](https://documentation.wazuh.com/current/user-manual/ruleset/custom.html)
- [MITRE ATT&CK](https://attack.mitre.org/)

---

## 👤 Author

**zeldaim**  
Blue Team / SOC Analyst 취업 준비 중  
OT/ICS 보안 장기 목표 | 수정체 공급망 경력 기반  
Substack: [Signal & Threat](https://zeldaim.substack.com)
