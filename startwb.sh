#!/bin/bash

# --- Configurações de Cores ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Iniciando configuração do ambiente...${NC}\n"

# --- Passo 1: Copiar arquivos .env ---
echo -e "Passo 1: Copiando arquivos de ambiente..."
cp -n backend/.env.example backend/.env 2>/dev/null
cp -n frontend/.env.example frontend/.env.local 2>/dev/null

# --- Passo 2: Gerar Secrets ---
echo -e "Passo 2: Gerando chaves secretas..."
# Gerar chaves
BACKEND_KEY=$(openssl rand -hex 32)
FRONTEND_KEY=$(openssl rand -hex 32)

# Atualizar ou adicionar as chaves nos arquivos
# Usando sed para substituir se existir ou append se não existir
if grep -q "DJANGO_SECRET_KEY" backend/.env; then
    sed -i "s/^DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$BACKEND_KEY/" backend/.env
else
    echo "DJANGO_SECRET_KEY=$BACKEND_KEY" >> backend/.env
fi

if grep -q "AUTH_SECRET" frontend/.env.local; then
    sed -i "s/^AUTH_SECRET=.*/AUTH_SECRET=$FRONTEND_KEY/" frontend/.env.local
else
    echo "AUTH_SECRET=$FRONTEND_KEY" >> frontend/.env.local
fi

# --- Passo 3: Validar Docker ---
echo -e "Passo 3: Validando serviço Docker..."
if [ "$(systemctl is-active docker)" != "active" ]; then
    echo -e "${YELLOW}Docker inativo. Tentando iniciar...${NC}"
    sudo systemctl start docker
fi

# --- Passo 4: Docker Compose Build ---
echo -e "Passo 4: Reiniciando containers..."
sudo docker compose -f docker-compose.yml down -v
sudo docker compose -f docker-compose.yml up --build -d

# --- Passo 5: Migrations ---
echo -e "Passo 5: Executando migrações do banco de dados..."
sudo docker compose -f docker-compose.yml exec \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  backend python manage.py migrate

# --- Passo 6: Validar Status ---
echo -e "\nPasso 6: Status dos containers:"
sudo docker compose -f docker-compose.yml ps

# --- Passo 7: Testes ---
echo -e "\n---"
read -p "Deseja executar os testes com Pytest agora? (s/N): " confirm
if [[ "$confirm" =~ ^[sS]$ ]]; then
    echo -e "${YELLOW}Executando testes...${NC}"
    sudo docker exec -it backend. pytest -v
else
    echo -e "${GREEN}Setup finalizado sem testes.${NC}"
fi

echo -e "\n${GREEN}Pronto! O ambiente deve estar rodando.${NC}"
