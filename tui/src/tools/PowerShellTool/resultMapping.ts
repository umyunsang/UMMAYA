import type { ToolResultBlockParam } from '@anthropic-ai/sdk/resources/index.mjs';
import { getTaskOutputPath } from '../../utils/task/diskOutput.js';
import { buildLargeToolResultMessage, generatePreview, PREVIEW_SIZE_BYTES } from '../../utils/toolResultStorage.js';
import { buildImageToolResult } from '../BashTool/shellOutputUtils.js';
import type { Out } from './schemas.js';

const EOL = '\n';
const ASSISTANT_BLOCKING_BUDGET_MS = 15_000;

export function mapPowerShellToolResultToBlock({
  interrupted,
  stdout,
  stderr,
  isImage,
  persistedOutputPath,
  persistedOutputSize,
  backgroundTaskId,
  backgroundedByUser,
  assistantAutoBackgrounded
}: Out, toolUseID: string): ToolResultBlockParam {
  if (isImage) {
    const block = buildImageToolResult(stdout, toolUseID);
    if (block) return block;
  }
  let processedStdout = stdout;
  if (persistedOutputPath) {
    const trimmed = stdout ? stdout.replace(/^(\s*\n)+/, '').trimEnd() : '';
    const preview = generatePreview(trimmed, PREVIEW_SIZE_BYTES);
    processedStdout = buildLargeToolResultMessage({
      filepath: persistedOutputPath,
      originalSize: persistedOutputSize ?? 0,
      isJson: false,
      preview: preview.preview,
      hasMore: preview.hasMore
    });
  } else if (stdout) {
    processedStdout = stdout.replace(/^(\s*\n)+/, '').trimEnd();
  }
  let errorMessage = stderr.trim();
  if (interrupted) {
    if (stderr) errorMessage += EOL;
    errorMessage += '<error>Command was aborted before completion</error>';
  }
  const backgroundInfo = formatBackgroundInfo({
    backgroundTaskId,
    backgroundedByUser,
    assistantAutoBackgrounded
  });
  return {
    tool_use_id: toolUseID,
    type: 'tool_result' as const,
    content: [processedStdout, errorMessage, backgroundInfo].filter(Boolean).join('\n'),
    is_error: interrupted
  };
}

type BackgroundInfoInput = Pick<Out, 'backgroundTaskId' | 'backgroundedByUser' | 'assistantAutoBackgrounded'>;

function formatBackgroundInfo({
  backgroundTaskId,
  backgroundedByUser,
  assistantAutoBackgrounded
}: BackgroundInfoInput): string {
  if (!backgroundTaskId) {
    return '';
  }
  const outputPath = getTaskOutputPath(backgroundTaskId);
  if (assistantAutoBackgrounded) {
    return `Command exceeded the assistant-mode blocking budget (${ASSISTANT_BLOCKING_BUDGET_MS / 1000}s) and was moved to the background with ID: ${backgroundTaskId}. It is still running — you will be notified when it completes. Output is being written to: ${outputPath}. In assistant mode, delegate long-running work to a subagent or use run_in_background to keep this conversation responsive.`;
  }
  if (backgroundedByUser) {
    return `Command was manually backgrounded by user with ID: ${backgroundTaskId}. Output is being written to: ${outputPath}`;
  }
  return `Command running in background with ID: ${backgroundTaskId}. Output is being written to: ${outputPath}`;
}
