import { useCallback, useEffect, useRef, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<{ data?: T; error?: Error; loading: boolean }>({ loading: true });
  const alive = useRef(true);
  const run = useCallback(() => {
    setState((s) => ({ data: s.data, loading: true }));
    fn().then(
      (data) => alive.current && setState({ data, loading: false }),
      (error) => alive.current && setState({ loading: false, error }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    alive.current = true;
    run();
    return () => { alive.current = false; };
  }, [run]);
  return { ...state, reload: run };
}
