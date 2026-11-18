#!/usr/bin/env bash
# Confere que as customizações do fork D3S continuam no lugar.
#
# Um merge do upstream (4devsmart/wrapper-api) pode desfazer uma delas SEM dar
# conflito: foi assim que o push na main saiu dos gatilhos do CI e o deploy na
# Kronn parou de existir sem erro nenhum. Este script transforma cada uma dessas
# regressões em falha do CI. Não usa rede. Ver docs/FORK.md.
set -euo pipefail
cd "$(dirname "$0")/../.."

falhas=0
exigir() { # arquivo regex motivo
  if ! grep -Eq -- "$2" "$1" 2>/dev/null; then
    echo "FALTA em $1: $3" >&2
    falhas=$((falhas + 1))
  fi
}
proibir() { # arquivo regex motivo
  if grep -Eq -- "$2" "$1" 2>/dev/null; then
    echo "SOBROU em $1: $3" >&2
    falhas=$((falhas + 1))
  fi
}

# --- deploy contínuo na Kronn ---------------------------------------------
# Só o bloco "push:" do "on:" conta: o pull_request também lista a main, e uma
# regex no arquivo inteiro aceitaria aquela linha.
push_branches=$(awk '/^on:/{on=1;next} on&&/^[^ ]/{on=0} on&&/^  push:/{p=1;next} on&&/^  [a-z_]+:/{p=0} p&&/^    branches:/{print}' .github/workflows/ci.yml)
if ! printf '%s\n' "$push_branches" | grep -Eq '\bmain\b'; then
  echo "FALTA em .github/workflows/ci.yml: o push na main precisa disparar o CI: é ele que publica e implanta" >&2
  falhas=$((falhas + 1))
fi
exigir .github/workflows/ci.yml 'uses: \./\.github/workflows/publicar\.yml' \
  'o job publicar do CI chama o publicar.yml'
exigir .github/workflows/ci.yml 'KRONN_DEPLOY_HOOK: \$\{\{ secrets\.KRONN_DEPLOY_HOOK \}\}' \
  'o CI repassa o secret do deploy hook ao publicar.yml'
exigir .github/workflows/ci.yml "cancel-in-progress: \\$\\{\\{ github\\.ref != 'refs/heads/main' \\}\\}" \
  'na main o CI não cancela a execução anterior (cortaria um deploy no meio)'
exigir .github/workflows/publicar.yml '^  workflow_call:' \
  'o publicar.yml só roda chamado pelo CI, depois dos gates'
exigir .github/workflows/publicar.yml 'name: implanta na Kronn' \
  'o publicar.yml chama o deploy hook da Kronn'
proibir .github/workflows/publicar.yml '^concurrency:' \
  'concurrency no topo do publicar.yml disputa o grupo com o job que o chama'
exigir .github/workflows/release.yml '^    tags: \["v\*"\]' \
  'o release do fork é pela tag, não pelo push na main'
exigir .workflow.conf '^DEPLOY_WORKFLOW="ci\.yml"' \
  'o make ship acompanha o ci.yml, que é quem implanta'
exigir .workflow.conf '^RELEASE_BUILD_WORKFLOW=""' \
  'o fork não builda no push de release/vX.Y.Z'

# --- libs da ACBr com os patches do fork -----------------------------------
exigir Makefile '^ACBR_REPO \?= cpereiraweb/wrapper-api$' \
  'as libs saem do release deste repositório'
exigir Makefile '^export ACBR_REPO$' \
  'os scripts de libs leem ACBR_REPO do ambiente'
exigir Makefile '^ACBR_LIBS_RELEASE \?= acbrlib-r[0-9]+-d3s[0-9]+$' \
  'o release das libs é o do fork (sufixo -d3sN)'
[ -s docker/acbr-patches/0006-danfse-padraonacional-layout-adn.patch ] || {
  echo "FALTA docker/acbr-patches/0006-danfse-padraonacional-layout-adn.patch" >&2
  falhas=$((falhas + 1))
}

# --- DANFSe ------------------------------------------------------------------
exigir Dockerfile 'COPY --chmod=0644 docker/logo-nfse\.jpg /opt/acbr/logo-nfse\.jpg' \
  'a logo da NFS-e entra na imagem'
exigir Dockerfile 'docker/fontconfig/30-microsoft-sans-serif\.conf' \
  'o alias da Microsoft Sans Serif entra na imagem'
exigir Dockerfile '^        ghostscript \\$' \
  'o gs embute as fontes nos PDFs'
exigir Dockerfile 'COPY --chmod=0755 docker/entrypoint\.sh' \
  'o entrypoint não depende do umask de quem builda'
exigir internal/acbr/acbr_cgo.go 'configDANFSe\(logoNFSe\)' \
  'a sessão de NFS-e liga a logo e o canhoto'
exigir cmd/fiscal-worker/main.go 'acbr\.OpcoesDoWorker\(cfg\.ACBr\)' \
  'o worker liga o embutidor de fontes'

# --- prazo de parada na Kronn ----------------------------------------------
# O compose da Kronn tem de esperar mais que o encerramento do serviço
# (ACBR_WORKER_TIMEOUT_SECONDS + margem), senão um deploy corta uma transmissão.
timeout=$(sed -nE 's/.*envInt\("ACBR_WORKER_TIMEOUT_SECONDS", ([0-9]+)\).*/\1/p' internal/platform/config/config.go | head -1)
margem=$(sed -nE 's/^const margemDeEncerramento = ([0-9]+) \* time\.Second$/\1/p' internal/platform/config/config.go | head -1)
if [ -z "$timeout" ] || [ -z "$margem" ]; then
  echo "não achei o timeout do worker ou a margem de encerramento em config.go" >&2
  falhas=$((falhas + 1))
else
  prazo=$((timeout + margem))
  for g in $(sed -nE 's/^ *stop_grace_period: ([0-9]+)s$/\1/p' deploy/kronn/docker-compose.yml); do
    if [ "$g" -le "$prazo" ]; then
      echo "deploy/kronn/docker-compose.yml: stop_grace_period ${g}s <= encerramento ${prazo}s" >&2
      falhas=$((falhas + 1))
    fi
  done
fi

if [ "$falhas" -gt 0 ]; then
  echo "$falhas customização(ões) do fork fora do lugar. Ver docs/FORK.md." >&2
  exit 1
fi
echo "fork D3S: customizações no lugar"
