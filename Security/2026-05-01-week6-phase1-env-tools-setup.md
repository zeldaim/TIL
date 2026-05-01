# Week 6 Phase 1 진행 기록 — 2026-05-01

## 목표
Red team 시나리오 체이닝 준비 — 환경 점검 및 툴 셋업

---

## 1. Wazuh/ELK 서비스 상태 확인

### 확인 명령어
```bash
# 컨테이너 상태
docker ps

# Wazuh Indexer 응답 확인
curl -k -u "admin:PASSWORD" https://localhost:9200

# Wazuh Dashboard 응답 확인
curl -kv https://localhost:443
```

### 결과
| 서비스 | 포트 | 상태 |
|--------|------|------|
| Wazuh Indexer | 9200 | ✅ 정상 (200 OK) |
| Wazuh Dashboard | 443 | ✅ 정상 (302 → /app/login) |
| Kibana | 5601 | ✅ 정상 (443으로 포워딩) |

### 탐지 룰 무결성 확인
```bash
docker exec single-node-wazuh.manager-1 cat /var/ossec/etc/rules/local_rules.xml
```

- `local_rules.xml` → placeholder로 덮어씌워진 상태 발견
- `local_rules.xml.bak` → 5주차 룰 백업 확인
- `.bak`으로 복구 후 wazuh-control restart

### 복구된 룰 목록
| Rule ID | 기법 | 설명 |
|---------|------|------|
| 100001 | T1110 | SSH Brute Force Attack Detected |
| 100004 | T1046 | Nmap port scan detected via iptables |
| 100005 | T1190 | SQL Injection attempt detected |
| 100006 | T1190 | SQL Injection Brute Attack (5회/60초) |

### 미완성 룰
- T1547 (Persistence) — FIM 방식으로 탐지 성공했으나 Rule 방식 미완성 → Week 6에서 완성 예정

### FIM 상태 확인
```bash
docker exec single-node-wazuh.manager-1 cat /var/ossec/etc/ossec.conf | grep -A 10 "syscheck"
```
- `frequency: 43200` (12시간) — 기본값으로 원복된 상태
- 용량 문제로 인해 테스트 시 변경 예정

---

## 2. ATT&CK Navigator 로컬 배포

### 설치
```bash
# Node.js 설치 (Rocky Linux 9)
sudo dnf module reset nodejs -y
sudo dnf module enable nodejs:18 -y
sudo dnf install nodejs -y

# ATT&CK Navigator 클론 및 실행
git clone https://github.com/mitre-attack/attack-navigator.git
cd attack-navigator/nav-app
npm install
npm run start
```

### 접속
```
http://192.168.190.128:4200
```

### Week 6 레이어 파일 생성
- 파일명: `navigator-week6.json`
- 포함 기법:

| ATT&CK ID | 기법명 | 단계 |
|-----------|--------|------|
| T1046 | Network Service Discovery | Reconnaissance |
| T1190 | Exploit Public-Facing Application | Initial Access |
| T1110 | Brute Force | Credential Access |
| T1547 | Boot or Logon Autostart Execution | Persistence |
| T1055 | Process Injection | Privilege Escalation |
| T1059 | Command and Scripting Interpreter | Execution |

---

## 3. Metasploit 업데이트 및 DB 연결

### 설치 및 실행
```bash
# Kali Linux에서
sudo apt update && sudo apt install metasploit-framework
sudo msfdb init
msfconsole
```

### Week 6 워크스페이스 설정
```bash
workspace -a week6
db_status
# → Connected to msf. Connection type: postgresql.
```

---

## Phase 1 완료 체크리스트
- [x] Wazuh/ELK 서비스 상태 확인
- [x] 탐지 룰 무결성 확인 및 복구
- [x] ATT&CK Navigator 로컬 배포
- [x] Week 6 레이어 파일 생성 (navigator-week6.json)
- [x] Metasploit 업데이트 및 DB 연결
- [x] week6 워크스페이스 생성

---

## 이슈 및 메모
- VM 디스크 풀(0바이트) → .vmem 삭제 + 스냅샷 정리로 32GB 확보
- Wazuh Indexer curl 접속 오류 → HTTPS + 올바른 비밀번호로 해결
- Node.js v16 → v18로 업그레이드 필요했음 (Angular CLI 요구사항)
- T1547 룰 미완성 → Phase 2에서 Sysmon EventID 13 룰 작성 예정

## 다음 단계 (Phase 2)
- T1046 → T1190 체이닝 (Nmap → SQLi → Meterpreter)
- T1110 → T1021 체이닝 (Brute Force → 횡적이동)
- T1547 Sysmon EventID 13 룰 완성
