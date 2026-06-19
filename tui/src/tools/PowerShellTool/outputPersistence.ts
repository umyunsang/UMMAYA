import { copyFile, link, stat as fsStat, truncate as fsTruncate } from 'fs/promises';
import type { ExecResult } from '../../utils/ShellCommand.js';
import { ensureToolResultsDir, getToolResultPath } from '../../utils/toolResultStorage.js';

const MAX_PERSISTED_SIZE = 64 * 1024 * 1024;

type PersistedOutput = {
  readonly path?: string;
  readonly size?: number;
};

export async function persistLargePowerShellOutput(result: ExecResult): Promise<PersistedOutput> {
  if (!result.outputFilePath || !result.outputTaskId) {
    return {};
  }
  try {
    const fileStat = await fsStat(result.outputFilePath);
    await ensureToolResultsDir();
    const dest = getToolResultPath(result.outputTaskId, false);
    if (fileStat.size > MAX_PERSISTED_SIZE) {
      await fsTruncate(result.outputFilePath, MAX_PERSISTED_SIZE);
    }
    try {
      await link(result.outputFilePath, dest);
    } catch (error) {
      if (error instanceof Error) {
        await copyFile(result.outputFilePath, dest);
      } else {
        throw error;
      }
    }
    return {
      path: dest,
      size: fileStat.size
    };
  } catch (error) {
    if (error instanceof Error) {
      return {};
    }
    throw error;
  }
}
