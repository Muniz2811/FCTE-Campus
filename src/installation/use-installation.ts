import { useCallback, useEffect, useState } from 'react';
interface InstallPrompt extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}
const standalone = () => window.matchMedia('(display-mode: standalone)').matches ||
  (navigator as Navigator & { standalone?: boolean }).standalone === true;
export function useInstallation() {
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [installed, setInstalled] = useState(standalone);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  useEffect(() => {
    const receive = (event: Event) => { event.preventDefault(); setPrompt(event as InstallPrompt); };
    const done = () => { setInstalled(true); setPrompt(null); setNotice('Aplicativo instalado.'); };
    window.addEventListener('beforeinstallprompt', receive);
    window.addEventListener('appinstalled', done);
    return () => { window.removeEventListener('beforeinstallprompt', receive); window.removeEventListener('appinstalled', done); };
  }, []);
  const install = useCallback(async () => {
    if (!prompt) return;
    setBusy(true);
    try {
      await prompt.prompt();
      const result = await prompt.userChoice;
      setNotice(result.outcome === 'accepted' ? 'Instalação solicitada ao navegador.' : 'Você pode instalar mais tarde.');
      setPrompt(null);
    } catch { setNotice('Abra o menu do navegador e procure a opção de instalar.'); }
    finally { setBusy(false); }
  }, [prompt]);
  return { open, setOpen, installed, canPrompt: !!prompt, busy, notice, install };
}
