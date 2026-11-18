package acbr

import "os"

// configLogoNFSe devolve a chave que põe a marca da NFS-e no DANFSe.
//
// O layout do Padrão Nacional da lib (TfrlXDANFSeRLPadraoNacional) reserva o
// espaço da logo no topo à esquerda e a carrega de [DANFSe] LogoNFSe. Sem a
// chave o espaço fica em branco, e o PDF diverge do DANFSe oficial do ADN, que
// traz a marca ali. Os outros layouts (ABRASF, ISSNet...) ignoram a chave.
//
// Só manda a chave quando o arquivo existe: um caminho inválido a lib tentaria
// ler como o conteúdo da imagem. Fora da imagem Docker, a nota sai sem logo.
func configLogoNFSe(path string) []ConfigKV {
	if path == "" {
		return nil
	}
	if st, err := os.Stat(path); err != nil || st.IsDir() {
		return nil
	}
	return []ConfigKV{{Section: "DANFSe", Key: "LogoNFSe", Value: path}}
}

// configDANFSe reúne as chaves que aproximam o DANFSe local do oficial do ADN:
// a faixa de rodapé (data, identificação e assinatura, número e chave), que a lib
// só imprime com ImprimeCanhoto ligado, e a logo, quando há arquivo.
func configDANFSe(logo string) []ConfigKV {
	kvs := []ConfigKV{{Section: "DANFSe", Key: "ImprimeCanhoto", Value: "1"}}
	return append(kvs, configLogoNFSe(logo)...)
}
