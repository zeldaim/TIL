# 🛡️ Home SOC Lab 3주차 완료 — Active Response 검증 & Python 로그 파싱

**날짜:** 2026-04-22  
**단계:** 3주차 — 탐지 고도화 (Rule Chaining / Active Response)  
**상태:** ✅ 완료 (SQLP 연계 → 7주차 이월)

---

## ✅ 1. Active Response 검증

### 목표
Wazuh가 공격 IP를 탐지 후 자동으로 iptables 차단하는지 end-to-end 검증

### 검증 방법
Kali(192.168.190.130)에서 SSH 브루트포스 재시도 → Rocky에서 차단 확인

### 검증 결과

```bash
# iptables DROP 규칙 등록 확인
sudo iptables -L -n | grep 192.168.190.130
DROP  all  -- 192.168.190.130  0.0.0.0/0

# active-responses.log 확인
2026/04/21 14:47:08  firewall-drop: Starting
2026/04/21 15:48:42  Blocked 192.168.190.130
```

### 동작 체인
```
Kali 공격 → Wazuh 탐지 → firewall-drop 실행 → iptables DROP 등록 → 통신 차단
```

- MITRE T1110 (SSH BF) 탐지 → Active Response 자동 발동 ✅
- timeout 300초 후 자동 해제 설정 ✅

---

## ✅ 2. Python 로그 파싱

### 목표
`alerts.json` → 공격 통계 자동 출력 스크립트 작성

### 파일
```
TIL/Security/2026-04-22_parse_alerts_3Weeks_Python파싱.py
```

### 구현 항목
| 항목 | 내용 |
|------|------|
| 공격 IP 빈도 | Top 10 |
| Rule 발동 횟수 | Top 15 (설명 포함) |
| 시간대 분포 | 0~23시 막대그래프 |
| MITRE ATT&CK | Technique별 발동 횟수 |
| 위협 레벨 | Level별 횟수 및 비율 |

### 실행 방법
```bash
# 컨테이너에서 alerts.json 추출
docker cp single-node-wazuh.manager-1:/var/ossec/logs/alerts/alerts.json ~/alerts.json

# 파싱 실행
python3 ~/TIL/Security/2026-04-22_parse_alerts_3Weeks_Python파싱.py ~/alerts.json
```

### 오늘 분석 결과 (2026-04-22 기준)

**총 이벤트: 1,716건 | 파싱 오류: 0건**

**공격 IP**
| IP | 횟수 |
|----|------|
| 192.168.190.130 (Kali) | 10회 |

> Active Response 차단 이후라 횟수 적음 — 정상

**Rule 발동 Top**
| Rule ID | 횟수 | 설명 |
|---------|------|------|
| 5502 | 571 | PAM: Login session closed |
| 5402 | 567 | Successful sudo to ROOT executed |
| 5501 | 567 | PAM: Login session opened |
| 510 | 8 | Host-based anomaly detection (rootcheck) |
| 5557 | 2 | unix_chkpwd: Password check failed |
| 5503 | 1 | PAM: User login failed |

**MITRE ATT&CK**
| Technique | 횟수 | 설명 |
|-----------|------|------|
| T1548.003 | 567 | Sudo and Sudo Caching |
| T1078 | 567 | Valid Accounts |
| T1110.001 | 3 | SSH Brute Force ✅ |

**위협 레벨 분포**
| Level | 횟수 | 비율 |
|-------|------|------|
| Lv 7 | 8 | 0.5% |
| Lv 5 | 3 | 0.2% |
| Lv 3 | 1,705 | 99.4% |

**시간대 분포**
- 02시(UTC) = 11시(KST)에 1,716건 집중 → 오늘 오전 작업 시간대 일치

---

## 🔧 3. 부수 트러블슈팅

### Rocky → GitHub 접근 불가
| 항목 | 내용 |
|------|------|
| 증상 | `Could not resolve host: github.com` |
| 원인 | `/etc/resolv.conf` 가 VMware 게이트웨이(192.168.190.2)만 바라보고 있었음. VMnet 어댑터 Not Present 상태로 DNS 쿼리가 외부로 못 나감 |
| 해결 | `echo "nameserver 8.8.8.8" \| sudo tee /etc/resolv.conf` |
| 영구 설정 | `sudo nmcli con mod ens160 ipv4.dns "8.8.8.8 8.8.4.4"` |

### Windows → Rocky scp 불가
| 항목 | 내용 |
|------|------|
| 증상 | `Connection timed out` / `Connection reset` |
| 원인 | VMnet8 어댑터 Not Present + NAT 포트포워딩 미설정 |
| 해결 | VMware NAT Settings → 포트포워딩 추가 `2222 TCP → 192.168.190.128:22` |
| 추가 | Windows 방화벽 인바운드 2222 허용 |

> 결국 파일 전송은 GitHub를 통해 해결 — Rocky에서 git clone 후 pull 방식으로 운영

### Rocky sshd PasswordAuthentication
| 항목 | 내용 |
|------|------|
| 원인 | Rocky 기본값 비활성화 |
| 해결 | `/etc/ssh/sshd_config` → `PasswordAuthentication yes` 후 `sudo systemctl restart sshd` |

---

## 📌 3주차 최종 체크리스트

- [x] Rule chaining — SSH BF 60초 내 5회 이상 `MITRE T1110`
- [x] Rule chaining — SQL Injection 5회 이상 level 12 고위험 알럿
- [x] Active Response — 공격 IP 자동 iptables 차단 (timeout 300초)
- [x] Active Response 검증 — 차단 후 Kali 재공격 시도 → 통신 차단 확인
- [x] Python 로그 파싱 — 공격 IP 빈도 / Rule별 통계 / 시간대 분포
- [ ] SQLP 연계 → **7주차로 이월**

---

## 🔜 다음 단계 — 4주차 Terraform 모듈화

- [ ] ELK 모듈 / Wazuh 모듈 분리
- [ ] AWS 이식 가능한 구조 설계 (EC2 + Security Group + VPC)
- [ ] GitHub Actions 자동 배포 파이프라인
