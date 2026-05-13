#!/bin/bash

YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Finalizando o ambiente Docker...${NC}\n"

sudo docker compose -f Docker-compose.yml logs -f backend db redis | tee log.txt

echo -e "${YELLOW}Ctrl + C para continuar...${NC}\n"

sudo docker compose -f Docker-compose.yml down

echo -e "${YELLOW}Containers dockers em atividade...${NC}\n"

sudo docker ps -a
