# 🔥 방화벽 보안 강좌 정리

> 방화벽 개념부터 OPNSense 실습, IPS/WAF 실습까지 정리한 보안 학습 노트.  
> 홈 SOC 랩(OPNSense + Wazuh) 연계 실습 포인트 포함.

---

## 📚 목차

### Part 1. 방화벽 이론
- [1-1. 방화벽 개요](#1-1-방화벽-개요)
- [1-2. 방화벽 작동 방식](#1-2-방화벽-작동-방식)
- [1-3. 네트워크 배치 및 도입 고려사항](#1-3-네트워크-배치-및-도입-고려사항)

### Part 2. OPNSense 실습 환경
- [2-1. 실습 네트워크 구성](#2-1-실습-네트워크-구성)
- [2-2. 기본 통신 확인](#2-2-기본-통신-확인)

### Part 3. OPNSense 실습 시나리오
- [3-1. Outbound NAT를 활용한 내부 네트워크 은닉](#3-1-outbound-nat를-활용한-내부-네트워크-은닉)
- [3-2. 포트 주소 기반 접근통제](#3-2-포트-주소-기반-접근통제)
- [3-3. IPS 플러그인(Suricata)을 이용한 유해패턴 탐지](#3-3-ips-플러그인suricata을-이용한-유해패턴-탐지)

### Part 4. ModSecurity WAF
- [4-1. WAF 개요 및 ModSecurity 개념](#4-1-waf-개요-및-modsecurity-개념)
- [4-2. 실습 환경 및 설정 파일 구조](#4-2-실습-환경-및-설정-파일-구조)
- [4-3. 룰셋 문법 — ARGS & REQUEST_URI 실습](#4-3-룰셋-문법--args--request_uri-실습)

---

## Part 1. 방화벽 이론

### 1-1. 방화벽 개요

**정의:** 네트워크 사이의 경계에 위치하여 허가되지 않은 접근으로부터 보호대상 네트워크를 보호하는 보안 솔루션

#### 세대별 역사

| 세대 | 이름 | 특징 |
|------|------|------|
| 1세대 | 패킷 필터링 방화벽 | IP주소, 포트, 프로토콜 헤더 기반 트래픽 제어 |
| 2세대 | 상태 기반 방화벽 | 연결 상태 테이블로 활성 세션 추적 → 무작위 패킷 차단 |
| 3세대 | 애플리케이션 계층 방화벽 | 네트워크 + 애플리케이션 계층까지 검사. 앱 프로토콜 취약점 공격 차단 |
| 4세대 | 차세대 방화벽 (NGFW) | IPS, 앱 인식, 사용자 신원 관리, 위협 인텔리전스 연동 |

#### 구현 방식별 종류

| 종류 | 사용 환경 | 구현 방식 |
|------|----------|----------|
| 하드웨어 방화벽 | 고성능·고가용성 필요 기업 | 전용 어플라이언스 (Cisco, Fortinet, Palo Alto) |
| 소프트웨어 방화벽 | 호스트 단위 / 소규모 환경 | Windows Defender, iptables / OPNSense, pfSense |
| 클라우드 방화벽 | 클라우드 인프라 보호 | 가상 네트워크 보안, WAAS |

> 💡 **홈랩 연계:** OPNSense = 소프트웨어 방화벽(가상 어플라이언스). 범용 CPU 처리라 하드웨어 방화벽 대비 처리량 한계 존재.

---

### 1-2. 방화벽 작동 방식

패킷이 지나갈 때 여러 단계 검사 메커니즘을 통해 허용/차단을 결정. 각 작동방식은 **동시에** 이루어진다.

| 작동방식 | 내용 |
|---------|------|
| 패킷 필터링 | 소/목적지 IP, 포트, 프로토콜 기반 의사결정 |
| 상태기반 검사 | 연결 상태 테이블 유지 → 패킷 상태 추적 |
| 심층 패킷 검사 (DPI) | 응용계층 패킷 내용 분석 후 의사결정 |
| 프록시 기반 필터링 | 클라이언트-서버 사이 중재자 역할 |

**패킷 필터링 검사 범위:**
```
이더넷 헤더 → IP 헤더 → TCP/UDP 헤더 → 응용계층 헤더 → 페이로드
```

#### 방화벽 vs IPS vs WAF 비교

| 구분 | 판단 기준 | 대상 계층 |
|------|----------|----------|
| 방화벽 | IP, 포트, 프로토콜 (헤더) | 네트워크 계층 |
| IPS | 패킷 페이로드 시그니처 | 네트워크/전송 계층 |
| WAF | HTTP 요청/응답 내용 | 애플리케이션 계층 (L7) |

---

### 1-3. 네트워크 배치 및 도입 고려사항

```
외부 네트워크
      │
   [방화벽]
   ┌───┴────────────┐
DMZ 네트워크    [방화벽]
(외부/내부       ┌────┴────┐
접속 가능)  내부 네트워크  격리 네트워크
           (외부통신 가능) (내부만 접근)
```

| 고려사항 | 내용 |
|---------|------|
| 성능과 보안의 균형 | DPI, 암호화 트래픽 검사는 성능 저하 유발 → Throughput 평가 필수 |
| 확장성 | 향후 3~5년 트래픽 증가량 예측, 클러스터링 지원 여부 |
| 관리 용이성 | 중앙 집중식 콘솔, 정책 템플릿 일괄 관리, 로깅 기능 |
| 다른 보안솔루션과의 통합 | SIEM, EDR/XDR, SOAR 연동 / 개방형 API 지원 |
| TCO(총소유비용) 분석 | 초기 구매, 라이선스, 유지보수, 운영인력, 전력·공간 비용 |

---

## Part 2. OPNSense 실습 환경

### 2-1. 실습 네트워크 구성

```
[WAN Network: 192.168.10.0/24]
  Attacker_Kali   WAS01_CentOS5   WAS02_CentOS4   WAS03_Ubuntu10
  .10.10          .10.20          .10.30          .10.40
                        │
               OPNSense_FreeBSD
               WAN: 192.168.10.1
               LAN: 192.168.20.1
                        │
[LAN Network: 192.168.20.0/24]
  Desktop_Win10
  .20.10
```

| 가상머신 | IP | 용도 |
|---------|-----|------|
| Attacker_Kali | 192.168.10.10 | 공격자 시스템 |
| WAS01_CentOS5 | 192.168.10.20 | 웹 서버 #1 |
| WAS02_CentOS4 | 192.168.10.30 | 웹 서버 #2 |
| WAS03_Ubuntu10 | 192.168.10.40 | 웹 서버 #3 |
| OPNSense_FreeBSD | 192.168.10.1 / 192.168.20.1 | 방화벽 (NIC 2개) |
| Desktop_Win10 | 192.168.20.10 | 방화벽 관리용 단말 |

---

### 2-2. 기본 통신 확인

**공격자 → 방화벽 PING (Attacker_Kali)**
```bash
ping 192.168.10.1
# 결과: 100% packet loss → 방화벽이 ICMP 응답 차단 (ping sweep 방지)

arp -an
# ARP 캐시에는 방화벽 MAC 주소 존재 → NIC는 살아있음
```

**내부 → 외부 통신 (Desktop_Win10)**
```cmd
ping -n 1 192.168.10.10   # TTL=63 (방화벽 한 홉 경유)
ping -n 1 192.168.20.1    # TTL=64 (방화벽 LAN 직접)
```
> TTL이 1 감소 = 방화벽(게이트웨이) 한 홉 경유. 패킷 경로 추적에 활용.

---

## Part 3. OPNSense 실습 시나리오

### 3-1. Outbound NAT를 활용한 내부 네트워크 은닉

#### 핵심 개념

| 구분 | 역할 | 핵심 질문 |
|------|------|----------|
| 방화벽 필터링 (Stateful) | 패킷 허용/차단 | "이 패킷을 통과시킬까?" |
| NAT 엔진 | 주소 변환 | "출발지 IP를 뭐로 바꿀까?" |

> ⚠️ NAT와 방화벽 필터링은 **완전히 독립적**으로 동작. NAT가 없어도 패킷은 통과하지만 내부 IP가 노출됨.

```
[NAT 정상]   Desktop(192.168.20.10) → 방화벽 변환 → 외부: 192.168.10.1
[NAT 초기화] Desktop(192.168.20.10) → 변환 없음  → 외부: 192.168.20.10 노출!
```

#### OPNSense Outbound NAT 설정

**경로:** `Firewall → NAT → Outbound` → Manual 모드 선택

| 항목 | 값 |
|------|-----|
| Interface | WAN |
| Protocol | any |
| Source address | LAN net |
| Translation / target | **WAN address** |

#### PF 처리 순서 (FreeBSD)
```
패킷 수신 → 정규화 → NAT(nat-to) → 필터링(block/pass) → 라우팅
```
> NAT가 필터링보다 **먼저** 처리됨.

```bash
# pfctl로 NAT 룰 확인
pfctl -sn
# NAT 적용 후:
# nat on em1 inet from (em0:network) to any -> (em1:0) port 1024:65535
```

#### 결과 비교 (Wireshark)

| 구분 | Source IP |
|------|-----------|
| NAT 설정 전 | 192.168.20.10 (내부 IP 노출) |
| NAT 설정 후 | 192.168.10.1 (방화벽 WAN IP) |

---

### 3-2. 포트 주소 기반 접근통제

**시나리오:** 악성코드 유포 사이트(192.168.10.20)로의 일반 접근은 차단하되, SSH 원격 관제는 허용

#### 적용 룰 (순서 중요!)

```
✅ 올바른 순서:
1. Pass  | LAN | TCP | LAN Net → 192.168.10.20:22 (SSH 허용)
2. Block | LAN |     | LAN Net → 192.168.10.20    (전체 차단)
3. Pass  | LAN |     | LAN Net → *               (기본 허용)
```

> ⚠️ OPNSense는 **first-match** 방식. SSH 허용 룰이 Block 룰보다 위에 있어야 함.

#### 결과 확인

```cmd
# Desktop_Win10
# 브라우저 접속 → 차단
# SSH 접속 → 성공
ssh root@192.168.10.20   # password: lab
```

로그 확인: `Firewall → Log Files → Live View`

---

### 3-3. IPS 플러그인(Suricata)을 이용한 유해패턴 탐지

#### Suricata 설정

**경로:** `Services → Intrusion Detection → Administration`

| 설정 | 값 |
|------|-----|
| Enabled | ✅ |
| IPS mode | ✅ (탐지 + 차단) |
| Interfaces | LAN |
| Pattern matcher | Hyperscan |

#### malicious.rules 룰 문법

```
# alert 모드 — 탐지만, 차단 안 함
alert tcp any any -> any any (msg:"Malicious file pattern test1"; sid:2;
flow:to_client,established; file_data; content:"MALSIG1"; depth:16;)

# drop 모드 — 탐지 + 차단
alert tcp any any -> any any (msg:"Malicious file pattern test2"; sid:3;
flow:to_client,established; file_data; content:"MALSIG2"; depth:16;)
```

| 필드 | 의미 |
|------|------|
| `flow:to_client,established` | 서버→클라이언트, 세션 수립된 트래픽만 |
| `file_data` | HTTP 응답 바디(파일 내용) 검사 |
| `content` | 탐지할 패턴 문자열 |
| `depth:16` | 파일 시작 16바이트 이내 탐색 |

#### alert vs drop 차이

| 모드 | 동작 | 클라이언트 결과 |
|------|------|----------------|
| `alert` | 탐지 + 로그 | 파일 다운로드 **성공** |
| `drop` | 탐지 + 차단 + 로그 | 파일 다운로드 **실패** |

로그 확인: `Services → Intrusion Detection → Alerts`

---

## Part 4. ModSecurity WAF

### 4-1. WAF 개요 및 ModSecurity 개념

**WAF(Web Application Firewall):** HTTP/HTTPS 요청과 응답의 내용을 분석하여 웹 애플리케이션 계층(L7)의 공격을 탐지·차단하는 보안 시스템.

**ModSecurity:** Apache, Nginx, IIS에 모듈 형태로 탑재되는 오픈소스 WAF.

#### Process Phases (처리 단계)

| Phase | 단계 | 설명 |
|-------|------|------|
| 1 | Request Headers | 요청 메서드, URL, Host, 쿠키 파싱 |
| 2 | Request Body | POST 본문, 파일 업로드 파싱 |
| 3 | Response Headers | HTTP 상태코드, 캐시 제어 파싱 |
| 4 | Response Body | 응답 본문 분석 |
| 5 | Logging | 룰 적용 결과 기록 |

#### 주요 지시자

| 지시자 | 옵션 | 설명 |
|--------|------|------|
| `SecRuleEngine` | On / Off / DetectOnly | WAF 기능 활성화 여부 |
| `SecAuditEngine` | On / Off / RelevantOnly | 감사 로그 제어 |
| `SecDefaultAction` | deny, allow, redirect, phase, log... | 룰 매칭 시 기본 동작 |

```apache
# 예시
SecDefaultAction "phase:1,deny,log,auditlog,status:403"
SecDefaultAction "phase:1,deny,log,auditlog,status:403,t:lowercase,t:urlDecodeUni,t:htmlEntityDecode"
```

---

### 4-2. 실습 환경 및 설정 파일 구조

| 파일 | 경로 | 역할 |
|------|------|------|
| 룰 적용 파일 | `/etc/httpd/modsecurity.d/tortix_waf.conf` | 탐지 환경 구성 및 룰 패턴 작성 |
| 로그 파일 | `/var/log/httpd/modsec_audit.log` | 탐지 로그 기록 |
| 환경 설정 파일 | `/etc/httpd/conf.d/00_mod_security.conf` | Apache 모듈 메인 설정 |

#### tortix_waf.conf 주요 설정

```apache
SecAuditEngine RelevantOnly          # 매칭된 요청만 로그 기록
SecAuditLogType Serial               # 이벤트마다 고유 ID 부여
SecAuditLog logs/modsec_audit.log    # 로그 저장 경로

SecRule REQUEST_METHOD "(PUT|DELETE|TRACE)" "deny,log"  # 위험 HTTP 메서드 차단

SecRequestBodyAccess On              # 요청 본문 검사
SecResponseBodyAccess On             # 응답 본문 검사
SecResponseBodyMimeType (null) text/html text/plain text/xml
SecResponseBodyLimit 524288          # 응답 본문 최대 512KB
```

---

### 4-3. 룰셋 문법 — ARGS & REQUEST_URI 실습

#### SecRule 문법 구조

```
SecRule  VARIABLES  OPERATOR  [ACTIONS]
```

#### 주요 VARIABLES

| 변수 | 설명 |
|------|------|
| `ARGS` | GET + POST 파라미터 전체 |
| `ARGS_GET` | GET 파라미터만 |
| `ARGS_POST` | POST 파라미터만 |
| `REQUEST_URI` | 요청 URL 경로 + 쿼리 문자열 |
| `REQUEST_HEADERS` | 요청 헤더 |
| `REQUEST_METHOD` | GET, POST 등 요청 메서드 |
| `FULL_REQUEST` | HTTP 요청 전체 |

#### 주요 OPERATOR

| 연산자 | 설명 |
|--------|------|
| `@rx` | 정규식 (기본값, 생략 가능) |
| `@streq` | 문자열 일치 |
| `@contains` | 문자열 포함 |
| `@beginsWith` / `@endsWith` | 접두어/접미어 비교 |
| `@ipMatch` | IP 주소 비교 |

#### 실습 #1 — ARGS로 셸코드 탐지

```bash
# CentOS5에서 룰 추가
vi /etc/httpd/modsecurity.d/tortix_waf.conf
# 아래 룰 추가
SecRule ARGS ^shell. "id:7,redirect:/error.html"
:wq!
service httpd restart
```

```bash
# Kali에서 테스트
Firefox http://192.168.10.20/coremall
# 검색창에 'shellcode' 입력 → /error.html 리다이렉트
```

```bash
# 로그 확인
cat /var/log/httpd/modsec_audit.log | grep id[[:space:]]\"7\"
# Pattern match "^shell." at ARGS:ps_search.
```

#### 실습 #2 — REQUEST_URI로 경로 기반 탐지

```bash
# 정규식 패턴 탐지
SecRule REQUEST_URI "@rx patt+ern" "id:7,redirect:/error.html"

# 어드민 페이지 접근 차단
SecRule REQUEST_URI "admin" "msg:'Admin',redirect:/error.html"
```

```bash
# 테스트
Firefox 192.168.10.20/webhack/pattttttttttern   # → error.html
Firefox 192.168.10.20/webhack/admin.php          # → error.html
```

> 💡 `patt+ern` 정규식: `+`는 앞 문자(`t`)가 1회 이상 반복. 변형 URL 우회 공격 탐지에 활용.

---

## 🔗 홈랩 연계 포인트

| 실습 내용 | 홈랩 연계 |
|----------|----------|
| OPNSense 방화벽 로그 | Wazuh SIEM 수집 → 차단 이벤트 자동 알람 |
| Suricata IPS Alert | Wazuh로 수집 → SOC 분석가 워크플로우 구성 |
| ModSecurity WAF 로그 | Wazuh 수집 → `msg` 필드로 공격 유형 분류 |
| Outbound NAT 설계 | OT/ICS 제어망 은닉 — KEPCO/KHNP 환경 적용 원리 |

---

## 📝 보안기사 시험 대비 포인트

- 방화벽 세대별 특징 (1~4세대)
- 패킷 필터링 vs 상태기반 vs DPI 차이
- NAT(Stateful) vs 방화벽 필터링 독립성
- Suricata `alert` vs `drop` 액션 차이
- ModSecurity SecRule 문법 구조: `SecRule VARIABLES OPERATOR [ACTIONS]`
- ModSecurity Phase 1~5 처리 단계
- WAF vs IPS vs 방화벽 계층별 차이

---

> ⚠️ **Note:** 강좌 진행 중. 이후 섹션 추가 예정.
