import { Building2, DoorOpen, Trees, ParkingCircle, FlaskConical, MapPin } from 'lucide-react';
import type { Category } from '../campus/domain/place';
const icons = { building: Building2, entrance: DoorOpen, outdoor: Trees, parking: ParkingCircle, laboratory: FlaskConical, service: MapPin };
export function PlaceIcon({ category, size = 21 }: { category: Category; size?: number }) {
  const Icon = icons[category];
  return <Icon size={size} strokeWidth={1.8} aria-hidden="true" />;
}
