package acbr

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/4devsmart/wrapper-api/internal/platform/config"
)

// gsFalso grava um executável que faz o papel do Ghostscript: lê o PDF do último
// argumento e escreve em -sOutputFile= o que o corpo do script mandar.
func gsFalso(t *testing.T, corpo string) string {
	t.Helper()
	bin := filepath.Join(t.TempDir(), "gs")
	script := "#!/bin/sh\nset -eu\nfor a in \"$@\"; do case \"$a\" in -sOutputFile=*) out=\"${a#-sOutputFile=}\";; esac; in=\"$a\"; done\n" + corpo + "\n"
	if err := os.WriteFile(bin, []byte(script), 0o755); err != nil {
		t.Fatal(err)
	}
	return bin
}

const pdfDaLib = "%PDF-1.2\nPDF do FortesReport, fontes só nomeadas\n%%EOF\n"

func TestEmbutidor_DevolveOQueOGhostscriptEscreveu(t *testing.T) {
	bin := gsFalso(t, `{ echo "%PDF-1.4"; echo "embutido"; cat "$in"; } > "$out"`)
	e := EmbutidorDeFontes{Binario: bin, Prazo: 5 * time.Second}

	saida, err := e.Embutir(context.Background(), []byte(pdfDaLib))
	if err != nil {
		t.Fatalf("Embutir: %v", err)
	}
	if !bytes.HasPrefix(saida, []byte("%PDF-1.4\nembutido\n")) {
		t.Fatalf("saída não é a do gs: %q", saida)
	}
	// O PDF de entrada chegou inteiro ao gs.
	if !bytes.Contains(saida, []byte(pdfDaLib)) {
		t.Fatalf("o gs não recebeu o PDF da lib: %q", saida)
	}
}

func TestEmbutidor_ErrosNaoDevolvemPDF(t *testing.T) {
	casos := map[string]struct {
		corpo string
		prazo time.Duration
	}{
		"gs sai com erro":        {corpo: `echo "Error: /undefinedfilename" >&2; exit 1`, prazo: 5 * time.Second},
		"saída não é PDF":        {corpo: `echo "lixo" > "$out"`, prazo: 5 * time.Second},
		"saída vazia":            {corpo: `: > "$out"`, prazo: 5 * time.Second},
		"gs estoura o prazo":     {corpo: `sleep 5; cat "$in" > "$out"`, prazo: 200 * time.Millisecond},
		"gs não escreve a saída": {corpo: `true`, prazo: 5 * time.Second},
	}
	for nome, c := range casos {
		t.Run(nome, func(t *testing.T) {
			e := EmbutidorDeFontes{Binario: gsFalso(t, c.corpo), Prazo: c.prazo}
			inicio := time.Now()
			saida, err := e.Embutir(context.Background(), []byte(pdfDaLib))
			if err == nil {
				t.Fatalf("esperava erro, veio %q", saida)
			}
			if saida != nil {
				t.Fatalf("com erro não devolve PDF, veio %q", saida)
			}
			if time.Since(inicio) > 3*time.Second {
				t.Fatalf("o prazo não foi respeitado: %v", time.Since(inicio))
			}
		})
	}
}

func TestEmbutidor_BinarioInexistente(t *testing.T) {
	e := EmbutidorDeFontes{Binario: filepath.Join(t.TempDir(), "nao-existe"), Prazo: time.Second}
	if _, err := e.Embutir(context.Background(), []byte(pdfDaLib)); err == nil {
		t.Fatal("esperava erro com binário inexistente")
	}
}

// Contra o Ghostscript de verdade: um PDF que só nomeia a Arial, como o
// FortesReport, sai com ela dentro. É o defeito que isto corrige: fonte só
// nomeada, e cada leitor desenhando o DANFSe com a que tiver. A conferência é
// pelo pdffonts porque o gs grava os objetos comprimidos (/ObjStm), e procurar
// /FontFile nos bytes não acharia nada. Helvetica não serve de exemplo: é uma das
// 14 fontes-padrão do PDF, que o gs nunca embute.
func TestEmbutidor_GhostscriptRealEmbuteAFonte(t *testing.T) {
	bin, err := exec.LookPath("gs")
	if err != nil {
		t.Skip("gs não instalado")
	}
	pdffonts, err := exec.LookPath("pdffonts")
	if err != nil {
		t.Skip("pdffonts (poppler-utils) não instalado")
	}
	e := EmbutidorDeFontes{Binario: bin, Prazo: 30 * time.Second}
	saida, err := e.Embutir(context.Background(), pdfComFonteSoNomeada())
	if err != nil {
		t.Fatalf("Embutir: %v", err)
	}
	arq := filepath.Join(t.TempDir(), "saida.pdf")
	if err := os.WriteFile(arq, saida, 0o600); err != nil {
		t.Fatal(err)
	}
	lista, err := exec.Command(pdffonts, arq).CombinedOutput()
	if err != nil {
		t.Fatalf("pdffonts: %v: %s", err, lista)
	}
	// pdffonts: nome, tipo, codificação, emb, sub, uni, objeto.
	for _, l := range strings.Split(string(lista), "\n") {
		if c := strings.Fields(l); len(c) >= 4 && strings.HasSuffix(c[0], "Arial") {
			if c[3] != "yes" {
				t.Fatalf("Arial não foi embutida:\n%s", lista)
			}
			return
		}
	}
	t.Fatalf("Arial sumiu do PDF:\n%s", lista)
}

// pdfComFonteSoNomeada monta um PDF mínimo que usa a Arial sem embuti-la,
// como o FortesReport faz com Arial e Microsoft Sans Serif.
func pdfComFonteSoNomeada() []byte {
	conteudo := "BT /F1 12 Tf 72 720 Td (Prestador do Servico) Tj ET"
	objs := []string{
		"<< /Type /Catalog /Pages 2 0 R >>",
		"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
		"<< /Type /Font /Subtype /TrueType /BaseFont /Arial /FirstChar 32 /LastChar 126 /Encoding /WinAnsiEncoding >>",
		"<< /Length " + itoa(len(conteudo)) + " >>\nstream\n" + conteudo + "\nendstream",
	}
	var b strings.Builder
	b.WriteString("%PDF-1.4\n")
	offs := make([]int, len(objs))
	for i, o := range objs {
		offs[i] = b.Len()
		b.WriteString(itoa(i+1) + " 0 obj\n" + o + "\nendobj\n")
	}
	xref := b.Len()
	b.WriteString("xref\n0 " + itoa(len(objs)+1) + "\n0000000000 65535 f \n")
	for _, o := range offs {
		s := itoa(o)
		b.WriteString(strings.Repeat("0", 10-len(s)) + s + " 00000 n \n")
	}
	b.WriteString("trailer\n<< /Size " + itoa(len(objs)+1) + " /Root 1 0 R >>\nstartxref\n" + itoa(xref) + "\n%%EOF\n")
	return []byte(b.String())
}

func itoa(n int) string { return strconv.Itoa(n) }

// --- no worker: todo PDF que sai da lib passa pelo embutidor ---

type embutidorFake struct {
	saida    []byte
	err      error
	chamadas int
}

func (e *embutidorFake) Embutir(_ context.Context, pdf []byte) ([]byte, error) {
	e.chamadas++
	if e.err != nil {
		return nil, e.err
	}
	return append(append([]byte{}, e.saida...), pdf...), nil
}

func chamarRPC(t *testing.T, h http.Handler, p Pedido) Resposta {
	t.Helper()
	corpo, _ := json.Marshal(p)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, RotaRPC, bytes.NewReader(corpo)))
	var r Resposta
	if err := json.Unmarshal(rec.Body.Bytes(), &r); err != nil {
		t.Fatalf("resposta não é JSON (%d): %s", rec.Code, rec.Body.String())
	}
	return r
}

func TestRPC_PDFPassaPeloEmbutidor(t *testing.T) {
	f := &servicoFake{result: Result{PDF: []byte(pdfDaLib)}}
	emb := &embutidorFake{saida: []byte("EMBUTIDO:")}
	h, _ := RPCHandler(servicosFake(f), 1, 0, ComEmbutidorDeFontes(emb))

	r := chamarRPC(t, h, Pedido{Servico: ServicoNFSe, Metodo: "Emitir"})
	if string(r.PDF) != "EMBUTIDO:"+pdfDaLib {
		t.Fatalf("PDF não passou pelo embutidor: %q", r.PDF)
	}
	if emb.chamadas != 1 {
		t.Fatalf("embutidor chamado %d vezes", emb.chamadas)
	}
}

// Um PDF sem fonte embutida ainda é o documento: perder o DANFSe porque o gs
// falhou seria pior que entregá-lo como a lib o gerou.
func TestRPC_FalhaDoEmbutidorDevolveOPDFDaLib(t *testing.T) {
	f := &servicoFake{result: Result{PDF: []byte(pdfDaLib)}}
	emb := &embutidorFake{err: errors.New("gs: exit status 1")}
	h, _ := RPCHandler(servicosFake(f), 1, 0, ComEmbutidorDeFontes(emb))

	r := chamarRPC(t, h, Pedido{Servico: ServicoNFSe, Metodo: "Emitir"})
	if string(r.PDF) != pdfDaLib {
		t.Fatalf("com o embutidor falhando, esperava o PDF da lib, veio %q", r.PDF)
	}
	if r.Erro != "" {
		t.Fatalf("falha do embutidor não é erro da chamada: %q", r.Erro)
	}
}

func TestRPC_RespostaSemPDFNaoChamaOEmbutidor(t *testing.T) {
	f := &servicoFake{result: Result{XML: "<DPS/>"}}
	emb := &embutidorFake{saida: []byte("EMBUTIDO:")}
	h, _ := RPCHandler(servicosFake(f), 1, 0, ComEmbutidorDeFontes(emb))

	r := chamarRPC(t, h, Pedido{Servico: ServicoNFSe, Metodo: "Emitir"})
	if r.XML != "<DPS/>" || len(r.PDF) != 0 {
		t.Fatalf("resposta alterada: %+v", r)
	}
	if emb.chamadas != 0 {
		t.Fatalf("embutidor chamado sem PDF: %d", emb.chamadas)
	}
}

// Sem a opção, o PDF sai como a lib o gerou (os testes e o worker sem gs).
func TestRPC_SemEmbutidorOPDFSaiComoALibGerou(t *testing.T) {
	f := &servicoFake{result: Result{PDF: []byte(pdfDaLib)}}
	h, _ := RPCHandler(servicosFake(f), 1, 0)
	r := chamarRPC(t, h, Pedido{Servico: ServicoNFSe, Metodo: "Emitir"})
	if string(r.PDF) != pdfDaLib {
		t.Fatalf("PDF alterado sem embutidor: %q", r.PDF)
	}
}

func TestOpcoesDoWorker(t *testing.T) {
	if op := OpcoesDoWorker(config.ACBr{PDFGhostscript: ""}); op != nil {
		t.Fatalf("ACBR_PDF_GS vazio devia desligar, veio %d opções", len(op))
	}
	if op := OpcoesDoWorker(config.ACBr{PDFGhostscript: filepath.Join(t.TempDir(), "nao-existe")}); op != nil {
		t.Fatalf("gs ausente devia desligar, veio %d opções", len(op))
	}
	bin := gsFalso(t, `cat "$in" > "$out"`)
	if op := OpcoesDoWorker(config.ACBr{PDFGhostscript: bin}); len(op) != 1 {
		t.Fatalf("gs presente devia ligar o embutidor, veio %d opções", len(op))
	}
}
