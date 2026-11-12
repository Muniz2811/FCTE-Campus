import { useCallback, useEffect, useRef, useState } from 'react';
import type { Coordinate } from '../domain/place';
export type LocationState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; coordinate: Coordinate; accuracy: number };
export function useLocation() {
  const [location, setLocation] = useState<LocationState>({ status: 'idle' });
  const generation = useRef(0);
  useEffect(() => () => { generation.current++; }, []);
  const request = useCallback(() => {
    const requestId = ++generation.current;
    if (!window.isSecureContext || !navigator.geolocation) {
      setLocation({ status: 'error', message: 'A localização precisa de HTTPS e de um navegador compatível.' });
      return;
    }
    setLocation({ status: 'loading' });
    navigator.geolocation.getCurrentPosition(position => {
      if (requestId !== generation.current) return;
      setLocation({ status: 'ready', coordinate: { latitude: position.coords.latitude,
        longitude: position.coords.longitude }, accuracy: position.coords.accuracy });
    }, error => {
      if (requestId !== generation.current) return;
      const message = error.code === 1 ? 'Localização não autorizada. Libere a permissão no navegador e tente de novo.'
        : error.code === 3 ? 'O GPS demorou a responder. Vá para um lugar aberto e tente novamente.'
          : 'Não foi possível obter sua localização. Tente de novo em um lugar aberto.';
      setLocation({ status: 'error', message });
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  }, []);
  return { location, request };
}
