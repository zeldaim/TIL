\# Docker Volume Mount 오류



\## 오류 메시지

mount src=wazuh.indexer.yml not a directory



\## 원인

curl로 docker-compose.yml만 받으면

참조하는 설정파일 자리에 빈 디렉토리 생성



\## 해결

curl 대신 git clone으로 전체 프로젝트 받기



\## 배운 것

\- curl은 단일 파일만 받음

\- git clone은 전체 프로젝트 구조를 받음

\- docker volume prune으로 찌꺼기 볼륨 삭제 가능

