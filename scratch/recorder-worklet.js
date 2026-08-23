class Recorder extends AudioWorkletProcessor {
  constructor() {
    super();
    this.running = false;
    this.blocks = [];
    this.held = 0;
    this.peak = 0;
    this.ticks = 0;
    this.port.onmessage = (event) => {
      if (event.data === "start") {
        this.running = true;
        this.blocks = [];
        this.held = 0;
      } else if (event.data === "stop") {
        this.running = false;
        this.flush(true);
      }
    };
  }

  flush(final) {
    let samples = null;
    if (this.held) {
      samples = new Float32Array(this.held);
      let at = 0;
      for (const block of this.blocks) {
        samples.set(block, at);
        at += block.length;
      }
    }
    this.blocks = [];
    this.held = 0;
    this.port.postMessage({ peak: this.peak, samples, final: Boolean(final) });
    this.peak = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    let peak = 0;
    for (let i = 0; i < channel.length; i++) {
      const sample = Math.abs(channel[i]);
      if (sample > peak) peak = sample;
    }
    if (peak > this.peak) this.peak = peak;

    if (this.running) {
      this.blocks.push(new Float32Array(channel));
      this.held += channel.length;
    }
    if (++this.ticks % 8 === 0) this.flush(false);
    return true;
  }
}

registerProcessor("recorder", Recorder);
