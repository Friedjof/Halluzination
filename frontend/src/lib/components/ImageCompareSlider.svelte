<script lang="ts">
  import { onMount, tick } from 'svelte';

  export let aiUrl: string;
  export let originalUrl: string;
  export let autoReveal = false;

  // Start fully on the AI side when auto-revealing
  let sliderPercent = autoReveal ? 100 : 50;
  let animating = false;
  let container: HTMLDivElement;
  let active = false;

  // Detect natural aspect ratio from the loaded image
  let aspectRatio = '16 / 9';
  function onImgLoad(e: Event) {
    const img = e.target as HTMLImageElement;
    if (img.naturalWidth && img.naturalHeight) {
      aspectRatio = `${img.naturalWidth} / ${img.naturalHeight}`;
    }
  }

  onMount(async () => {
    if (!autoReveal) return;
    animating = true;
    sliderPercent = 100;
    await tick(); // let the initial position render first
    // Short delay so the browser registers the start position before transitioning
    setTimeout(() => { sliderPercent = 0; }, 150);
    setTimeout(() => { animating = false; }, 5150); // 150ms delay + 5s animation
  });

  function getPercent(clientX: number): number {
    const rect = container.getBoundingClientRect();
    return Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
  }

  function onPointerDown(e: PointerEvent) {
    if (animating) return;
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
  class:animating
  style="aspect-ratio: {aspectRatio}"
  bind:this={container}
  on:pointerdown={onPointerDown}
  on:pointermove={onPointerMove}
  on:pointerup={onPointerUp}
  on:pointercancel={onPointerUp}
>
  <!-- Bottom layer: original (always full width) -->
  <img class="layer" src={originalUrl} alt="Original" draggable="false" on:load={onImgLoad} />

  <!-- Top layer: AI image, clipped to the left portion -->
  <img
    class="layer ai-layer"
    class:reveal-anim={animating}
    src={aiUrl}
    alt="KI"
    style="clip-path: inset(0 {100 - sliderPercent}% 0 0)"
    draggable="false"
  />

  <!-- Corner labels -->
  <div class="label label-left">KI</div>
  <div class="label label-right">Original</div>

  <!-- Vertical divider + drag handle -->
  <div class="divider" class:reveal-anim={animating} style="left: {sliderPercent}%">
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
    overflow: hidden;
    border-radius: 16px;
    cursor: ew-resize;
    user-select: none;
    touch-action: none;
    background: #111;
    box-shadow: 0 8px 48px rgba(0,0,0,0.7);
  }

  .compare.animating {
    cursor: default;
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

  /* Smooth 5s transition for the auto-reveal animation */
  .ai-layer.reveal-anim {
    transition: clip-path 5s ease-in-out;
  }

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

  .divider.reveal-anim {
    transition: left 5s ease-in-out;
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

  .compare.animating .handle {
    cursor: default;
    pointer-events: none;
  }

  .handle.active {
    transform: translate(-50%, -50%) scale(1.12);
    box-shadow: 0 4px 24px rgba(0,0,0,0.55);
  }

  .handle svg {
    pointer-events: none;
  }
</style>
