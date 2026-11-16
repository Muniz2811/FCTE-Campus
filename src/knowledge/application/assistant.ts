export interface KnowledgeQuestion { text: string; campus: 'gama'; placeId?: string; previousRequestId?: string }
export interface KnowledgeSource { id: string; title: string; excerpt: string; url?: string; section?: string; version: string;
  sourceId?: string; reviewedAt?: string; validUntil?: string; distance?: number; lexicalScore?: number }
export interface KnowledgeMeta { requestId?: string; model?: string; baseVersion?: string; retrieved?: KnowledgeSource[];
  retrievalProfile?: string; retrievalMethod?: string }
export type KnowledgeResult = (
  | { status: 'answered'; answer: string; sources: KnowledgeSource[] }
  | { status: 'insufficient'; message: string }
  | { status: 'unavailable'; message: string }) & KnowledgeMeta;
export type AssistantHealth = { status: 'loading' | 'idle' }
  | { status: 'unavailable'; message: string }
  | { status: 'ready'; generationConfigured: boolean; sources: number; chunks: number; model: string };
export interface CampusAssistant {
  availability: 'available' | 'unavailable';
  ask(question: KnowledgeQuestion, signal?: AbortSignal): Promise<KnowledgeResult>;
}
