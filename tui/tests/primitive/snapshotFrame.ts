const CSI_ESCAPE_SEQUENCE = /\x1B\[[0-?]*[ -/]*[@-~]/g

export function stripSnapshotAnsi(frame: string): string {
  return frame.replace(CSI_ESCAPE_SEQUENCE, '')
}
