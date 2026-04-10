\# 2026-04-10 Home SOC Lab 진행 현황



\## ✅ 완료된 것



\### 환경 구성

\- Rocky Linux 9 (관제서버) 192.168.190.128

\- Kali Linux (공격자) 192.168.190.130

\- ELK Stack (Elasticsearch 9201, Kibana 5601, Logstash 5044)

\- Wazuh 4.9.0 (Dashboard 443, Indexer 9200, Manager 1514)



\### 보안 탐지

\- Kali → Rocky Linux SSH 브루트포스 공격

\- Wazuh에서 실시간 탐지 확인

\- MITRE ATT\&CK T1110 (Password Guessing) 룰 작성



\### 로그 연동

\- Wazuh alerts.json → Filebeat → Logstash → Elasticsearch

\- Kibana에서 Wazuh 보안 로그 시각화



\### SOC Security Dashboard

\- 차트 1: 시간별 보안 이벤트 수

\- 차트 2: 공격자 IP별 공격 횟수 (192.168.190.130)

\- 차트 3: 탐지 룰별 이벤트 분석



\## 🔧 트러블슈팅



\### ELK 9200 포트 충돌

\- 원인: Wazuh Indexer가 9200 사용

\- 해결: ELK Elasticsearch 포트를 9201로 변경



\### Logstash → Elasticsearch 연결 실패

\- 원인: 컨테이너 안에서 localhost로 접속 시도

\- 해결: hosts를 elasticsearch:9200으로 변경



\### Filebeat 크래시

\- 원인: 버전 호환성 문제

\- 해결: curl로 직접 Elasticsearch에 데이터 삽입



\### Wazuh alerts.json 경로 문제

\- 원인: 파일이 Docker 컨테이너 안에 있음

\- 해결: docker cp로 호스트로 복사 후 Filebeat로 전송



\## ⏭️ 다음 단계

\- Windows VM 설치

\- Sysmon 설치

\- Windows Wazuh 에이전트 연동

\- Terraform 인프라 코드화

