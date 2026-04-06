\# Wazuh 4.9.0 설치 (Docker)



\## 환경

\- Rocky Linux 9

\- Docker CE

\- Wazuh 4.9.0



\## 설치 명령어

git clone https://github.com/wazuh/wazuh-docker.git -b v4.9.0

cd wazuh-docker/single-node

docker compose -f generate-indexer-certs.yml run --rm generator

docker compose up -d



\## 배운 것

\- curl로 yml만 받으면 설정파일 누락으로 오류 발생

\- git clone으로 전체 프로젝트 받아야 함

\- 인증서 생성 단계를 반드시 먼저 해야 함

\- 기본 로그인: admin / SecretPassword

