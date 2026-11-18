#!/usr/bin/env python3
"""Gera o patch 0006: DANFSe do Padrão Nacional no layout do DANFSe oficial do ADN.

Edita cópias do .lfm (UTF-8, CRLF) e do .pas (ISO-8859-1, CRLF) e escreve o diff
unificado com caminhos a/ b/ relativos à raiz do fonte do ACBr (patch -p1).

Uso: make fork-patch-danfse   (ou, à mão:
     gerar-patch-danfse.py <dir com os originais> <dir de saída> <arquivo .patch>)

Quando uma revisão nova do ACBr mudar o trecho que uma troca procura, o script
para e mostra qual: ajuste a troca aqui, nunca o .patch à mão. Ver docs/FORK.md.
"""
import re
import subprocess
import sys
from pathlib import Path

ORIG, SAIDA, PATCH = map(Path, sys.argv[1:4])
REL = "Fontes/ACBrDFe/ACBrNFSeX/DANFSE/Fortes"
LFM = "ACBrNFSeXDANFSeRLPadraoNacional.lfm"
PAS = "ACBrNFSeXDANFSeRLPadraoNacional.pas"

CINZA = "15921906"  # $00F2F2F2, o fundo das células do DANFSe oficial
COL = [4, 192, 381, 569]  # quatro colunas iguais, como no oficial (752 px)


# --------------------------------------------------------------------------
# .lfm como árvore de objetos, preservando cada linha
# --------------------------------------------------------------------------
class Obj:
    def __init__(self, nome, classe, ind, cab):
        self.nome, self.classe, self.ind = nome, classe, ind
        self.cab = cab  # linha "object X: Y"
        self.props = []  # linhas de propriedade (podem ser multilinha)
        self.filhos = []

    def prop(self, k):
        for p in self.props:
            m = re.match(r"\s*" + re.escape(k) + r" = (.*)", p[0])
            if m:
                return m.group(1)
        return None

    def set(self, k, v):
        pad = " " * (self.ind + 2)
        for p in self.props:
            if re.match(r"\s*" + re.escape(k) + r" = ", p[0]):
                p[:] = [f"{pad}{k} = {v}"]
                return
        self.props.append([f"{pad}{k} = {v}"])

    def remove(self, k):
        self.props = [p for p in self.props if not re.match(r"\s*" + re.escape(k) + r" = ", p[0])]

    def linhas(self):
        out = [self.cab]
        for p in self.props:
            out += p
        for f in self.filhos:
            out += f.linhas()
        out.append(" " * self.ind + "end")
        return out


def ler_lfm(texto):
    linhas = texto.split("\r\n")
    raiz, pilha, i = None, [], 0
    while i < len(linhas):
        l = linhas[i]
        m = re.match(r"^(\s*)(?:object|inherited) (\w+): (\w+)", l)
        if m:
            o = Obj(m.group(2), m.group(3), len(m.group(1)), l)
            if pilha:
                pilha[-1].filhos.append(o)
            else:
                raiz = o
            pilha.append(o)
            i += 1
            continue
        if re.match(r"^\s*end$", l) and pilha:
            pilha.pop()
            i += 1
            if not pilha:
                resto = linhas[i:]
                return raiz, resto
            continue
        # propriedade, possivelmente multilinha ( ... ) ou { ... } ou < ... >
        bloco = [l]
        if re.search(r"= \($|= \{$|= <$", l) or re.search(r"= \($", l):
            fecha = {"(": ")", "{": "}", "<": ">"}[l.rstrip()[-1]]
            i += 1
            while i < len(linhas):
                bloco.append(linhas[i])
                if linhas[i].rstrip().endswith(fecha):
                    break
                i += 1
        pilha[-1].props.append(bloco)
        i += 1
    raise SystemExit("lfm sem fim")


def todos(o):
    yield o
    for f in o.filhos:
        yield from todos(f)


def achar(raiz, nome):
    for o in todos(raiz):
        if o.nome == nome:
            return o
    raise SystemExit(f"componente não encontrado: {nome}")


def num(o, k, padrao=0):
    v = o.prop(k)
    return int(v) if v is not None else padrao


def fundo(nome, ind, left, top, width, height):
    """Retângulo cinza sem borda, pintado antes dos rótulos da célula."""
    o = Obj(nome, "TRLDraw", ind, " " * ind + f"object {nome}: TRLDraw")
    for k, v in [("Left", left), ("Height", height), ("Top", top), ("Width", width),
                 ("Brush.Color", CINZA), ("Pen.Color", CINZA)]:
        o.set(k, str(v))
    return o


# --------------------------------------------------------------------------
lfm_txt = (ORIG / LFM).read_bytes().decode("utf-8")
raiz, resto = ler_lfm(lfm_txt)

# 1. Nenhum rótulo pinta o próprio fundo: com Transparent = False ele cobre o
#    cinza das células e o texto do vizinho (o ")" de "(ISSQN)" sumia assim).
for o in todos(raiz):
    if o.classe in ("TRLLabel", "TRLMemo") and o.prop("Transparent") == "False":
        o.set("Transparent", "True")

# 2. Fontes no tamanho do oficial: 7 pt nos títulos, rótulos principais e valores;
#    6 pt nos sub-rótulos.
TITULOS = ["RLLabel21", "RLLabel4", "RLLabel14", "RLLabel10", "RLLabel115",
           "RLLabel27", "RLLabel3", "RLLabel6", "RLLabel42"]
IDE_ROTULOS = ["rllCodigoChave", "RLLabel13", "RLLabel7", "RLLabel12", "RLLabel18",
               "RLLabel16", "RLLabel22", "RLLabel23", "RLLabel15", "RLLabel19"]
CABECALHO = {"RLLabel74", "RLLabel8", "rlbHomologacao", "rlmPrefeitura", "rllMsgTeste"}
banda_de = {}
for b in raiz.filhos:
    for o in todos(b):
        banda_de[o.nome] = b.nome
for o in todos(raiz):
    if o.classe not in ("TRLLabel", "TRLMemo") or o.nome in CABECALHO:
        continue
    negrito = (o.prop("Font.Style") or "").find("fsBold") >= 0
    if o.nome in TITULOS or o.nome in IDE_ROTULOS:
        o.set("Font.Height", "-9")
    elif negrito:
        o.set("Font.Height", "-8")
    elif o.prop("Font.Height") in ("-11", "-12", "-13"):
        o.set("Font.Height", "-9")  # valores (identificação e canhoto)
# Os avisos de "não identificado" continuam opacos e da largura da banda: com a
# banda encolhida a 20 px, são eles que cobrem os rótulos vazios da primeira
# linha (CNPJ / CPF / NIF...). Transparentes, os rótulos apareciam por baixo.
for nome in ["rllDestinatarioNaoIdentificado", "rllIntermediarioNaoIdentificado"]:
    o = achar(raiz, nome)
    o.set("Font.Height", "-9")
    o.remove("Font.Style")
    for k, v in [("AutoSize", "False"), ("Left", "1"), ("Top", "2"), ("Width", "750"),
                 ("Height", "14"), ("Transparent", "False")]:
        o.set(k, v)

# 3. Quatro colunas iguais em todas as seções.
MAPA = {
    "rlbBanda02_Ide_NFSe": [4, 195, 328],
    "rlbBanda03_Emitente": [4, 264, 408, 607],
    "rlbBanda04_Tomador": [4, 264, 408, 607],
    "rlbBanda05_Destinatario": [4, 264, 408, 607],
    "rlbBanda06_Intermediario": [4, 264, 408, 607],
    "rlbBanda07_ServicoPrestado": [4, 170, 408, 539],
    "rlbBanda10_TributacaoMunicipal": [4, 204, 365, 573],
    "rlbBanda11_TributacaoFederal": [4, 238, 377, 574],
    "rlbBanda12_TributacaoFederalIBSCBS": [4, 186, 374, 580],
    "rlbBanda13_ValorTotaNFSe": [4, 227, 392, 557],
}
ESPECIAL = {"RLLabel134": 2, "rllDescCSLL": 2, "RLLabel38": 2, "rllcIndOp": 2}
for bnome, cols in MAPA.items():
    b = achar(raiz, bnome)
    for o in b.filhos:
        if o.classe not in ("TRLLabel", "TRLMemo"):
            continue
        left = num(o, "Left")
        if o.nome in ESPECIAL:
            o.set("Left", str(COL[ESPECIAL[o.nome]]))
            continue
        for i, c in enumerate(cols):
            if abs(left - c) <= 3:
                o.set("Left", str(COL[i]))
                break
# No oficial, o regime de apuração do SN fica na segunda coluna, ao lado do
# "Simples Nacional na Data de Competência".
emit = achar(raiz, "rlbBanda03_Emitente")
for o in emit.filhos:
    if o.nome == "rllEmitenteRegimeApuracao" or (o.prop("Caption") or "").startswith("'Regime de Apura"):
        o.set("Left", str(COL[1]))
# QR e texto da autenticidade na quarta coluna.
qr = achar(raiz, "imgQRCode")
for k, v in [("Left", 630), ("Top", 4), ("Width", 58), ("Height", 58)]:
    qr.set(k, str(v))
m1 = achar(raiz, "RLMemo1")
for k, v in [("Left", COL[3]), ("Top", 66), ("Width", 180)]:
    m1.set(k, str(v))

# 4. Textos dos rótulos como no oficial.
TROCAS = [
    ("NFS-E'", "NFS-e'"),
    ("'Inscrição Municipal'", "'Indicador Municipal (Inscrição)'"),
    ("'Código NBS'", "'Código da NBS'"),
    ("'Código de Tributação Nacional / Municípal'", "'Código de Tributação Nacional/Municipal'"),
    ("'DESTINATÁRIO DO SERVIÇO NÃO IDENTIFICADO NA NFS-e'", "'DESTINATÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e'"),
    ("'INTERMEDIÁRIO DO SERVIÇO NÃO IDENTIFICADO NA NFS-e'", "'INTERMEDIÁRIO DA OPERAÇÃO NÃO IDENTIFICADO NA NFS-e'"),
    ("'Município / Sigla UF / Pais de Incidência do ISSQN'", "'Município / Sigla UF / País de Incidência do ISSQN'"),
    ("'Contribuição Previdenciária-Retida'", "'Contribuição Previdenciária - Retida'"),
    ("'Contribuições Sociais-Retidas'", "'Contribuições Sociais - Retidas'"),
    ("'COFINS-Débito Apuração Própria'", "'COFINS - Débito Apuração Própria'"),
    ("'Descrição Contrib. Sociais-Retidas'", "'Descrição Contrib. Sociais - Retidas'"),
    ("'TRIBUTAÇÃO IBS / CBS'", "'TRIBUTAÇÃO IBS/CBS'"),
    ("'Exclusões e Reduções da BC'", "'Exclusões e Reduções da Base de Cálculo'"),
    ("'BC após Exclusões e Reduções'", "'Base de Cálculo Após Exclusões e Reduções'"),
    ("'Alíq. Efetiva Municípal - IBS'", "'Alíq. Efetiva Municipal - IBS'"),
    ("'Alíq. Efetiva - CBS'", "'Alíquota Efetiva - CBS'"),
    ("'Valor da Operação / Serviço'", "'VALOR DA OPERAÇÃO / SERVIÇO'"),
    ("'Valor Líquido da NFS-e'", "'VALOR LÍQUIDO DA NFS-e'"),
    ("'Valor Líquido da NFS-e + IBS/CBS'", "'VALOR LÍQUIDO DA NFS-e + IBS/CBS'"),
    ("'Desconto Incondicionando'", "'Desconto Incondicionado'"),
    ("'Beneficio Municipal'", "'Benefício Municipal'"),
    ("'DATA'", "'DATA CIENTIFICAÇÃO:'"),
    ("'Identificação e Assinatura do Recebedor'", "'IDENTIFICAÇÃO E ASSINATURA'"),
    ("'N. NFS-e / Chave NFS-e'", "'N° NFS-e / CHAVE NFS-e'"),
]
for o in todos(raiz):
    c = o.prop("Caption")
    if c is None:
        continue
    novo = c
    for a, b_ in TROCAS:
        if a == "NFS-E'":
            novo = novo.replace("NFS-E'", "NFS-e'")
        elif novo == a:
            novo = b_
    if novo != c:
        o.set("Caption", novo)

# 5. Fundo cinza (#F2F2F2): cabeçalho e as células da lista.
cab = achar(raiz, "rlbBanda01_Logos")
logo = achar(raiz, "rliLogoNFSe")
for k, v in [("Left", 4), ("Top", 6), ("Width", 160), ("Height", 32)]:
    logo.set(k, str(v))
for nome, top in [("RLLabel74", 6), ("RLLabel8", 20), ("rlbHomologacao", 34)]:
    achar(raiz, nome).set("Top", str(top))
pref = achar(raiz, "rlmPrefeitura")
for k, v in [("Left", COL[3]), ("Top", 6), ("Width", 180)]:
    pref.set(k, str(v))
# "Ambiente Gerador" e "Tipo de Ambiente" em 6 pt, abaixo do município, nos
# rótulos que antes mostravam a paginação (o oficial não pagina).
for nome, top in [("RLLabel33", 19), ("RLLabel62", 27)]:
    o = achar(raiz, nome)
    for k, v in [("Left", COL[3]), ("Top", top), ("Width", 180), ("Height", 10), ("Font.Height", "-8")]:
        o.set(k, str(v))
    o.remove("Font.Style")
    o.set("Caption", "''")
for nome in ["RLSystemInfo1", "RLSystemInfo2"]:
    achar(raiz, nome).set("Visible", "False")
# 2 px de folga em cada lado: o FortesReport pinta as bordas da banda ANTES dos
# componentes, e um retângulo encostado nelas as cobria.
FOLGA = 2
cab.filhos.insert(0, fundo("rldFundoCabecalho", cab.ind + 2, FOLGA, FOLGA, 752 - 2 * FOLGA, 52 - 2 * FOLGA))
cab.remove("AutoSize")
cab.set("Height", "52")

def celula(banda, nome, left, top, width, height):
    b = achar(raiz, banda)
    b.filhos.insert(0, fundo(nome, b.ind + 2, left, top, width, height))

LARG = COL[1] - 5 - FOLGA  # da borda até antes da segunda coluna
celula("rlbBanda02_Ide_NFSe", "rldFundoEmitente", FOLGA, 90, LARG, 120 - 90 - FOLGA)
celula("rlbBanda03_Emitente", "rldFundoPrestador", FOLGA, FOLGA, LARG, 26 - FOLGA)
celula("rlbBanda04_Tomador", "rldFundoTomador", FOLGA, FOLGA, LARG, 26 - FOLGA)
celula("rlbBanda07_ServicoPrestado", "rldFundoServico", FOLGA, FOLGA, LARG, 26 - FOLGA)
celula("rlbBanda10_TributacaoMunicipal", "rldFundoTribMun", FOLGA, FOLGA, LARG, 26 - FOLGA)
celula("rlbBanda11_TributacaoFederal", "rldFundoTribFed", FOLGA, FOLGA, LARG, 26 - FOLGA)
celula("rlbBanda12_TributacaoFederalIBSCBS", "rldFundoIBSCBS", FOLGA, FOLGA, LARG, 26 - FOLGA)
celula("rlbBanda13_ValorTotaNFSe", "rldFundoValorTotal", FOLGA, FOLGA, LARG, 26 - FOLGA)
celula("rlbBanda13_ValorTotaNFSe", "rldFundoLiqIBSCBS", COL[3] - 4, 29, 752 - (COL[3] - 4) - FOLGA, 63 - 29 - FOLGA)

# A banda é desenhada com 752 px, mas na geração ela estica até a largura do
# relatório (o AjustarMargem muda as margens). Largura fixa deixava o cinza do
# cabeçalho e o da última célula terminarem antes da borda direita.
# Anchors não basta: o FortesReport não reaplica a âncora quando a banda estica.
# A largura final é ajustada no BeforePrint de cada banda (ver o .pas).

# 6. Canhoto no rodapé da página, em três colunas, como no oficial.
can = achar(raiz, "rlbCanhoto")
can.set("BandType", "btFooter")
can.set("Height", "34")
for nome, left, top in [("RLLabel121", COL[0], 3), ("RLLabel54", COL[1], 3),
                        ("RLLabel50", COL[2], 3), ("rllNumChave", COL[2], 14)]:
    o = achar(raiz, nome)
    o.set("Left", str(left))
    o.set("Top", str(top))
for nome in ["RLLabel121", "RLLabel54", "RLLabel50"]:
    o = achar(raiz, nome)
    o.set("Font.Height", "-8")
    o.set("Font.Style", "[fsBold]")
achar(raiz, "rllNumChave").set("Font.Height", "-9")
for nome in ["rllNumNFSe", "RLLabel122", "RLDraw5"]:
    achar(raiz, nome).set("Visible", "False")
# Divisórias verticais entre as colunas do canhoto.
for i, nome in [(1, "rldCanhotoDiv1"), (2, "rldCanhotoDiv2")]:
    d = Obj(nome, "TRLDraw", can.ind + 2, " " * (can.ind + 2) + f"object {nome}: TRLDraw")
    for k, v in [("Left", COL[i] - 4), ("Height", 34), ("Top", 0), ("Width", 1), ("DrawKind", "dkLine"), ("Angle", "90")]:
        d.set(k, str(v))
    can.filhos.append(d)

novos_draws = ["rldFundoCabecalho", "rldFundoEmitente", "rldFundoPrestador", "rldFundoTomador",
               "rldFundoServico", "rldFundoTribMun", "rldFundoTribFed", "rldFundoIBSCBS",
               "rldFundoValorTotal", "rldFundoLiqIBSCBS", "rldCanhotoDiv1", "rldCanhotoDiv2"]

SAIDA.mkdir(parents=True, exist_ok=True)
(SAIDA / LFM).write_bytes("\r\n".join(raiz.linhas() + resto).encode("utf-8"))

# --------------------------------------------------------------------------
# .pas
# --------------------------------------------------------------------------
pas = (ORIG / PAS).read_bytes().decode("latin-1")


def troca(antigo, novo, n=1):
    global pas
    antigo = antigo.replace("\n", "\r\n")
    novo = novo.replace("\n", "\r\n")
    achados = pas.count(antigo)
    if achados != n:
        raise SystemExit(f"esperava {n} ocorrência(s), achei {achados}:\n{antigo}")
    pas = pas.replace(antigo, novo)


# campos dos componentes novos
troca("    imgQRCode: TRLImage;\n",
      "    imgQRCode: TRLImage;\n" + "".join(f"    {n}: TRLDraw;\n" for n in novos_draws))

# funções de formatação, antes da primeira implementação
troca("  FQuebradeLinha: String;\n\n  { TfrlXDANFSeRLPadraoNacional }\n",
      """  FQuebradeLinha: String;

  { TfrlXDANFSeRLPadraoNacional }

// Formatos do DANFSe oficial do ADN.
function TracoSeVazio(const s: string): string;
begin
  if Trim(s) = '' then
    Result := '-'
  else
    Result := s;
end;

// 3304557 -> 33.04557
function FormatarIBGEADN(const c: string): string;
begin
  if Length(c) = 7 then
    Result := Copy(c, 1, 2) + '.' + Copy(c, 3, 5)
  else
    Result := c;
end;

// 20051040 -> 20.051-040
function FormatarCEPADN(const c: string): string;
var
  d: string;
  i: Integer;
begin
  d := '';
  for i := 1 to Length(c) do
    if CharInSet(c[i], ['0'..'9']) then
      d := d + c[i];
  if Length(d) = 8 then
    Result := Copy(d, 1, 2) + '.' + Copy(d, 3, 3) + '-' + Copy(d, 6, 3)
  else
    Result := c;
end;

// (21)2038-8855 -> (21) 2038-8855
function FormatarFoneADN(const f: string): string;
begin
  Result := FormatarFone(f);
  if (Pos(')', Result) > 0) and (Pos(') ', Result) = 0) then
    Result := StringReplace(Result, ')', ') ', []);
  Result := TracoSeVazio(Result);
end;

// Rio de Janeiro/RJ -> Rio de Janeiro / RJ
function BarraComEspacos(const s: string): string;
begin
  Result := StringReplace(s, ' / ', '/', [rfReplaceAll]);
  Result := StringReplace(Result, '/', ' / ', [rfReplaceAll]);
end;

// País do local: o oficial mostra '-' para o Brasil.
function PaisADN(c: Integer): string;
begin
  if (c = 0) or (c = 1058) then
    Result := '-'
  else
    Result := CodIBGEPaisToSiglaISO2(c);
end;

""")

# cabeçalho
troca("""  rlmPrefeitura.Lines.Add(ACBrStr('Município: ') + fpNFSe.infNFSe.xLocEmi + '/' +
                                          fpNFSe.infNFSe.UFLocEmi);
  rlmPrefeitura.Lines.Add(ACBrStr('Ambiente Gerador: ' + ambGerToStrText(fpNFSe.infNFSe.ambGer)));
  rlmPrefeitura.Lines.Add(ACBrStr('Tipo Ambiente: ' + Ambiente));
""", """  rlmPrefeitura.Lines.Add(ACBrStr('Município: ') + fpNFSe.infNFSe.xLocEmi + ' - ' +
                                          fpNFSe.infNFSe.UFLocEmi);
  RLLabel33.Caption := 'Ambiente Gerador: ' + ambGerToStr(fpNFSe.infNFSe.ambGer);
  if fpNFSe.Producao = snNao then
    RLLabel62.Caption := 'Tipo de Ambiente: 2'
  else
    RLLabel62.Caption := 'Tipo de Ambiente: 1';
""")

# Fundos que vão até a borda direita: a banda estica até a largura do relatório
# na geração, então a largura do retângulo sai da largura final da banda.
troca("""  TDFeReportFortes.CarregarLogo(rliLogoNFSe, fpDANFSe.LogoNFSe);
""", """  TDFeReportFortes.CarregarLogo(rliLogoNFSe, fpDANFSe.LogoNFSe);
  rldFundoCabecalho.Width := rlbBanda01_Logos.Width - 2 * rldFundoCabecalho.Left;
""")
troca("""procedure TfrlXDANFSeRLPadraoNacional.rlbBanda13_ValorTotaNFSeBeforePrint(
  Sender: TObject; var PrintIt: Boolean);
var
  LValor: Double;
begin
  inherited;
""", """procedure TfrlXDANFSeRLPadraoNacional.rlbBanda13_ValorTotaNFSeBeforePrint(
  Sender: TObject; var PrintIt: Boolean);
var
  LValor: Double;
begin
  inherited;
  rldFundoLiqIBSCBS.Width := rlbBanda13_ValorTotaNFSe.Width - rldFundoLiqIBSCBS.Left - 2;
""")

# identificação
troca("""    tePrestador: rllEmitente.Caption := ACBrStr('Prestador do Serviço');
    teTomador: rllEmitente.Caption := ACBrStr('Tomador do Serviço');
  else
    // teIntermediario
    rllEmitente.Caption := ACBrStr('Intermediário do Serviço');""".encode("utf-8").decode("utf-8"),
      """    tePrestador: rllEmitente.Caption := ACBrStr('Prestador');
    teTomador: rllEmitente.Caption := ACBrStr('Tomador');
  else
    // teIntermediario
    rllEmitente.Caption := ACBrStr('Intermediário');""")
# Sem o grupo IBSCBS a finalidade não foi informada: o oficial mostra '-'.
troca("  rllFinalidade.Caption := finNFSeToStrText(fpNFSe.IBSCBS.finNFSe);\n",
      """  if fpNFSe.IBSCBS.cIndOp <> '' then
    rllFinalidade.Caption := finNFSeToStrText(fpNFSe.IBSCBS.finNFSe)
  else
    rllFinalidade.Caption := '-';
""")

# prestador
troca("    rllEmitenteSimplesNacional.Caption := ACBrStr('Optante - MicroEmpresa EPP');",
      "    rllEmitenteSimplesNacional.Caption := ACBrStr('Optante - Microempresa ou Empresa de ...');")
troca("""  rllEmitenteInscMunicipal.Caption := fpNFSe.infNFSe.emit.Identificacao.InscricaoMunicipal;
  rllEmitenteEmail.Caption := fpNFSe.infNFSe.emit.Contato.Email;
  rllEmitenteMunicipio.Caption := fpNFSe.infNFSe.emit.Endereco.xMunicipio + '/' +
                                  fpNFSe.infNFSe.emit.Endereco.UF;
""", """  rllEmitenteInscMunicipal.Caption := TracoSeVazio(fpNFSe.infNFSe.emit.Identificacao.InscricaoMunicipal);
  rllEmitenteEmail.Caption := TracoSeVazio(LowerCase(fpNFSe.infNFSe.emit.Contato.Email));
  rllEmitenteMunicipio.Caption := fpNFSe.infNFSe.emit.Endereco.xMunicipio + ' / ' +
                                  fpNFSe.infNFSe.emit.Endereco.UF;
""")
troca("        rllEmitenteRegimeApuracao.Caption := ACBrStr('Federais e Municipal pelo SN');",
      "        rllEmitenteRegimeApuracao.Caption := ACBrStr('Regime de apuração dos tributos federais e municipal pelo Simples Nacional');")
troca("        rllEmitenteRegimeApuracao.Caption := ACBrStr('Federais pelo SN');",
      "        rllEmitenteRegimeApuracao.Caption := ACBrStr('Regime de apuração dos tributos federais pelo SN e o ISSQN pela NFS-e');")
troca("      rllEmitenteRegimeApuracao.Caption := ACBrStr('Federais e Municipal fora SN');",
      "      rllEmitenteRegimeApuracao.Caption := ACBrStr('Regime de apuração dos tributos federais e municipal pela NFS-e');")
troca("""  rllEmitenteTelefone.Caption := FormatarFone(fpNFSe.infNFSe.emit.Contato.Telefone);
  rllEmitenteCEP.Caption := fpNFSe.Prestador.Endereco.CodigoMunicipio + ' / ' +
                            FormatarCEP(fpNFSe.infNFSe.emit.Endereco.CEP);
""", """  rllEmitenteTelefone.Caption := FormatarFoneADN(fpNFSe.infNFSe.emit.Contato.Telefone);
  rllEmitenteCEP.Caption := FormatarIBGEADN(fpNFSe.Prestador.Endereco.CodigoMunicipio) + ' / ' +
                            FormatarCEPADN(fpNFSe.infNFSe.emit.Endereco.CEP);
""")

# tomador
troca("""  rllTomaInscMunicipal.Caption := fpNFSe.Tomador.IdentificacaoTomador.InscricaoMunicipal;
  rllTomaEmail.Caption := fpNFSe.Tomador.Contato.Email;
  rllTomaMunicipio.Caption := fpNFSe.Tomador.Endereco.xMunicipio + '/' +
                                  fpNFSe.Tomador.Endereco.UF;
  rllTomaTelefone.Caption := FormatarFone(fpNFSe.Tomador.Contato.Telefone);
  rllTomaCEP.Caption := fpNFSe.Tomador.Endereco.CodigoMunicipio + ' / ' +
                            FormatarCEP(fpNFSe.Tomador.Endereco.CEP);
""", """  rllTomaInscMunicipal.Caption := TracoSeVazio(fpNFSe.Tomador.IdentificacaoTomador.InscricaoMunicipal);
  rllTomaEmail.Caption := TracoSeVazio(LowerCase(fpNFSe.Tomador.Contato.Email));
  rllTomaMunicipio.Caption := fpNFSe.Tomador.Endereco.xMunicipio + ' / ' +
                                  fpNFSe.Tomador.Endereco.UF;
  rllTomaTelefone.Caption := FormatarFoneADN(fpNFSe.Tomador.Contato.Telefone);
  rllTomaCEP.Caption := FormatarIBGEADN(fpNFSe.Tomador.Endereco.CodigoMunicipio) + ' / ' +
                            FormatarCEPADN(fpNFSe.Tomador.Endereco.CEP);
""")

# serviço
troca("""    Codigo := Codigo + '/' + fpNFSe.Servico.CodigoTributacaoMunicipio;""",
      """    Codigo := Codigo + ' / ' + fpNFSe.Servico.CodigoTributacaoMunicipio;""")
troca("""  rllCodigoNBS.Caption := fpNFSe.Servico.CodigoNBS;""",
      """  rllCodigoNBS.Caption := TracoSeVazio(fpNFSe.Servico.CodigoNBS);""")
troca("""  rllLocalPrestacao.Caption := fpNFSe.Servico.MunicipioPrestacaoServico + ' / ' +
                              CodIBGEPaisToSiglaISO2(fpNFSe.Servico.CodigoPais);""",
      """  rllLocalPrestacao.Caption := BarraComEspacos(fpNFSe.Servico.MunicipioPrestacaoServico) + ' / ' +
                              PaisADN(fpNFSe.Servico.CodigoPais);""")

# tributação municipal
troca("""    rllMunicipioIncidencia.Caption := fpNFSe.infNFSe.xLocIncid + ' / ' +
                                      fpNFSe.infNFSe.UFLocIncid;

    if fpNFSe.Servico.Valores.tribMun.cPaisResult > 0 then
      rllMunicipioIncidencia.Caption := rllMunicipioIncidencia.Caption + ' / ' +
        CodIBGEPaisToSiglaISO2(fpNFSe.Servico.Valores.tribMun.cPaisResult);""",
      """    rllMunicipioIncidencia.Caption := fpNFSe.infNFSe.xLocIncid + ' / ' +
                                      fpNFSe.infNFSe.UFLocIncid + ' / ' +
                                      PaisADN(fpNFSe.Servico.Valores.tribMun.cPaisResult);""")
# bug do original: com vCalcBM zerado, o traço ia para o ISSQN apurado.
troca("""    rllCalculoBM.Caption := 'R$ ' + FormatFloatBr(fpNFSe.infNFSe.Valores.vCalcBM)
  else
    rllValorISSQNApurado.Caption := '-';""",
      """    rllCalculoBM.Caption := 'R$ ' + FormatFloatBr(fpNFSe.infNFSe.Valores.vCalcBM)
  else
    rllCalculoBM.Caption := '-';""")

# Sem regime especial, imunidade, suspensão, benefício, deduções nem desconto,
# o oficial não mostra essas duas linhas: a de BC/alíquota sobe e a banda encolhe.
troca("""  else
    rllValorISSQNApurado.Caption := '-';
end;

procedure TfrlXDANFSeRLPadraoNacional.rlbBanda11_TributacaoFederalBeforePrint(""",
      """  else
    rllValorISSQNApurado.Caption := '-';

  OcultarLinhasMunicipais(
    (fpNFSe.RegimeEspecialTributacao = retNenhum) and
    (rllTipoImunidade.Caption = '-') and
    (fpNFSe.Servico.Valores.tribMun.tpSusp <> tsDecisaoJudicial) and
    (fpNFSe.Servico.Valores.tribMun.tpSusp <> tsProcessoAdm) and
    (rllNumeroProcesso.Caption = '-') and (rllBeneficioMunic.Caption = '-') and
    (rllCalculoBM.Caption = '-') and (rllValorTotalDedRed.Caption = '-') and
    (rllValorDescIncond.Caption = '-'));
end;

procedure TfrlXDANFSeRLPadraoNacional.OcultarLinhasMunicipais(Ocultar: Boolean);
var
  Opcionais: array[0..15] of TRLLabel;
  Ultima: array[0..7] of TRLLabel;
  i, Delta: Integer;
begin
  Opcionais[0] := RLLabel107;  Opcionais[1] := RLLabel17;
  Opcionais[2] := RLLabel90;   Opcionais[3] := RLLabel101;
  Opcionais[4] := rllRegimeEspecial; Opcionais[5] := rllTipoImunidade;
  Opcionais[6] := rllSuspensao;      Opcionais[7] := rllNumeroProcesso;
  Opcionais[8] := RLLabel109;  Opcionais[9] := RLLabel111;
  Opcionais[10] := RLLabel103; Opcionais[11] := RLLabel93;
  Opcionais[12] := rllBeneficioMunic;   Opcionais[13] := rllCalculoBM;
  Opcionais[14] := rllValorTotalDedRed; Opcionais[15] := rllValorDescIncond;
  Ultima[0] := RLLabel25;  Ultima[1] := RLLabel97;
  Ultima[2] := RLLabel105; Ultima[3] := RLLabel113;
  Ultima[4] := rllValorBCISSQN;  Ultima[5] := rllAliquotaAplicada;
  Ultima[6] := rllRetencaoISSQN; Ultima[7] := rllValorISSQNApurado;

  for i := Low(Opcionais) to High(Opcionais) do
    Opcionais[i].Visible := not Ocultar;

  // Posições do .lfm: a última linha fica em 85 (rótulos) e 98 (valores), e
  // sobe para 29/42 quando as duas do meio somem.
  if Ocultar then
    Delta := 56
  else
    Delta := 0;
  for i := 0 to 3 do
    Ultima[i].Top := 85 - Delta;
  for i := 4 to 7 do
    Ultima[i].Top := 98 - Delta;
  rlbBanda10_TributacaoMunicipal.Height := 115 - Delta;
end;

procedure TfrlXDANFSeRLPadraoNacional.rlbBanda11_TributacaoFederalBeforePrint(""")
troca("""    procedure rlbCanhotoBeforePrint(Sender: TObject; var PrintIt: Boolean);
""", """    procedure rlbCanhotoBeforePrint(Sender: TObject; var PrintIt: Boolean);
    procedure OcultarLinhasMunicipais(Ocultar: Boolean);
""")

# tributação federal
troca("  rllDescCSLL.Caption := ACBrStr(tpRetPisCofinsDescricao(fpNFSe.Servico.Valores.tribFed.tpRetPisCofins));",
      "  rllDescCSLL.Caption := ACBrStr(tpRetPisCofinsToStr(fpNFSe.Servico.Valores.tribFed.tpRetPisCofins) + ' - ' +\r\n"
      "    tpRetPisCofinsDescricao(fpNFSe.Servico.Valores.tribFed.tpRetPisCofins));")

# canhoto
troca("""  rllNumNFSe.Caption := fpNFSe.Numero;
  rllNumChave.Caption := fpNFSe.CodigoVerificacao;""",
      """  rllNumNFSe.Caption := fpNFSe.Numero;
  if Length(fpNFSe.ChaveAcesso) = 50 then
    rllNumChave.Caption := fpNFSe.Numero + ' / ' + fpNFSe.ChaveAcesso
  else
    rllNumChave.Caption := fpNFSe.Numero + ' / ' + fpNFSe.CodigoVerificacao;""")

(SAIDA / PAS).write_bytes(pas.encode("latin-1"))

# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------
partes = []
for nome in (LFM, PAS):
    r = subprocess.run(["diff", "-u", "--label", f"a/{REL}/{nome}", "--label", f"b/{REL}/{nome}",
                        str(ORIG / nome), str(SAIDA / nome)], capture_output=True)
    if r.returncode not in (0, 1):
        raise SystemExit(r.stderr.decode())
    partes.append(r.stdout)
cabecalho = (Path(__file__).with_name("0006-cabecalho.txt")).read_bytes()
PATCH.write_bytes(cabecalho + b"".join(partes))
print("patch:", PATCH, len(b"".join(partes)), "bytes")
