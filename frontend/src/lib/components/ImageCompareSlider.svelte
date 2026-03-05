<script lang="ts">
  export let aiUrl: string;
  export let originalUrl: string;

  let sliderPercent = 50;
  let container: HTMLDivElement;
  let active = false;

  function getPercent(clientX: number): number {
    const rect = container.getBoundingClientRect();
    return Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
  }

  function onPointerDown(e: PointerEvent) {
    active = true;
    container.setPointerCapture(e.pointerId);
    sliderPercent = getPercent(e.clientX);
  }

  function onPointerMove(e: PointerEvent) {
    if (!active) return;
    sliderPercent = getPercent(e.clientX);
  }

  function onPointerUp() {
    active = false;
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="compare"
  bind:this={container}
  on:pointerdown={onPointerDown}
  on:pointermove={onPointerMove}
  on:pointerup={onPointerUp}
  on:pointercancel={onPointerUp}
>
  <!-- Bottom layer: original (always full width) -->
  <img class="layer" src={originalUrl} alt="Original" draggable="false" />

  <!-- Top layer: AI image, clipped to the left portion -->
  <img
    class="layer"
    src={aiUrl}
    alt="KI"
    style="clip-path: inset(0 {100 - sliderPercent}% 0 0)"
    draggable="false"
  />

  <!-- Corner labels -->
  <div class="label label-left">KI</div>
  <div class="label label-right">Original</div>

  <!-- Vertical divider + drag handle -->
  <div class="divider" style="left: {sliderPercent}%">
    <div class="handle" class:active>
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 5L3 11L8 17" stroke="#333" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M14 5L19 11L14 17" stroke="#333" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
  </div>
</div>

<style>
  .compare {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    border-radius: 16px;
    cursor: ew-resize;
    user-select: none;
    touch-action: none;
    background: #111;
    box-shadow: 0 8px 48px rgba(0,0,0,0.7);
  }

  .layer {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    pointer-events: none;
    display: block;
  }

  .label {
    position: absolute;
    top: 0.8rem;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: white;
    background: rgba(0,0,0,0.55);
    padding: 0.2rem 0.55rem;
    border-radius: 5px;
    pointer-events: none;
  }

  .label-left { left: 0.8rem; }
  .label-right { right: 0.8rem; }

  .divider {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: rgba(255,255,255,0.9);
    transform: translateX(-50%);
    pointer-events: none;
    box-shadow: 0 0 6px rgba(0,0,0,0.5);
  }

  .handle {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 46px;
    height: 46px;
    border-radius: 50%;
    background: white;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 16px rgba(0,0,0,0.45);
    pointer-events: auto;
    cursor: ew-resize;
    transition: transform 0.1s ease, box-shadow 0.1s ease;
  }

  .handle.active {
    transform: translate(-50%, -50%) scale(1.12);
    box-shadow: 0 4px 24px rgba(0,0,0,0.55);
  }

  .handle svg {
    pointer-events: none;
  }
</style>
