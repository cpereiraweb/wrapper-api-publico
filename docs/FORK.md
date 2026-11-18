# Fork D3S

Este repositório (`cpereiraweb/wrapper-api`) é um fork de
[`4devsmart/wrapper-api`](https://github.com/4devsmart/wrapper-api). As mudanças
abaixo são do fork e **não vão para o upstream**: a cada atualização dele, elas são
reaplicadas aqui.

`scripts/fork/conferir-fork.sh` (`make fork-conferir`, primeiro passo do job `test`
do CI) confere que cada uma continua no lugar. Um merge que desfizer alguma, mesmo
sem conflito, quebra o CI.

## O que o fork muda

| Área | Mudança | Onde |
|---|---|---|
| Deploy | Deploy contínuo na Kronn: push na `main` → gates do CI → `publicar.yml` (build, fumaça, integração, libs, `:<sha>`, `:latest`) → webhook de pacotes do GitHub → auto-deploy da Kronn | `.github/workflows/ci.yml`, `publicar.yml`, `deploy/kronn/` |
| Deploy | Release pela tag `v*`, promovendo o `:<sha>` já publicado; não move `:latest` | `.github/workflows/release.yml` |
| Deploy | `make ship` acompanha o `ci.yml`; sem build no push de `release/vX.Y.Z` | `.workflow.conf` |
| Deploy | `stop_grace_period` da Kronn acima do encerramento do serviço (timeout do worker + margem) | `deploy/kronn/docker-compose.yml` |
| Libs | Libs da ACBr do release **deste** repositório (`ACBR_REPO`, `ACBR_LIBS_RELEASE` com sufixo `-d3sN`) | `Makefile` |
| Libs | Patch `0006`: DANFSe do Padrão Nacional no layout do DANFSe oficial do ADN | `docker/acbr-patches/0006-*.patch`, gerado por `scripts/fork/gerar-patch-danfse.py` |
| DANFSe | Logo da NFS-e e canhoto (`[DANFSe] LogoNFSe` e `ImprimeCanhoto`) | `internal/acbr/logo.go`, `docker/logo-nfse.jpg` |
| PDF | Fontes embutidas em todo PDF da lib (Ghostscript) e "Microsoft Sans Serif" → Liberation Sans | `internal/acbr/pdffontes.go`, `docker/fontconfig/` |
| Imagem | `COPY --chmod` no entrypoint e nas `.so` (build com umask 077) | `Dockerfile` |

## Sincronizar com o upstream

```bash
git remote add upstream https://github.com/4devsmart/wrapper-api.git   # uma vez
git fetch upstream
git merge --no-ff --no-commit upstream/main
```

1. **Conflitos esperados**, sempre a favor do fluxo do fork: `ci.yml`, `publicar.yml`,
   `release.yml`, `.workflow.conf`, `Makefile` (`ACBR_LIBS_RELEASE`, `ACBR_REPO`),
   `Dockerfile`, `internal/platform/config/config.go`, `.env.example`.
2. **Releia o resultado inteiro** dos arquivos que os dois lados tocaram, inclusive os
   que mesclaram sozinhos. O git não vê dependência entre trechos: um gatilho mudado
   no `on:` desliga o job `publicar` sem conflito nenhum.
3. `make fork-conferir`. Tem de passar antes de seguir.
4. **O upstream mudou `ACBR_REV`?** (compare com `git diff HEAD upstream/main -- Makefile`)
   Se sim, as libs do fork precisam ser refeitas na revisão nova, com o 0006:
   ```bash
   make acbr-fonte ACBR_REV=<nova>
   make fork-patch-danfse ACBR_REV=<nova>
   make acbr-compilar ACBR_REV=<nova>
   ```
   Se uma troca do gerador não achar o trecho no fonte novo, ele para e mostra qual.
   Ajuste a troca em `scripts/fork/gerar-patch-danfse.py`, **nunca o .patch à mão**, e
   rode de novo. Depois extraia as `.so` (`make acbr-extrair`), gere um DANFSe de
   homologação e compare com o oficial antes de publicar:
   ```bash
   make acbr-libs-publicar ACBR_REV=<nova> ACBR_LIBS_RELEASE=acbrlib-r<nova>-d3s1
   ```
   e ponha esse nome em `ACBR_LIBS_RELEASE` no `Makefile`.
   Mesma revisão, mas o 0006 mudou? Republique com o sufixo seguinte (`-d3s2`...).
5. **O upstream mudou o encerramento do serviço?** (`ACBR_WORKER_TIMEOUT_SECONDS`,
   `margemDeEncerramento`) O `fork-conferir` falha se o `stop_grace_period` da
   Kronn ficar curto: suba os dois serviços do compose da Kronn.
6. `make ci`, `make up` e uma emissão de homologação com PDF (ver abaixo).
7. Commit do merge, push para a `develop` (só os gates, sem deploy), e só com o CI
   verde, push para a `main`, que publica e implanta.

Nunca `git push --tags`: as tags do upstream (`v1.x.y`) disparariam o `release.yml`
do fork.

## Release e deploy

- **Deploy:** todo push na `main` que passar nos gates publica `:<sha>` e move
  `:latest`. O webhook do repositório (eventos de pacote) avisa a Kronn, e o
  auto-deploy dela reimplanta quando o `:latest` mudou. O secret
  `KRONN_DEPLOY_HOOK` fica sem cadastrar: com o webhook ativo, ele faria cada
  publicação implantar duas vezes. Ver `deploy/kronn/README.md`.
- **Release:** `vX.Y.Z-d3s.N`, sobre a versão do upstream em que o fork está.
  É uma tag num commit da `main` já publicado:
  `git tag -a v1.8.0-d3s.1 -m v1.8.0-d3s.1 && git push origin v1.8.0-d3s.1`.
  Com hífen, é pré-release: não move `:stable` nem `:v1`, e a Kronn segue no `:latest`.

## Conferência do DANFSe

Gere o PDF de uma nota de homologação por `POST /v1/nfse/pdf` com o `xml_b64` e
compare com um DANFSe oficial do ADN. Para medir o fundo cinza (`#F2F2F2`) contra
as bordas, renderize a 300 dpi (`pdftoppm -r 300`) e confira os pixels: miniatura
reduzida engana.
