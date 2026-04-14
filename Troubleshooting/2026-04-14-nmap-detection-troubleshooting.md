# Troubleshooting — Nmap 탐지 구현 과정

Wazuh + iptables 기반 Nmap 포트스캔 탐지 구현 중 발생한 문제와 해결 과정 기록

---

## 시도 1 — Wazuh 기본 룰 활용 (실패)

### 시도

Wazuh 기본 sshd 룰(if_sid: 5706, 5710)을 이용해 Nmap 스캔 탐지 시도

### 문제

Nmap SYN 스캔(`-sS`)은 TCP 연결을 완성하지 않으므로 sshd가 로그를 남기지 않는다.  
`/var/log/secure`에 아무런 기록이 없어 Wazuh 룰이 트리거되지 않음.

### 결론

sshd 기반 탐지는 완전한 TCP 연결이 이루어진 경우에만 유효. SYN 스캔 탐지는 패킷 레벨에서 접근해야 함.

---

## 시도 2 — iptables 패킷 레벨 로깅 (성공)

### 시도

```bash
sudo iptables -I INPUT -p tcp --tcp-flags SYN,ACK,FIN,RST RST \
  -m limit --limit 1/s \
  -j LOG --log-prefix "PORTSCAN: "
```

### 결과

`/var/log/messages`에 PORTSCAN 로그 생성 성공 ✅

```
Apr 14 14:25:20 localhost kernel: PORTSCAN: IN=ens160 SRC=192.168.190.130 ...
```

---

## 시도 3 — Wazuh 에이전트 /var/log/messages 수집 설정

### 문제 1: log_format 오류

**증상:** Wazuh가 파일을 읽지 못함  
**원인:** `ossec.conf`의 `log_format`이 `journald`로 설정되어 있어 일반 파일 읽기 불가  
**해결:** `log_format`을 `syslog`로 변경

```xml
<!-- 수정 전 -->
<log_format>journald</log_format>

<!-- 수정 후 -->
<log_format>syslog</log_format>
<location>/var/log/secure</location>
```

### 문제 2: /var/log/secure 권한

**증상:** Wazuh Agent가 파일 읽기 실패  
**원인:** `/var/log/secure` 권한이 `root`만 읽기 가능(`-rw-------`)  
**해결:**
```bash
sudo chmod 644 /var/log/secure
```

### 문제 3: ossec.conf XML 구조 오류

**증상:** Wazuh Agent 시작 실패  
**원인:** `<ossec_config>` 태그가 중복으로 삽입되어 XML 파싱 오류  
**해결:** ossec.conf 전체를 올바른 구조로 새로 작성

---

## 시도 4 — rsyslog 설정 변경

### 문제

kern 로그(iptables PORTSCAN)가 `/var/log/secure`에 기록되지 않음

### 원인

기본 rsyslog 설정이 `imjournal` 모듈을 사용하며, kern 로그가 `/var/log/secure`로 라우팅되지 않도록 구성되어 있음

### 해결

```
imjournal → imklog 모듈로 변경
kern.* 을 /var/log/secure에도 기록하도록 추가
```

```bash
sudo systemctl restart rsyslog
```

**결과:** `/var/log/secure`에 PORTSCAN 로그 정상 기록 ✅

---

## 시도 5 — Wazuh logtest 룰 매칭 실패

### 문제

logtest 실행 시 Rule 100004가 아닌 Rule 4100만 매칭됨

```
Rule 4100 (Firewall rules grouped, level 0) matched
→ Rule 100004 not triggered
```

### 원인

Wazuh 룰 엔진은 계층 구조로 동작한다.  
커스텀 룰 100004에 부모 룰 지정이 없으면 4100이 매칭된 후 100004가 실행되지 않음.

### 해결

`local_rules.xml`의 100004 룰에 `<if_sid>4100</if_sid>` 추가하여 4100의 자식 룰로 동작하도록 수정

```xml
<!-- 수정 전 -->
<rule id="100004" level="10">
  <match>PORTSCAN</match>
  ...
</rule>

<!-- 수정 후 -->
<rule id="100004" level="10">
  <if_sid>4100</if_sid>   <!-- 부모 룰 지정 -->
  <match>PORTSCAN</match>
  ...
</rule>
```

**결과:** Rule 4100 → Rule 100004 순으로 정상 매칭 ✅

---

## 시도 6 — local_rules.xml 쓰기 권한 오류

### 문제 1: 일반 사용자로 직접 쓰기 시도

```
bash: /var/ossec/etc/rules/local_rules.xml: 허가 거부
```

**원인:** `/var/ossec/`는 wazuh 소유. sudo만으로는 리다이렉션(`>`)이 현재 사용자 권한으로 실행됨  
**해결:** `sudo bash -c '...'`로 서브쉘 전체를 sudo 권한으로 실행

```bash
# 틀린 방법
sudo cat > /var/ossec/etc/rules/local_rules.xml << EOF ...

# 올바른 방법
sudo bash -c 'cat > /var/ossec/etc/rules/local_rules.xml << EOF ... EOF'
```

### 문제 2: 경로 없음 오류

```
bash: /var/ossec/etc/rules/local_rules.xml: 그런 파일이나 디렉터리가 없습니다
```

**원인:** Wazuh가 Docker 컨테이너로 실행 중이므로 `/var/ossec/`는 호스트가 아닌 컨테이너 내부에 존재  
**해결:** `docker exec`로 컨테이너 내부에서 직접 실행

```bash
docker exec -it single-node-wazuh.manager-1 bash -c 'cat > /var/ossec/etc/rules/local_rules.xml << EOF
...
EOF'
```

---

## 잔여 이슈

| 이슈 | 상태 | 내용 |
|---|---|---|
| Rule 100001 중복 | 미해결 (Minor) | logtest 경고 발생, 기능 영향 없음. local_rules.xml에서 중복 제거 필요 |
| iptables 영구 적용 | 미적용 | 현재 재부팅 시 초기화됨. `iptables-save` 또는 `firewalld` 설정 필요 |
