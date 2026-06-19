import { z } from 'zod/v4';
import { isEnvTruthy } from '../../utils/envUtils.js';
import { lazySchema } from '../../utils/lazySchema.js';
import { semanticBoolean } from '../../utils/semanticBoolean.js';
import { semanticNumber } from '../../utils/semanticNumber.js';
import { getMaxBashTimeoutMs } from '../../utils/timeouts.js';

export const isBackgroundTasksDisabled =
  // eslint-disable-next-line custom-rules/no-process-env-top-level -- Intentional: schema must be defined at module load
  isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_BACKGROUND_TASKS);

export const fullInputSchema = lazySchema(() => z.strictObject({
  command: z.string().describe('The PowerShell command to execute'),
  timeout: semanticNumber(z.number().optional()).describe(`Optional timeout in milliseconds (max ${getMaxBashTimeoutMs()})`),
  description: z.string().optional().describe('Clear, concise description of what this command does in active voice.'),
  run_in_background: semanticBoolean(z.boolean().optional()).describe(`Set to true to run this command in the background. Use Read to read the output later.`),
  dangerouslyDisableSandbox: semanticBoolean(z.boolean().optional()).describe('Set this to true to dangerously override sandbox mode and run commands without sandboxing.')
}));

export const inputSchema = lazySchema(() => isBackgroundTasksDisabled ? fullInputSchema().omit({
  run_in_background: true
}) : fullInputSchema());

export const outputSchema = lazySchema(() => z.object({
  stdout: z.string().describe('The standard output of the command'),
  stderr: z.string().describe('The standard error output of the command'),
  interrupted: z.boolean().describe('Whether the command was interrupted'),
  returnCodeInterpretation: z.string().optional().describe('Semantic interpretation for non-error exit codes with special meaning'),
  isImage: z.boolean().optional().describe('Flag to indicate if stdout contains image data'),
  persistedOutputPath: z.string().optional().describe('Path to persisted full output when too large for inline'),
  persistedOutputSize: z.number().optional().describe('Total output size in bytes when persisted'),
  backgroundTaskId: z.string().optional().describe('ID of the background task if command is running in background'),
  backgroundedByUser: z.boolean().optional().describe('True if the user manually backgrounded the command with Ctrl+B'),
  assistantAutoBackgrounded: z.boolean().optional().describe('True if the command was auto-backgrounded by the assistant-mode blocking budget')
}));

export type InputSchema = ReturnType<typeof inputSchema>;
export type PowerShellToolInput = z.infer<ReturnType<typeof fullInputSchema>>;
export type OutputSchema = ReturnType<typeof outputSchema>;
export type Out = z.infer<OutputSchema>;
