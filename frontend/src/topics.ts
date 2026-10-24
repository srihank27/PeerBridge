import { useSyncExternalStore } from 'react';
import type { SupportedTopic } from './types';

let catalog: SupportedTopic[] = [];
const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export function setTopicCatalog(topics: SupportedTopic[]) { catalog = topics; listeners.forEach(listener => listener()); }
export function useTopics() { return useSyncExternalStore(subscribe, () => catalog); }
export const label = (value: string | null | undefined) => value ? (catalog.find(t => t.id === value)?.label || value.replaceAll('_', ' ').replace(/^\w/, c => c.toUpperCase())) : 'Unclassified';
