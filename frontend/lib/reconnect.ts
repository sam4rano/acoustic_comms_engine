export type ReconnectHandler = {
  onReconnect: (attempt: number) => void;
  onMaxAttempts: () => void;
};

export class WebSocketReconnector {
  private attempts = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private aborted = false;

  constructor(
    private readonly maxAttempts = 5,
    private readonly baseDelay = 1000,
  ) {}

  async connect(
    url: string,
    handlers: ReconnectHandler,
  ): Promise<WebSocket> {
    this.aborted = false;
    this.attempts = 0;

    while (this.attempts < this.maxAttempts) {
      try {
        return await this.tryConnect(url);
      } catch {
        this.attempts++;
        if (this.attempts >= this.maxAttempts) {
          handlers.onMaxAttempts();
          throw new Error("Max reconnection attempts reached");
        }
        handlers.onReconnect(this.attempts);
        await this.delay(this.backoff());
      }
    }

    throw new Error("Failed to connect");
  }

  abort(): void {
    this.aborted = true;
    if (this.timer) clearTimeout(this.timer);
  }

  private tryConnect(url: string): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      ws.onopen = () => resolve(ws);
      ws.onerror = () => reject(new Error("WebSocket connection failed"));
      const timeout = setTimeout(() => {
        ws.close();
        reject(new Error("WebSocket connection timeout"));
      }, 5000);
      ws.onopen = () => {
        clearTimeout(timeout);
        resolve(ws);
      };
    });
  }

  private backoff(): number {
    return this.baseDelay * Math.pow(2, this.attempts) + Math.random() * 500;
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => {
      this.timer = setTimeout(resolve, ms);
    });
  }
}
