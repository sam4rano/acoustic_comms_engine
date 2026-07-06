export class AudioEncoder {
  private readonly sampleRate: number;
  private readonly bufferSize: number;
  private buffer: Float32Array[];
  private sequence: number;

  constructor(sampleRate = 16000, bufferSize = 4096) {
    this.sampleRate = sampleRate;
    this.bufferSize = bufferSize;
    this.buffer = [];
    this.sequence = 0;
  }

  feed(chunk: Float32Array): void {
    this.buffer.push(chunk);
  }

  encode(): { sequence: number; data: string; sample_rate: number } | null {
    if (this.buffer.length === 0) return null;

    const total = this.buffer.reduce((s, c) => s + c.length, 0);
    const merged = new Float32Array(total);
    let offset = 0;
    for (const chunk of this.buffer) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    const bytes = new Uint8Array(merged.buffer);
    const binary = String.fromCharCode(...bytes);
    const data = btoa(binary);

    this.buffer = [];
    const seq = this.sequence++;
    return { sequence: seq, data, sample_rate: this.sampleRate };
  }

  reset(): void {
    this.buffer = [];
    this.sequence = 0;
  }
}
