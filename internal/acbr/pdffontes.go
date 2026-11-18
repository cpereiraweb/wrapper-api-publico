package acbr

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/4devsmart/wrapper-api/internal/platform/config"
)

// EmbutidorDeFontes reprocessa no Ghostscript o PDF que a lib gerou, para que as
// fontes passem a ir DENTRO dele.
//
// O FortesReport só nomeia as fontes (Arial, Microsoft Sans Serif) e posiciona
// cada letra com as métricas da fonte que o servidor tem. Sem a fonte no
// arquivo, o leitor desenha com a que tiver, e o texto desalinha: "NFS -e
// Gerada", "Prestador do S erviço". O pdfwrite embute a fonte que o fontconfig
// do servidor resolveu, a mesma das métricas, e o PDF sai igual em qualquer
// leitor. Vale para todo PDF da lib (DANFSe, DACTE, DAMDFE, boleto).
type EmbutidorDeFontes struct {
	Binario string        // caminho do gs
	Prazo   time.Duration // teto por PDF; estourado, o processo é morto
}

// Embutir devolve o PDF com as fontes embutidas, ou erro e nil. Quem chama
// decide o que fazer com o original: no worker, ele segue como a lib o gerou.
func (e EmbutidorDeFontes) Embutir(ctx context.Context, pdf []byte) ([]byte, error) {
	if e.Prazo > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, e.Prazo)
		defer cancel()
	}

	// Arquivos, e não pipe: o PDF é lido por acesso aleatório (xref no fim), e o
	// gs copiaria o stdin para um temporário do mesmo jeito.
	dir, err := os.MkdirTemp("", "pdffontes-")
	if err != nil {
		return nil, fmt.Errorf("pdffontes: diretório temporário: %w", err)
	}
	defer func() { _ = os.RemoveAll(dir) }()
	entrada, saida := filepath.Join(dir, "in.pdf"), filepath.Join(dir, "out.pdf")
	if err := os.WriteFile(entrada, pdf, 0o600); err != nil {
		return nil, fmt.Errorf("pdffontes: gravando a entrada: %w", err)
	}

	cmd := exec.CommandContext(ctx, e.Binario,
		"-q", "-dNOPAUSE", "-dBATCH",
		// -dSAFER: o PDF vem da lib, mas o texto dele vem do cliente. Sem ele o
		// PostScript embutido poderia ler e escrever arquivos do worker.
		"-dSAFER",
		"-sDEVICE=pdfwrite",
		"-dEmbedAllFonts=true", "-dSubsetFonts=true",
		// Mantém a página como a lib a montou: sem girar e sem reamostrar a logo.
		"-dAutoRotatePages=/None",
		"-sOutputFile="+saida,
		entrada,
	)
	cmd.Dir = dir
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	// Morto pelo prazo, o gs pode ter deixado filhos segurando o stderr.
	cmd.WaitDelay = time.Second
	if err := cmd.Run(); err != nil {
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return nil, fmt.Errorf("pdffontes: gs passou de %s", e.Prazo)
		}
		return nil, fmt.Errorf("pdffontes: gs: %w: %s", err, strings.TrimSpace(stderr.String()))
	}

	out, err := os.ReadFile(saida)
	if err != nil {
		return nil, fmt.Errorf("pdffontes: gs não gravou a saída: %w", err)
	}
	if !bytes.HasPrefix(out, []byte("%PDF-")) {
		return nil, errors.New("pdffontes: a saída do gs não é PDF")
	}
	return out, nil
}

// embutidor é o que o RPCHandler usa; a interface deixa o teste trocá-lo.
type embutidor interface {
	Embutir(ctx context.Context, pdf []byte) ([]byte, error)
}

// OpcaoRPC configura o RPCHandler.
type OpcaoRPC func(*opcoesRPC)

type opcoesRPC struct {
	fontes embutidor
}

// ComEmbutidorDeFontes faz todo PDF que sai do worker passar pelo embutidor.
// Se ele falhar, o PDF segue como a lib o gerou: sem a fonte dentro ainda é o
// documento, e perdê-lo por isso seria pior.
func ComEmbutidorDeFontes(e embutidor) OpcaoRPC {
	return func(o *opcoesRPC) { o.fontes = e }
}

// prazoDoGs é o teto por PDF. Um DANFSe leva décimos de segundo; o teto só
// existe para um gs travado não segurar a vaga do worker até o fim da chamada.
const prazoDoGs = 30 * time.Second

// OpcoesDoWorker monta as opções do RPCHandler a partir da configuração. Sem o
// gs (ACBR_PDF_GS=off, ou binário ausente, como fora da imagem), o worker sobe
// do mesmo jeito e os PDFs saem como a lib os gera, com o motivo no log.
func OpcoesDoWorker(cfg config.ACBr) []OpcaoRPC {
	if cfg.PDFGhostscript == "" {
		slog.Info("fontes dos PDFs não serão embutidas: ACBR_PDF_GS=off")
		return nil
	}
	bin, err := exec.LookPath(cfg.PDFGhostscript)
	if err != nil {
		slog.Warn("fontes dos PDFs não serão embutidas: gs não encontrado", "ACBR_PDF_GS", cfg.PDFGhostscript, "err", err)
		return nil
	}
	slog.Info("fontes dos PDFs serão embutidas", "gs", bin)
	return []OpcaoRPC{ComEmbutidorDeFontes(EmbutidorDeFontes{Binario: bin, Prazo: prazoDoGs})}
}
