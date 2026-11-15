/**
 * MAVUNQO Sound & Vibration Notification Engine
 * High-priority audio chimes using HTML5 Web Audio API (AudioContext)
 * Zero external sound file dependencies; runs directly in browser.
 */

class MavunqoAudioAlerts {
  constructor() {
    this.audioCtx = null;
    this.loopInterval = null;
    this.isAlerting = false;
    this.wakeLock = null;
  }

  initAudio() {
    if (!this.audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.audioCtx = new AudioContext();
      }
    }
    if (this.audioCtx && this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
  }

  // Request screen wake lock so phone/counter tablet doesn't go to sleep
  async requestWakeLock() {
    try {
      if ('wakeLock' in navigator) {
        this.wakeLock = await navigator.wakeLock.request('screen');
      }
    } catch (err) {
      console.log('Wake Lock request ignored or unsupported:', err);
    }
  }

  // Play a single high-pitch double cash register / chime sound
  playCashChime() {
    this.initAudio();
    if (!this.audioCtx) return;

    const ctx = this.audioCtx;
    const now = ctx.currentTime;

    // First Ping (e.g. 987.77 Hz - B5 note)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(987.77, now);
    gain1.gain.setValueAtTime(0.8, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.35);

    // Second Ping (High Cash Chime: 1760 Hz - A6 note)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(1760, now + 0.12);
    gain2.gain.setValueAtTime(0.9, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.65);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.65);

    // Trigger Phone Vibration
    if (navigator.vibrate) {
      navigator.vibrate([400, 150, 400]);
    }
  }

  // Play Driver Dispatch Radar Ping (sharp triple beep)
  playDriverPing() {
    this.initAudio();
    if (!this.audioCtx) return;

    const ctx = this.audioCtx;
    const now = ctx.currentTime;

    [0, 0.18, 0.36].forEach((delay, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'square';
      osc.frequency.setValueAtTime(1174.66 + (idx * 200), now + delay);
      gain.gain.setValueAtTime(0.6, now + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, now + delay + 0.14);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + delay);
      osc.stop(now + delay + 0.14);
    });

    if (navigator.vibrate) {
      navigator.vibrate([300, 100, 300, 100, 500]);
    }
  }

  // Start continuous repeating alarm until user stops it
  startLoopingAlert(type = 'merchant') {
    if (this.isAlerting) return;
    this.isAlerting = true;
    this.requestWakeLock();

    const playSound = () => {
      if (type === 'driver') {
        this.playDriverPing();
      } else {
        this.playCashChime();
      }
    };

    playSound();
    this.loopInterval = setInterval(playSound, 3800);
  }

  // Stop the alarm when user accepts or views the order
  stopAlert() {
    if (this.loopInterval) {
      clearInterval(this.loopInterval);
      this.loopInterval = null;
    }
    this.isAlerting = false;
  }
}

// Global singleton instance
window.mavunqoAudio = new MavunqoAudioAlerts();
