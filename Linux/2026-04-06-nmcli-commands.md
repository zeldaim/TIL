# nmcli 명령어

\# nmcli 주요 명령어



\## 네트워크 상태 확인

nmcli connection show

ip addr show



\## 네트워크 연결

sudo nmcli connection up ens160



\## IP 자동 할당 설정

sudo nmcli connection modify ens160 ipv4.method auto



\## 재부팅 후 자동 연결

sudo nmcli connection modify ens160 connection.autoconnect yes



\## 배운 것

\- Rocky Linux는 NetworkManager로 네트워크 관리

\- nmcli가 주요 명령어 도구

