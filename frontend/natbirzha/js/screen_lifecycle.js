const screenCleanups = new Set();

export function registerScreenCleanup(cleanup) {
  if (typeof cleanup !== 'function') return () => {};
  screenCleanups.add(cleanup);
  return () => screenCleanups.delete(cleanup);
}

export function disposeCurrentScreen() {
  const cleanups = [...screenCleanups];
  screenCleanups.clear();
  cleanups.forEach((cleanup) => {
    try { cleanup(); } catch (error) { console.warn('Screen cleanup failed:', error); }
  });
}
