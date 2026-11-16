# Deploy do PyArena numa VM

Este guia descreve a instalação do PyArena numa VM da aplicação, atrás de uma VM
edge com Nginx Proxy Manager (NPM).

## Arquitetura recomendada

```text
Internet
   |
   | HTTPS :443
   v
VM edge - Nginx Proxy Manager
   |
   | HTTP privado :8080
   v
VM da aplicação - Caddy
   |
   | rede Docker interna
   v
app + PostgreSQL + runner
```

O Nginx Proxy Manager termina o HTTPS público. O Caddy continua a ser usado
como proxy interno da aplicação, encaminhando os pedidos para o serviço
FastAPI. O PostgreSQL e o runner não devem ser publicados na rede.

O serviço `proxy` do Compose publica a porta HTTP em `0.0.0.0:8080`. Isso
significa que a app fica acessível através de qualquer interface de rede ativa
da VM, incluindo uma interface dedicada à rede do Nginx Proxy Manager. Não é
necessário criar uma configuração Docker específica para cada IP.

## 1. Preparar a VM da aplicação

Instalar os requisitos:

```bash
sudo apt update
sudo apt install -y git ca-certificates openssl
```

Confirmar que Docker e Compose estão disponíveis:

```bash
docker --version
docker compose version
```

Clonar o projeto:

```bash
git clone <URL_DO_REPOSITORIO> pyarena
cd pyarena
```

## 2. Criar a configuração de produção

Criar o ficheiro local de ambiente:

```bash
cp .env.example .env
chmod 600 .env
```

Editar `.env` e preencher, no mínimo:

```env
POSTGRES_PASSWORD=PASSWORD_FORTE_DA_BASE_DE_DADOS
SESSION_SECRET=SEGREDO_LONGO_E_ALEATORIO

PUBLIC_ORIGIN=https://arena.exemplo.pt
COOKIE_SECURE=true

DOMAIN=:80
HTTP_PORT=8080
HTTPS_PORT=8443

TEACHER_USERNAME=professor
TEACHER_PASSWORD=PASSWORD_INICIAL_FORTE

WEB_CONCURRENCY=2
RUNNER_TOKEN=SEGREDO_DO_RUNNER
RUNNER_CPUS=2
```

Gerar segredos com:

```bash
openssl rand -hex 32
```

Usar valores diferentes para `POSTGRES_PASSWORD`, `SESSION_SECRET` e
`RUNNER_TOKEN`. O `.env` não deve ser commitado nem partilhado publicamente.

Em produção, `PUBLIC_ORIGIN` tem de ser o URL público completo, incluindo
`https://`. Não usar `localhost`.

## 3. Arrancar a aplicação

Na raiz do projeto:

```bash
docker compose up -d --build
```

O arranque executa automaticamente:

- as migrações Alembic;
- o bootstrap da conta inicial do professor;
- o carregamento inicial dos problemas;
- a aplicação FastAPI;
- o proxy Caddy;
- o PostgreSQL;
- o runner isolado.

Verificar os serviços:

```bash
docker compose ps
```

Verificar a aplicação:

```bash
curl -i http://127.0.0.1:8080/api/health
curl -i http://127.0.0.1:8080/api/ready
```

Ambos devem responder com HTTP `200`.

Consultar logs:

```bash
docker compose logs --tail=100 app
docker compose logs --tail=100 proxy
docker compose logs --tail=100 runner
```

## 4. Firewall da VM da aplicação

Apenas a VM edge deve conseguir aceder à porta publicada pelo Caddy. Por
exemplo, se a VM edge tiver o IP `192.168.1.20`:

```bash
sudo ufw allow from 192.168.1.20 to any port 8080 proto tcp
```

Não publicar na Internet as portas:

- `5432` — PostgreSQL;
- `8000` — FastAPI;
- `9000` — runner;
- `8443` — HTTPS direto do Caddy, neste cenário.

O endereço esperado pela VM edge é:

```text
http://IP_PRIVADO_DA_VM_APP:8080
```

Substituir `IP_PRIVADO_DA_VM_APP` pelo endereço real da VM da aplicação.
Por exemplo, se a interface dedicada tiver o endereço `192.168.1.37`, usar:

```text
http://192.168.1.37:8080
```

Confirmar o endereço na VM da aplicação antes de o entregar ao administrador:

```bash
ip -br addr
```

ou:

```bash
hostname -I
```

Se a aplicação for aberta diretamente pelo IP, em vez do domínio público, esse
IP também tem de estar incluído em `PUBLIC_ORIGIN`. Por exemplo:

```env
PUBLIC_ORIGIN=http://192.168.1.37:8080,https://arena.exemplo.pt
COOKIE_SECURE=false
```

Use `COOKIE_SECURE=false` apenas quando o acesso direto ao IP for HTTP. Para o
acesso normal através do domínio HTTPS, mantenha `COOKIE_SECURE=true` e use o
domínio público como origem principal.

## 5. Configurar o Nginx Proxy Manager

No NPM, criar um **Proxy Host** com:

```text
Domain Names: arena.exemplo.pt
Scheme: http
Forward Hostname/IP: IP_PRIVADO_DA_VM_APP
Forward Port: 8080
```

Ativar:

- **Websockets Support**;
- **Block Common Exploits**.

No separador **SSL**:

1. pedir um novo certificado Let's Encrypt;
2. selecionar `arena.exemplo.pt`;
3. ativar **Force SSL**;
4. guardar a configuração.

O DNS do domínio deve apontar para o endereço público da VM edge:

```text
A  arena.exemplo.pt  ->  IP_PUBLICO_DA_VM_EDGE
```

O NPM deve encaminhar os cabeçalhos `Host`, `X-Real-IP`,
`X-Forwarded-For` e `X-Forwarded-Proto`. A opção de WebSocket é obrigatória
para torneios, rankings e atualizações em tempo real.

## 6. Informação para o administrador da VM edge

Enviar estes dados ao administrador:

```text
Domínio: arena.exemplo.pt
Upstream: http://IP_PRIVADO_DA_VM_APP:8080
WebSocket: ativo
SSL: certificado Let's Encrypt no Nginx Proxy Manager
Force SSL: ativo
```

A VM edge deve ter conectividade TCP para a porta `8080` da VM da aplicação.
Não é necessário acesso externo às portas da base de dados, FastAPI ou runner.

## 7. Testes após a publicação

De um computador externo:

```bash
curl -I https://arena.exemplo.pt
curl -i https://arena.exemplo.pt/api/health
curl -i https://arena.exemplo.pt/api/ready
```

Confirmar no browser:

1. a página abre com HTTPS válido;
2. o login funciona;
3. o registo de aluno aceita apenas emails `@ipt.pt`;
4. o perfil mostra o score;
5. um torneio abre corretamente;
6. o projetor recebe atualizações;
7. o WebSocket não apresenta erros na consola;
8. uma submissão de código funciona;
9. a sessão usa cookies `Secure` e `HttpOnly`.

Se houver problemas:

```bash
docker compose logs --tail=200 proxy
docker compose logs --tail=200 app
docker compose logs --tail=200 runner
```

## 8. Backups

O volume Docker `pgdata` mantém os dados entre reinícios, mas não substitui
backups. Criar um backup manual:

```bash
mkdir -p backups
docker compose exec -T db \
  pg_dump -U pyarena -d pyarena \
  | gzip > "backups/pyarena-$(date +%Y%m%d-%H%M%S).sql.gz"
```

Copiar os backups para outro disco ou servidor. Um backup guardado apenas na
mesma VM não protege contra a perda da VM.

## 9. Atualizar a aplicação

Antes de atualizar, criar um backup da base de dados. Depois:

```bash
cd pyarena
git pull
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 app
```

As migrações são executadas pelo script
[`backend/serve.sh`](../backend/serve.sh) através de `alembic upgrade head`.

## Resumo

| Componente | Localização | Responsabilidade |
|---|---|---|
| Nginx Proxy Manager | VM edge | Domínio público, HTTPS e certificado |
| Caddy | VM da aplicação | Proxy interno e cabeçalhos de segurança |
| FastAPI/Gunicorn | Docker | Backend e frontend |
| PostgreSQL | Docker, rede interna | Dados da aplicação |
| Runner | Docker, rede isolada | Execução segura do código dos alunos |
