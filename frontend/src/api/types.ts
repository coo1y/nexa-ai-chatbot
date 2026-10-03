/**
 * API types. Everything here is derived from the generated OpenAPI types so that the
 * frontend cannot drift from the contract in ../../openapi.yaml.
 */
import type { components } from './schema.gen';

type Schemas = components['schemas'];

export type Capability = Schemas['Capability'];
export type CapabilityChoice = Schemas['CapabilityChoice'];
export type ChatRequest = Schemas['ChatRequest'];
export type ChatMessagePayload = Schemas['ChatMessage'];
export type FileMeta = Schemas['FileMeta'];
export type FeedbackRequest = Schemas['FeedbackRequest'];
export type FeedbackResponse = Schemas['FeedbackResponse'];
export type HealthResponse = Schemas['HealthResponse'];
export type CapabilitiesResponse = Schemas['CapabilitiesResponse'];
export type ErrorResponse = Schemas['ErrorResponse'];
export type RoutingInfo = Schemas['RoutingInfo'];
export type Source = Schemas['Source'];

export interface StreamEventMap {
  start: Schemas['StartEvent'];
  delta: Schemas['DeltaEvent'];
  tool_call: Schemas['ToolCallEvent'];
  tool_result: Schemas['ToolResultEvent'];
  sources: Schemas['SourcesEvent'];
  safety: Schemas['SafetyEvent'];
  error: Schemas['ErrorEvent'];
  done: Schemas['DoneEvent'];
}

export type StreamEventName = keyof StreamEventMap;

export type StreamEvent = {
  [K in StreamEventName]: { event: K; data: StreamEventMap[K] };
}[StreamEventName];

export const STREAM_EVENT_NAMES: readonly StreamEventName[] = [
  'start',
  'delta',
  'tool_call',
  'tool_result',
  'sources',
  'safety',
  'error',
  'done',
];
