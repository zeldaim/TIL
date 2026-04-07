# \# 📝 TIL: Wazuh Agent 설치 및 주요 설정 분석 (Windows/Ubuntu)

# 

# \## 🕒 일시

# \* \*\*날짜:\*\* 2026년 4월 7일

# \* \*\*학습 내용:\*\* Wazuh 아키텍처 이해 및 에이전트 배포/설정 실습

# 

# \---

# 

# \## 🛠 1. 실습 중 발생한 트러블슈팅 (Troubleshooting)

# 

# \### ❌ 문제 1: 설치 파일 경로 인식 불가

# \* \*\*현상:\*\* `cd /lab` 실행 시 `No such file or directory` 에러 발생.

# \* \*\*원인:\*\* 환경에 따라 실습 파일이 위치한 경로가 가이드와 상이함.

# \* \*\*해결:\*\* `ls -R` 또는 `find` 명령어로 실제 위치 확인 후 이동하거나, `/lab` 디렉토리를 생성하여 파일 이동 후 진행.

# 

# \### ❌ 문제 2: 에이전트 서비스 실행 실패 (Dead/Failed)

# \* \*\*현상:\*\* `systemctl restart wazuh-agent` 실행 시 에러 코드와 함께 서비스 구동 실패.

# \* \*\*원인:\*\* `ossec.conf` 설정 파일 내 XML 태그 오타 발생.

# &#x20;   \* `angent\_name` (오타) ➡️ `agent\_name` (정상)

# \* \*\*분석:\*\* XML 기반 설정은 대소문자와 태그 매칭에 매우 민감함. `journalctl -xeu`를 통해 구문 오류(Invalid XML)임을 확인하고 수정함.

# 

# 

# 

# \---

# 

# \## 🔍 2. ossec.conf 핵심 설정 분석

# 

# Wazuh 에이전트의 동작을 결정하는 `ossec.conf`의 주요 블록을 분석하였습니다.

# 

# \### 📡 서버 연결 (`<client>`)

# \* \*\*역할:\*\* 에이전트가 보고할 서버(Manager)의 정보를 설정합니다.

# \* \*\*설정값:\*\* `192.168.1.100` (서버 IP), `1514` (통신 포트).

# 

# \### 📥 로그 버퍼링 (`<client\_buffer>`)

# \* \*\*역할:\*\* 네트워크 장애 시 로그 유실을 방지합니다.

# \* \*\*설정값:\*\* `queue\_size` 5000개, `event\_per\_second` 500개로 제한하여 서버 과부하를 방지합니다.

# 

# \### 📂 로그 수집 (`<localfile>`)

# \* \*\*역할:\*\* 수집할 시스템 로그의 경로와 종류를 지정합니다.

# \* \*\*Windows 기준:\*\* Application, Security, System 로그를 수집하며, `<query>` 태그로 불필요한 이벤트 ID를 필터링하여 효율성을 높입니다.

# 

# \### 🛡 무결성 감시 (`<syscheck>`)

# \* \*\*역할:\*\* FIM(File Integrity Monitoring) 기능을 통해 파일/레지스트리 변경을 감시합니다.

# \* \*\*설정값:\*\* 12시간(`43200s`) 주기로 검사하며, `realtime="yes"` 옵션으로 실시간 감시를 수행합니다.

# 

# \---

# 

# \## 💡 오늘의 회고

# 설정 파일의 'n' 하나 때문에 서비스가 죽는 과정을 겪으며, 보안 솔루션 운영에서 \*\*'정확한 설정'\*\*과 \*\*'로그 분석 능력'\*\*이 얼마나 중요한지 체감할 수 있었습니다. 단순 설치를 넘어 각 설정 태그가 시스템 자원(Buffer)과 보안 탐지 범위(FIM, Filter)에 어떤 영향을 주는지 이해하는 계기가 되었습니다.

# 

# \---

# 

# \### 🔗 관련 자료

# \* \[Wazuh 공식 문서](https://documentation.wazuh.com)

# \* \[Wazuh Agent Configuration 가이드](https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/index.html)

# 

# 

# 

# 

