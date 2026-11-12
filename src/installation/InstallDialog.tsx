import { Download, ExternalLink, Smartphone, X } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { useInstallation } from './use-installation';
type Installation = ReturnType<typeof useInstallation>;
export function InstallDialog({ installation }: { installation: Installation }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const element = dialog.current;
    if (installation.open) { previousFocus.current = document.activeElement as HTMLElement; element?.showModal(); }
    else if (element?.open) { element.close(); previousFocus.current?.focus(); }
  }, [installation.open]);
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  return <dialog ref={dialog} className="install-dialog" onCancel={() => installation.setOpen(false)} onClick={event => { if (event.target === dialog.current) installation.setOpen(false); }} aria-labelledby="install-heading">
    <button className="icon-button dialog-close" aria-label="Fechar instruções de instalação" onClick={() => installation.setOpen(false)}><X size={21} /></button>
    <div className="install-illustration"><Smartphone size={42} /><span className="install-mini-brand">F</span></div>
    <h2 id="install-heading">O campus na sua tela.</h2>
    <p>{installation.installed ? 'Você já está usando o aplicativo instalado.' : 'Adicione o FCTE Campus à tela inicial para abrir com um toque.'}</p>
    {installation.canPrompt && !installation.installed ? <button className="primary-button" disabled={installation.busy} onClick={installation.install}><Download size={18} />{installation.busy ? 'Abrindo instalação…' : 'Instalar FCTE Campus'}</button>
      : !installation.installed && <div className="install-instructions">{ios ? <p>No Safari, toque em <strong>Compartilhar</strong> e em <strong>Adicionar à Tela de Início</strong>.</p> : <p>Abra o menu do navegador e procure <strong>Instalar aplicativo</strong> ou <strong>Adicionar à tela inicial</strong>. A opção depende do navegador e de acesso por HTTPS.</p>}</div>}
    <p className="small-copy">A lista de locais e os favoritos podem ser abertos offline após a primeira visita. O mapa-base e os links externos precisam de internet.</p>
    <p className="project-credit">Projeto acadêmico do Grupo 09. Não é um serviço oficial da UnB.</p>
    <a className="text-button" href="https://fcte.unb.br/" target="_blank" rel="noreferrer">Portal oficial da FCTE <ExternalLink size={15} /><span className="sr-only"> (nova aba)</span></a>
    <p role="status">{installation.notice}</p>
  </dialog>;
}
