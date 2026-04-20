# 2026-04-20 Week 3 — 트러블슈팅

> Wazuh SIEM 기반 Home SOC Lab  
> Rule Chaining 구현 중 발생한 문제 및 해결 기록

---

## 트러블슈팅 1 — 100001 미발동 (frequency/timeframe 덮어쓰기 문제)

### 문제
Kali에서 SSH 브루트포스 공격 후 Kibana 대시보드(Wazuh Threat Hunting)에서  
100001이 잡히지 않고 Wazuh 기본 룰 5763만 발동.

### 원인 파악

**1단계 — Wazuh 기본 룰 5763 조건 확인**
```bash
grep -r "5763" /var/ossec/ruleset/rules/
# → <rule id="5763" level="10" frequency="8" timeframe="120" ignore="60">
```

5763은 120초 내 8회 조건. 100001(60초 내 5회)보다 느슨하므로  
100001이 정상이라면 먼저 발동해야 했다.

**2단계 — 100001 룰 직접 확인**
```bash
grep -r "100001" /var/ossec/etc/rules/local_rules.xml
# → <rule id="100001" level="5">
```

frequency/timeframe 없음. 이전 작업 시 특정 IP(1.1.1.1) 단순 탐지 룰로  
덮어써진 상태였고 chaining 조건 자체가 빠져 있었다.

**3단계 — 전체 파일 확인**
```bash
cat /var/ossec/etc/rules/local_rules.xml
```

100001이 아래와 같이 잘못 저장돼 있었다.
```xml
<rule id="100001" level="5">
  <if_sid>5716</if_sid>
  <srcip>1.1.1.1</srcip>
  <description>sshd: authentication failed from IP 1.1.1.1.</description>
</rule>
```

### 해결
local_rules.xml 전체 재작성.

```bash
sudo docker exec -it single-node-wazuh.manager-1 bash
cat > /var/ossec/etc/rules/local_rules.xml << 'EOF'
# 올바른 룰 내용 작성
EOF
exit
sudo docker restart single-node-wazuh.manager-1
```

### 검증
Kibana 대시보드(Wazuh Threat Hunting)에서 `rule.id: 100001` 검색  
→ level 10 알럿 정상 확인 ✓

---

## 트러블슈팅 2 — SQLi curl 요청 미전달 (URL 특수문자 문제)

### 문제
curl 명령어 실행 시 요청이 서버에 도달하지 않아 100005/100006 미발동.  
Kibana Level 12 or above alerts 카운터가 0에서 변화 없음.

### 원인 파악

**1차 시도 — 대괄호 오류**
```bash
curl "http://[192.168.190.128]/index.php?id=1' union select 1,2,3--"
# curl: (3) bad range in URL position 12
```
IP를 대괄호로 감싸면 curl이 IPv6 주소 범위로 해석해 요청 자체를 거부한다.

**2차 시도 — 특수문자 미인코딩**
```bash
curl "http://192.168.190.128/index.php?id=1' union select 1,2,3--"
# curl: (3) URL rejected: Malformed input to a URL function
```
작은따옴표 `'` 와 공백은 URL에서 허용되지 않는 특수문자.  
인코딩 없이 그대로 넣으면 curl이 거부한다.

### 해결
URL 인코딩 적용.

```bash
for i in {1..10}; do
  curl "http://192.168.190.128/index.php?id=1%27%20union%20select%201,2,3--"
  sleep 2
done
```

| 특수문자 | URL 인코딩 |
|---------|-----------|
| `'` (작은따옴표) | `%27` |
| 공백 | `%20` |
| `;` | `%3B` |

### 검증
Kibana 대시보드(Wazuh Threat Hunting)에서 `rule.id: 100006` 검색  
→ level 12 알럿 2건 확인 ✓  
→ Level 12 or above alerts 카운터 0 → 2 변경 확인 ✓
