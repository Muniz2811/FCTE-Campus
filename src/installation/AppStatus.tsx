import { useEffect, useState } from 'react';
import { RefreshCw, WifiOff, X } from 'lucide-react';
import { useRegisterSW } from 'virtual:pwa-register/react';
export function AppStatus() {
  const [online, setOnline] = useState(navigator.onLine);
  const [workerError, setWorkerError] = useState(false);
  const { needRefresh: [needRefresh, setNeedRefresh], updateServiceWorker } = useRegisterSW({
    onRegisterError() { setWorkerError(true); },
  });
  useEffect(() => {
    const sync = () => setOnline(navigator.onLine);
    window.addEventListener('online', sync); window.addEventListener('offline', sync);
    return () => { window.removeEventListener('online', sync); window.removeEventListener('offline', sync); };
  }, []);
  if (!online) return <div className="app-status" role="status"><WifiOff size={17} /><span>Você está offline. A lista de locais e seus salvos continuam aqui.</span></div>;
  if (needRefresh) return <div className="app-status" role="status"><RefreshCw size={17} /><span>Uma nova versão está pronta.</span>
    <button onClick={() => void updateServiceWorker(true)}>Atualizar</button><button aria-label="Atualizar mais tarde" onClick={() => setNeedRefresh(false)}><X size={16} /></button></div>;
  if (workerError) return <div className="app-status" role="status"><span>O modo offline não foi ativado nesta visita.</span><button aria-label="Fechar aviso" onClick={() => setWorkerError(false)}><X size={16} /></button></div>;
  return null;
}
