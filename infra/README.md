# Infra Prep

Esta pasta prepara a proxima camada estrutural da PinkBlue Vet sem alterar o
runtime atual do Lab Monitor no Railway.

## O que existe aqui

- `docker-compose.dev.yml`
  - Postgres local para a futura trilha de persistencia
  - n8n local para explorar orquestracao sem depender de VPS
- `env/dev.env.example`
  - perfil de desenvolvimento local
- `env/prod.env.example`
  - checklist de variaveis e contratos esperados em producao

## O que esta pasta NAO faz

- nao substitui o deploy atual no Railway
- nao liga banco no app atual automaticamente
- nao cria staging
- nao provisiona Oracle ou Hetzner

## Uso recomendado agora

1. Subir Postgres local para preparar a trilha `PBCORE-14` / `PBCORE-15`
2. Subir n8n local para validar a linha `PBINC-16` sem comprometer producao
3. Separar variaveis por perfil antes de qualquer introducao de banco ou IA

## Comando base

Use um arquivo real de ambiente derivado de `env/dev.env.example` e rode:

```powershell
docker compose -f infra/docker-compose.dev.yml --env-file infra/env/dev.env up -d
```

Para derrubar:

```powershell
docker compose -f infra/docker-compose.dev.yml --env-file infra/env/dev.env down
```

## Diretriz de arquitetura

- `Railway` continua sendo o runtime do produto
- `Railway Postgres` e o primeiro banco oficial recomendado
- `Docker Compose` aqui existe para desenvolvimento e exploracao
- `Oracle Free Tier` ou `Hetzner` so entram quando a automacao persistente sair
  da fase local/PR environment
