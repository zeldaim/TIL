# 2026-04-20 Wazuh 알럿 로그 초기화

> Wazuh SIEM 기반 Home SOC Lab  
> Kibana 대시보드 데이터 완전 초기화 기록

---

## 문제

Wazuh 로그 파일을 초기화했음에도 Kibana 대시보드에 이전 알럿 데이터가 그대로 남아있었다.

---

## 원인

Wazuh 로그 파일(`alerts.log`, `alerts.json`)과 Kibana에 표시되는 데이터는 별개다.  
Kibana는 **Elasticsearch(Wazuh Indexer) 인덱스**에서 데이터를 읽기 때문에  
로그 파일만 지워서는 대시보드가 초기화되지 않는다.

```
alerts.log / alerts.json  ← Wazuh 로그 파일 (지워도 Kibana엔 영향 없음)
Elasticsearch 인덱스       ← Kibana가 실제로 읽는 곳 (여기를 지워야 함)
```

---

## 해결 과정

### Step 1 — Wazuh 로그 파일 초기화

```bash
sudo docker exec -it single-node-wazuh.manager-1 bash
> /var/ossec/logs/alerts/alerts.log
> /var/ossec/logs/alerts/alerts.json
exit
sudo docker restart single-node-wazuh.manager-1
```

### Step 2 — Elasticsearch 인덱스 삭제

컨테이너 목록 및 포트 확인:

```bash
sudo docker ps --format "table {{.Names}}\t{{.Ports}}"
# single-node-wazuh.indexer-1  0.0.0.0:9200->9200/tcp
```

Elasticsearch 비밀번호 확인:

```bash
grep -i password /home/yhc/wazuh-docker/single-node/docker-compose.yml
# INDEXER_PASSWORD=SecretPassword
```

인덱스 삭제:

```bash
curl -X DELETE "https://localhost:9200/wazuh-alerts-*" \
  -u admin:SecretPassword \
  -k
# {"acknowledged":true}
```

### Step 3 — Kibana 새로고침

Kibana 대시보드 우측 상단 **Refresh** 버튼 클릭 → 데이터 초기화 확인 ✓

---

## 정리

| 항목 | 명령어 |
|------|--------|
| Wazuh 로그 파일 초기화 | `> /var/ossec/logs/alerts/alerts.log` |
| Elasticsearch 인덱스 삭제 | `curl -X DELETE "https://localhost:9200/wazuh-alerts-*" -u admin:PASSWORD -k` |
| 컨테이너 재시작 | `sudo docker restart single-node-wazuh.manager-1` |
