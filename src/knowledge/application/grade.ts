export type GradeDay = 'seg' | 'ter' | 'qua' | 'qui' | 'sex' | 'sab';
export interface GradeMeeting { day: GradeDay; start: string; end: string }
export interface GradeIssue { code: string; message: string }
/** Local confirmado pela base do campus; `floor` fica vazio quando a fonte confirma só o prédio. */
export interface GradePlace { text: string; building: string; floor?: string; environmentId?: string;
  precision: 'ambiente' | 'predio'; sourceId: string; sourceTitle: string; version: string }
export interface GradeClass { code: string; name?: string; hours?: number; group?: string; status?: string;
  meetings: GradeMeeting[]; declaredPlace?: string; places: GradePlace[]; issues: GradeIssue[] }
export interface GradeCitation { n: number; origin: 'comprovante' | 'base'; reference: string; excerpt: string; version?: string }
export type GradeAnswerStatus = 'respondida' | 'insuficiente' | 'sem_pergunta' | 'indisponivel';
export interface GradeResult { period?: string; origin: string; classes: GradeClass[]; issues: GradeIssue[];
  question?: string; answer?: string; answerStatus: GradeAnswerStatus; citations: GradeCitation[] }
export type GradeOutcome = { status: 'ok'; result: GradeResult } | { status: 'unavailable'; message: string };
export interface GradeReader {
  read(file: File, question: string | undefined, signal?: AbortSignal): Promise<GradeOutcome>;
}
export const GRADE_MAX_BYTES = 8 * 1024 * 1024;
