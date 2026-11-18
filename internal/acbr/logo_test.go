package acbr

import (
	"os"
	"path/filepath"
	"testing"
)

// A logo do DANFSe é a chave [DANFSe] LogoNFSe da lib. O layout do Padrão
// Nacional já reserva o espaço no topo à esquerda e a lê dali; vazia, a nota sai
// sem a marca da NFS-e, diferente do DANFSe oficial do ADN.
func TestConfigLogoNFSe(t *testing.T) {
	dir := t.TempDir()
	logo := filepath.Join(dir, "logo-nfse.jpg")
	if err := os.WriteFile(logo, []byte("\x89PNG"), 0o644); err != nil {
		t.Fatal(err)
	}

	t.Run("arquivo existe: vira a chave da lib", func(t *testing.T) {
		kvs := configLogoNFSe(logo)
		if len(kvs) != 1 {
			t.Fatalf("esperava 1 chave, veio %d: %+v", len(kvs), kvs)
		}
		want := ConfigKV{Section: "DANFSe", Key: "LogoNFSe", Value: logo}
		if kvs[0] != want {
			t.Fatalf("chave = %+v, quero %+v", kvs[0], want)
		}
	})

	// Fora da imagem (go run, testes com a lib no host) o arquivo não existe.
	// Passar à lib um caminho que não existe faz o CarregarLogo tentar lê-lo
	// como conteúdo: melhor não mandar nada e sair sem logo.
	t.Run("arquivo não existe: nada", func(t *testing.T) {
		if kvs := configLogoNFSe(filepath.Join(dir, "nao-existe.png")); kvs != nil {
			t.Fatalf("esperava nada, veio %+v", kvs)
		}
	})

	t.Run("caminho vazio desliga a logo", func(t *testing.T) {
		if kvs := configLogoNFSe(""); kvs != nil {
			t.Fatalf("esperava nada, veio %+v", kvs)
		}
	})

	// Um diretório no lugar do arquivo é erro de montagem, não logo.
	t.Run("diretório: nada", func(t *testing.T) {
		if kvs := configLogoNFSe(dir); kvs != nil {
			t.Fatalf("esperava nada, veio %+v", kvs)
		}
	})
}

// O DANFSe oficial do ADN fecha com a faixa "data / identificação e assinatura
// / número e chave". O layout da lib tem a mesma faixa (rlbCanhoto), mas só a
// imprime com [DANFSe] ImprimeCanhoto ligado, e o padrão é desligado.
func TestConfigDANFSeLigaOCanhotoEALogo(t *testing.T) {
	logo := filepath.Join(t.TempDir(), "logo-nfse.jpg")
	if err := os.WriteFile(logo, []byte("jpg"), 0o644); err != nil {
		t.Fatal(err)
	}
	kvs := configDANFSe(logo)
	quer := map[ConfigKV]bool{
		{Section: "DANFSe", Key: "ImprimeCanhoto", Value: "1"}: false,
		{Section: "DANFSe", Key: "LogoNFSe", Value: logo}:      false,
	}
	for _, kv := range kvs {
		if _, ok := quer[kv]; !ok {
			t.Fatalf("chave inesperada: %+v", kv)
		}
		quer[kv] = true
	}
	for kv, veio := range quer {
		if !veio {
			t.Fatalf("faltou %+v em %+v", kv, kvs)
		}
	}

	// Sem logo, o canhoto continua.
	kvs = configDANFSe("")
	if len(kvs) != 1 || kvs[0].Key != "ImprimeCanhoto" {
		t.Fatalf("sem logo, esperava só o canhoto: %+v", kvs)
	}
}
