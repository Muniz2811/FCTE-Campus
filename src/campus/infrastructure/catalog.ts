import snapshot from './campus.json';
import { validatePlaces, type Place } from '../domain/place';

export const places = snapshot.places as Place[];
validatePlaces(places);
export const catalogSource = snapshot.source;
