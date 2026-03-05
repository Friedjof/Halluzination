<script lang="ts">
  import { adminToken } from '$lib/stores/auth';
</script>

<div class="admin-shell">
  <header>
    <span class="logo">🎭 Halluzination</span>
    {#if $adminToken}
      <button class="logout" on:click={() => ($adminToken = '')}>Token löschen</button>
    {/if}
  </header>

  <main>
    <slot />
  </main>
</div>

<style>
  :global(*, *::before, *::after) { box-sizing: border-box; margin: 0; padding: 0; }
  :global(body) { font-family: system-ui, sans-serif; background: #f0f2f5; color: #1a1a2e; }
  :global(input, textarea, select, button) { font-family: inherit; }

  .admin-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  header {
    background: #1a1a2e;
    color: white;
    padding: 0.75rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo {
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .logout {
    background: transparent;
    border: 1px solid rgba(255,255,255,0.3);
    color: rgba(255,255,255,0.7);
    padding: 0.3rem 0.8rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.8rem;
  }
  .logout:hover { border-color: white; color: white; }

  main {
    flex: 1;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
  }
</style>
